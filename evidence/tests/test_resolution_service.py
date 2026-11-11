"""Opt-in HTTP integration with an explicitly supplied actual resolution snapshot.

No resolution imports or database reads occur in this process. The subprocesses
use the selected snapshot, temporary storage and a payment-denying test adapter.
"""
import copy
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from evidence.backend.server import make_server
from evidence.integrated import readiness_line
from test_assessment import fixture
from test_resolution_client import RunningServer
from test_resolution_integration import call

SOURCE = os.environ.get('RECALLRELAY_RESOLUTION_SOURCE')

# Isolated Python ignores PYTHONPATH and the user site. Only the explicit source
# root and installed lane dependencies are available; no provider env is passed.
SERVER = """
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from resolution.backend.server import make_server
class DenyPayments:
    mode = 'mock'
    def refund(self, *args, **kwargs):
        Path(sys.argv[3]).touch()
        raise RuntimeError('Payment calls are disabled in this integration check')
server = make_server(0, sys.argv[2], adapter=DenyPayments())
print(json.dumps({'port': server.server_port}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
"""
CLIENT = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from resolution.backend.evidence_client import EvidenceClient
print(json.dumps(EvidenceClient(sys.argv[2]).assess(json.load(sys.stdin))))
"""


@unittest.skipUnless(SOURCE, 'Set RECALLRELAY_RESOLUTION_SOURCE to an exported actual service snapshot')
class ActualResolutionServiceTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(SOURCE).resolve()
        if not (self.source / 'resolution/backend/server.py').is_file():
            self.fail('Selected snapshot has no actual resolution server')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.payment_attempt = self.folder / 'payment-attempt'
        self.env = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'}
        self.merchant = subprocess.Popen(
            [sys.executable, '-I', '-B', '-u', '-c', SERVER, str(self.source),
             str(self.folder / 'resolution.sqlite3'), str(self.payment_attempt)],
            cwd=self.source, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop_merchant)
        lines = queue.Queue(maxsize=1)
        self.reader = threading.Thread(target=readiness_line, args=(self.merchant.stdout, lines), daemon=True)
        self.reader.start()
        try:
            raw = lines.get(timeout=8)
        except queue.Empty:
            self.fail('Actual resolution server did not start within eight seconds')
        try:
            port = json.loads(raw)['port']
            self.assertIs(type(port), int)
            self.assertTrue(0 < port < 65536)
        except (ValueError, KeyError, TypeError):
            self.fail('Actual resolution server failed before readiness')
        self.upstream = f'http://127.0.0.1:{port}'
        self.customer = self.enterContext(RunningServer(make_server(
            0, self.folder / 'evidence.sqlite3', self.upstream)))
        self.addCleanup(self.assert_no_payment_attempt)

    def stop_merchant(self):
        if self.merchant.poll() is None:
            self.merchant.terminate()
            try:
                self.merchant.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.merchant.kill()
                self.merchant.wait(timeout=3)
        if self.reader.ident is not None:
            self.reader.join(timeout=2)
        self.merchant.stdout.close()

    def assert_no_payment_attempt(self):
        self.assertFalse(self.payment_attempt.exists(), 'Review/status attempted a payment')

    def assess_from_merchant(self, request):
        process = subprocess.run(
            [sys.executable, '-I', '-B', '-c', CLIENT, str(self.source), self.customer],
            input=json.dumps(request), text=True, cwd=self.source, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
        self.assertEqual(process.returncode, 0, 'Actual merchant evidence client failed')
        assessment = json.loads(process.stdout)
        self.assertEqual(assessment['mode'], 'manual')
        self.assertEqual(assessment['case_id'], request['order']['case_id'])
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, assessment))
        return assessment

    def review(self, request, assessment, remedy):
        # This coordinator explicitly supplies merchant-owned remedy confirmation.
        # The customer app itself never creates a review or approves a refund.
        return call(self.upstream, '/v1/resolutions', {
            'schema_version': '1.0', 'order': copy.deepcopy(request['order']),
            'assessment': copy.deepcopy(assessment), 'remedy_conditions_met': remedy})

    def assert_review(self, request, assessment, remedy, status, amount=0):
        code, reviewed = self.review(request, assessment, remedy)
        self.assertEqual((code, reviewed['status'], reviewed['proposed_amount_minor']),
                         (200, status, amount))
        self.assertEqual(reviewed['citations'], sorted({item['source_id'] for item in assessment['evidence']}))
        self.assertEqual((reviewed['mode'], reviewed['refund_id'], reviewed['operation_id']),
                         ('mock', None, None))
        self.assertEqual(call(self.customer, '/demo/resolution-status'), (200, reviewed))
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, assessment))
        return reviewed

    def test_handoff_uses_frozen_assessment_and_status_reads_do_not_mutate_it(self):
        self.assertEqual(call(self.customer, '/demo/resolution-status')[0], 404)
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1')[0], 404)
        request = fixture()
        assessment = self.assess_from_merchant(request)
        self.assertEqual(assessment['decision'], 'eligible')
        self.assert_review(request, assessment, False, 'manual_required')
        reviewed = self.assert_review(request, assessment, True, 'awaiting_approval', 4000)
        self.assertIn(assessment['assessment_id'], reviewed['brief'])
        self.assertEqual(self.review(request, assessment, True), (200, reviewed))
        changed = copy.deepcopy(request)
        changed['label']['confirmed_batch'] = ''
        code, latest = call(self.customer, '/v1/assessments', changed)
        self.assertEqual((code, latest['decision']), (200, 'needs_information'))
        self.assertNotEqual(latest['assessment_id'], assessment['assessment_id'])
        # Resolution retains the supplied snapshot after evidence changes.
        self.assertEqual(call(self.customer, '/demo/resolution-status'), (200, reviewed))
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, latest))

    def test_missing_identifier_stays_unresolved_in_both_services(self):
        request = fixture()
        request['label']['confirmed_batch'] = ''
        assessment = self.assess_from_merchant(request)
        self.assertEqual(assessment['decision'], 'needs_information')
        self.assertEqual(assessment['missing_fields'], ['batch'])
        self.assertTrue(assessment['clarification'])
        self.assert_review(request, assessment, True, 'needs_information')

    def test_excluded_batch_remains_excluded_after_handoff(self):
        request = fixture()
        request['label']['confirmed_batch'] = 'B103'
        assessment = self.assess_from_merchant(request)
        self.assertEqual(assessment['decision'], 'excluded')
        self.assert_review(request, assessment, True, 'excluded')

    def test_review_uses_remaining_minor_units_and_requires_supported_order_age(self):
        request = fixture()
        request['order']['previously_refunded_minor'] = 1500
        assessment = self.assess_from_merchant(request)
        self.assert_review(request, assessment, True, 'awaiting_approval', 2500)
        # A separate fresh case is needed because an evidence order snapshot is immutable.
        older = fixture()
        older['order']['case_id'] = 'case-old-order'
        older['order']['age_days'] = 181
        code, old_assessment = call(self.customer, '/v1/assessments', older)
        self.assertEqual((code, old_assessment['decision']), (200, 'eligible'))
        code, reviewed = self.review(older, old_assessment, True)
        self.assertEqual((code, reviewed['status'], reviewed['proposed_amount_minor']),
                         (200, 'manual_required', 0))
        self.assertEqual((reviewed['refund_id'], reviewed['operation_id']), (None, None))

    def test_mismatched_case_is_rejected_without_replacing_a_review(self):
        request = fixture()
        assessment = self.assess_from_merchant(request)
        reviewed = self.assert_review(request, assessment, True, 'awaiting_approval', 4000)
        wrong = copy.deepcopy(assessment)
        wrong['case_id'] = 'case-other'
        self.assertEqual(self.review(request, wrong, True)[0], 400)
        self.assertEqual(call(self.customer, '/demo/resolution-status'), (200, reviewed))
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, assessment))

    def test_merchant_failure_is_visible_and_typed_entry_remains_usable(self):
        request = fixture()
        assessment = self.assess_from_merchant(request)
        self.assert_review(request, assessment, True, 'awaiting_approval', 4000)
        self.stop_merchant()
        code, failed = call(self.customer, '/demo/resolution-status')
        self.assertEqual(code, 503)
        self.assertIn('error', failed)
        self.assertNotIn('status', failed)
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, assessment))
        request['label']['confirmed_batch'] = 'B102'
        code, updated = call(self.customer, '/demo/assessments', {'label': request['label']})
        self.assertEqual((code, updated['decision'], updated['batch']), (200, 'eligible', 'B102'))
        self.assertEqual(call(self.customer, '/v1/assessments/case-demo-1'), (200, updated))
