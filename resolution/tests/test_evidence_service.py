"""Actual-service smoke: resolution's EvidenceClient and server against the real evidence HTTP service.

Evidence runs as a separate process (never imported). Typed confirmed identifiers only: no image
extraction, AI provider, PayPal or credentials are involved, and refunds use the fake adapter.
"""
import copy
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from resolution.backend.evidence_client import EvidenceClient, EvidenceUnavailable
from resolution.backend.server import make_server

try:
    import PIL  # Needed only by the evidence service process, which this test starts.
except ImportError:
    PIL = None

ROOT = Path(__file__).resolve().parents[2]
ASSESSMENT_REQUEST = json.loads((ROOT / 'contracts/fixtures/assessment-request.json').read_text())


class EvidenceProcess:
    """The real evidence server on an ephemeral loopback port with its own temporary database."""

    def __init__(self, db_path):
        env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP') if key in os.environ}  # No provider keys.
        self.process = subprocess.Popen(
            [sys.executable, '-B', '-m', 'evidence.backend.server', '--port', '0', '--db', str(db_path)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(self.process.stdout.readline()), daemon=True).start()
        try:
            match = re.search(r'http://127\.0\.0\.1:(\d+)', lines.get(timeout=20))
        except queue.Empty:
            match = None
        if not match:
            self.stop()
            raise RuntimeError('Evidence service did not start')
        self.url = f'http://127.0.0.1:{match.group(1)}'

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdout.close()


@unittest.skipIf(PIL is None, 'Install evidence/requirements.lock.txt to run the actual evidence service')
class ActualServiceSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.evidence = EvidenceProcess(Path(cls.tmp.name) / 'evidence.sqlite3')
        cls.resolution = make_server(0, Path(cls.tmp.name) / 'resolution.sqlite3')
        cls.thread = threading.Thread(target=cls.resolution.serve_forever, daemon=True)
        cls.thread.start()
        cls.resolution_url = f'http://127.0.0.1:{cls.resolution.server_port}'
        cls.client = EvidenceClient(cls.evidence.url)

    @classmethod
    def tearDownClass(cls):
        cls.resolution.shutdown()
        cls.resolution.server_close()
        cls.thread.join(timeout=2)
        cls.evidence.stop()
        cls.tmp.cleanup()

    def assess(self, case_id, **label):
        request = copy.deepcopy(ASSESSMENT_REQUEST)
        request['order']['case_id'] = case_id
        request['label'].update(label)
        return request, self.client.assess(request)

    def resolve(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.resolution_url + path, data=data, method=method, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def handoff(self, request, assessment, remedy_conditions_met=False):
        return self.resolve('POST', '/v1/resolutions', {
            'schema_version': '1.0', 'order': request['order'], 'assessment': assessment,
            'remedy_conditions_met': remedy_conditions_met})

    def test_eligible_identifiers_flow_through_both_services_to_a_fake_refund(self):
        request, assessment = self.assess('case-smoke-eligible')
        self.assertEqual((assessment['decision'], assessment['mode'], assessment['batch']), ('eligible', 'manual', 'B101'))

        code, review = self.handoff(request, assessment)  # Merchant has not confirmed the remedy yet.
        self.assertEqual((code, review['status'], review['proposed_amount_minor']), (200, 'manual_required', 0))
        code, review = self.handoff(request, assessment, remedy_conditions_met=True)
        self.assertEqual((code, review['status'], review['proposed_amount_minor']), (200, 'awaiting_approval', 4000))
        self.assertEqual(review['citations'], ['confirmed-label'])

        binding = {'assessment_id': assessment['assessment_id'], 'campaign_version': assessment['campaign_version'],
                   'capture_id': request['order']['capture_id'], 'amount_minor': 4000, 'approved_by': 'smoke-merchant'}
        code, done = self.resolve('POST', '/v1/cases/case-smoke-eligible/approve', binding)
        self.assertEqual((code, done['status'], done['mode']), (200, 'refunded', 'mock'))
        self.assertEqual(self.resolve('GET', '/v1/resolutions/case-smoke-eligible'), (200, done))
        self.assertEqual(self.resolve('POST', '/v1/cases/case-smoke-eligible/approve', binding), (200, done))  # Replay: same refund.

    def test_missing_batch_stays_needs_information_with_no_money_proposed(self):
        request, assessment = self.assess('case-smoke-missing', confirmed_batch='')
        self.assertEqual((assessment['decision'], assessment['missing_fields']), ('needs_information', ['batch']))
        code, review = self.handoff(request, assessment, remedy_conditions_met=True)
        self.assertEqual((code, review['status'], review['proposed_amount_minor']), (200, 'needs_information', 0))
        self.assertEqual(self.resolve('POST', '/v1/cases/case-smoke-missing/approve', {
            'assessment_id': assessment['assessment_id'], 'campaign_version': 1,
            'capture_id': request['order']['capture_id'], 'amount_minor': 4000, 'approved_by': 'smoke-merchant'})[0], 409)

    def test_excluded_batch_stays_excluded_with_no_money_proposed(self):
        request, assessment = self.assess('case-smoke-excluded', confirmed_batch='B103')
        self.assertEqual(assessment['decision'], 'excluded')
        code, review = self.handoff(request, assessment, remedy_conditions_met=True)
        self.assertEqual((code, review['status'], review['proposed_amount_minor']), (200, 'excluded', 0))

    def test_assessment_for_a_different_case_is_rejected_by_resolution(self):
        request, assessment = self.assess('case-smoke-wrong-a')
        request['order']['case_id'] = 'case-smoke-wrong-b'
        code, _ = self.handoff(request, assessment, remedy_conditions_met=True)
        self.assertEqual(code, 400)
        self.assertEqual(self.resolve('GET', '/v1/resolutions/case-smoke-wrong-b')[0], 404)

    def test_stopped_evidence_service_is_a_visible_error_not_a_fabricated_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = EvidenceProcess(Path(tmp) / 'evidence.sqlite3')
            client = EvidenceClient(service.url, timeout=2)
            self.assertEqual(client.assess(ASSESSMENT_REQUEST)['case_id'], 'case-demo-1')
            service.stop()
            with self.assertRaises(EvidenceUnavailable):
                client.assess(ASSESSMENT_REQUEST)


if __name__ == '__main__':
    unittest.main()
