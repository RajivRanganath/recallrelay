import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from resolution.ai.brief import BriefService
from resolution.backend.server import make_server
from resolution.backend.store import CaseStore
from resolution.backend.validation import validate_contract

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'cases.sqlite3'
        self.server = make_server(0, self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def call(self, method, path, body=None, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = Request(self.url + path, data=data, method=method, headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def eligible(self):
        data = copy.deepcopy(FIXTURE)
        data['remedy_conditions_met'] = True
        return data

    def test_post_then_get_returns_the_same_review(self):
        code, posted = self.call('POST', '/v1/resolutions', self.eligible())
        self.assertEqual((code, posted['status']), (200, 'awaiting_approval'))
        validate_contract('resolution-response', posted)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1'), (200, posted))
        self.assertEqual(self.call('POST', '/v1/resolutions', self.eligible()), (200, posted))

    def test_get_unknown_case_is_404_and_never_creates_one(self):
        self.assertEqual(self.call('GET', '/v1/resolutions/unknown')[0], 404)
        self.assertEqual(self.call('GET', '/v1/resolutions/unknown')[0], 404)

    def test_reposted_handoff_cannot_clear_merchant_confirmation(self):
        self.call('POST', '/v1/resolutions', copy.deepcopy(FIXTURE))
        _, confirmed = self.call('POST', '/v1/cases/case-demo-1/remedy-conditions')
        self.assertEqual(self.call('POST', '/v1/resolutions', copy.deepcopy(FIXTURE)), (200, confirmed))
        detail = self.call('GET', '/v1/cases/case-demo-1')[1]
        self.assertTrue(detail['remedy_conditions_met'])
        self.assertIsNone(detail['operation'])

    def test_case_detail_keeps_the_shape_the_evidence_handoff_recovery_reads(self):
        # The evidence service (handoff_if_needed) compares these exact fields to decide whether a lost
        # acknowledgement already reached this service. Changing them breaks that recovery; see
        # docs/vismaya/INTEGRATION-DEPENDENCIES.md.
        sent = copy.deepcopy(FIXTURE)
        sent['remedy_conditions_met'] = False
        self.call('POST', '/v1/resolutions', sent)
        detail = self.call('GET', '/v1/cases/case-demo-1')[1]
        self.assertEqual(set(detail['assessment']), {'assessment_id', 'decision', 'model', 'batch', 'reason', 'evidence', 'mode',
                                                     'missing_fields', 'clarification'})
        self.assertEqual(set(detail['order']), {'order_id', 'paid_minor', 'previously_refunded_minor', 'age_days', 'quantity'})
        self.assertTrue({'assessment_id', 'campaign_version', 'capture_id', 'currency'} <= set(detail['binding']))
        self.assertEqual(detail['resolution']['case_id'], 'case-demo-1')
        self.assertIn('status', detail['resolution'])

    def test_invalid_bodies_are_rejected_without_echoing_input(self):
        bad = self.eligible()
        bad['order']['paid_minor'] = 'SECRET-VALUE'
        for raw in (json.dumps(bad).encode(), b'not json', b'{"a":1,"a":2}', b'{}'):
            code, body = self.call('POST', '/v1/resolutions', raw=raw)
            self.assertEqual(code, 400)
            self.assertNotIn('SECRET-VALUE', json.dumps(body))

    def test_unknown_route_is_404(self):
        self.assertEqual(self.call('POST', '/v1/other', self.eligible())[0], 404)

    def test_merchant_flow_demo_confirm_remedy_approve_refund(self):
        code, seeded = self.call('POST', '/v1/demo/case')
        self.assertEqual((code, seeded['status']), (200, 'manual_required'))  # remedy not yet confirmed
        self.assertEqual(self.call('POST', '/v1/demo/case'), (200, seeded))
        detail = self.call('GET', '/v1/cases/case-demo-1')[1]
        self.assertFalse(detail['remedy_conditions_met'])
        self.assertEqual(self.call('GET', '/v1/cases')[1]['cases'], [seeded])
        code, reviewed = self.call('POST', '/v1/cases/case-demo-1/remedy-conditions')
        self.assertEqual((code, reviewed['status'], reviewed['proposed_amount_minor']), (200, 'awaiting_approval', 4000))
        binding = self.call('GET', '/v1/cases/case-demo-1')[1]['binding']
        approval = {key: binding[key] for key in ('assessment_id', 'campaign_version', 'capture_id', 'amount_minor')}
        code, done = self.call('POST', '/v1/cases/case-demo-1/approve', dict(approval, approved_by='merchant-demo'))
        self.assertEqual((code, done['status'], done['mode']), (200, 'refunded', 'mock'))
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/remedy-conditions')[0], 409)
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/reconcile')[0], 409)
        self.assertEqual(self.call('POST', '/v1/cases/unknown/remedy-conditions')[0], 404)

    def test_wrong_amount_is_rejected_over_http(self):
        self.call('POST', '/v1/demo/case')
        self.call('POST', '/v1/cases/case-demo-1/remedy-conditions')
        binding = self.call('GET', '/v1/cases/case-demo-1')[1]['binding']
        approval = {key: binding[key] for key in ('assessment_id', 'campaign_version', 'capture_id')}
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/approve', dict(approval, amount_minor=1, approved_by='m'))[0], 409)
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/approve', {'approved_by': 'm'})[0], 400)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1')[1]['status'], 'awaiting_approval')

    def prepare_awaiting_approval(self):
        self.call('POST', '/v1/demo/case')
        self.call('POST', '/v1/cases/case-demo-1/remedy-conditions')
        binding = self.call('GET', '/v1/cases/case-demo-1')[1]['binding']
        return {key: binding[key] for key in ('assessment_id', 'campaign_version', 'capture_id', 'amount_minor')} | {'approved_by': 'merchant-demo'}

    def test_hostile_origins_cannot_change_state_on_any_post_route(self):
        approval = self.prepare_awaiting_approval()
        for origin in ('http://evil.example', 'null', 'http://127.0.0.1:1', 'https://127.0.0.1:%d' % self.server.server_port):
            for path, body in (('/v1/cases/case-demo-1/approve', approval), ('/v1/cases/case-demo-1/remedy-conditions', None),
                               ('/v1/cases/case-demo-1/reconcile', None), ('/v1/demo/case', None),
                               ('/v1/resolutions', self.eligible())):
                with self.subTest(origin=origin, path=path):
                    self.assertEqual(self.call('POST', path, body, headers={'Origin': origin})[0], 403)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1')[1]['status'], 'awaiting_approval')
        self.assertIsNone(self.call('GET', '/v1/cases/case-demo-1')[1]['operation'])

    def test_same_origin_browser_requests_still_work(self):
        approval = self.prepare_awaiting_approval()
        origin = {'Origin': f'http://127.0.0.1:{self.server.server_port}'}
        localhost = {'Origin': f'http://localhost:{self.server.server_port}'}
        self.assertEqual(self.call('POST', '/v1/demo/case', headers=localhost)[0], 200)
        code, done = self.call('POST', '/v1/cases/case-demo-1/approve', approval, headers=origin)
        self.assertEqual((code, done['status']), (200, 'refunded'))

    def test_body_routes_require_a_json_content_type(self):
        approval = self.prepare_awaiting_approval()
        for content_type in ('text/plain', 'application/x-www-form-urlencoded', 'multipart/form-data', 'text/plain;charset=UTF-8'):
            for path, body in (('/v1/cases/case-demo-1/approve', approval), ('/v1/resolutions', self.eligible())):
                with self.subTest(content_type=content_type, path=path):
                    code, _ = self.call('POST', path, raw=json.dumps(body).encode(), headers={'Content-Type': content_type})
                    self.assertEqual(code, 415)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1')[1]['status'], 'awaiting_approval')
        self.assertIsNone(self.call('GET', '/v1/cases/case-demo-1')[1]['operation'])
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/approve', approval, headers={'Content-Type': 'application/json; charset=utf-8'})[0], 200)

    def test_brief_route_is_advisory_origin_protected_and_defaults_to_the_template(self):
        self.prepare_awaiting_approval()
        before = self.call('GET', '/v1/cases/case-demo-1')
        code, brief = self.call('POST', '/v1/cases/case-demo-1/brief')
        self.assertEqual((code, brief['source'], brief['fallback_reason']), (200, 'template', 'no_provider'))
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/brief', headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/v1/cases/unknown/brief')[0], 404)
        self.assertEqual(self.call('GET', '/v1/cases/case-demo-1'), before)  # Advisory: no state change, no operation, no refund.
        self.assertEqual(self.call('GET', '/health')[1]['brief'], 'template')

    def test_brief_route_uses_a_provider_only_when_configured_and_validates_its_output(self):
        class Provider:
            name = 'scripted'

            def __init__(self, content):
                self.content = content

            def complete(self, system, user):
                return json.dumps(self.content), 'served-model-1'

        good = {'summary': 'Batch B101 matches and the refund of 40.00 USD awaits your approval.', 'missing_steps': [], 'citations': ['review']}
        bad = {'summary': 'The refund has been approved and paid.', 'missing_steps': [], 'citations': ['review']}
        for content, source in ((good, 'ai'), (bad, 'template')):
            with self.subTest(source=source):
                with tempfile.TemporaryDirectory() as tmp:
                    server = make_server(0, Path(tmp) / 'cases.sqlite3', brief=BriefService(Provider(content)))
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        url = f'http://127.0.0.1:{server.server_port}'
                        for path in ('/v1/demo/case', '/v1/cases/case-demo-1/remedy-conditions'):
                            urlopen(Request(url + path, data=b'', method='POST'), timeout=5).close()
                        with urlopen(Request(url + '/v1/cases/case-demo-1/brief', data=b'', method='POST'), timeout=5) as response:
                            result = json.loads(response.read())
                        with urlopen(url + '/health', timeout=5) as response:
                            self.assertEqual(json.loads(response.read())['brief'], 'ai')
                    finally:
                        server.shutdown()
                        server.server_close()
                        thread.join(timeout=2)
                self.assertEqual(result['source'], source)
                self.assertEqual(result['fallback_reason'], None if source == 'ai' else 'invalid_output')

    def test_ui_assets_are_served_with_a_restrictive_policy(self):
        for path, kind in (('/', 'text/html'), ('/app.js', 'text/javascript'), ('/style.css', 'text/css')):
            with urlopen(self.url + path, timeout=5) as response:
                self.assertTrue(response.headers['Content-Type'].startswith(kind))
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])

    def test_review_cannot_overwrite_a_refund_in_progress(self):
        pending = {'schema_version': '1.0', 'case_id': 'case-demo-1', 'status': 'pending', 'brief': 'x',
                   'citations': [], 'proposed_amount_minor': 4000, 'currency': 'USD', 'refund_id': None,
                   'operation_id': 'operation-1', 'mode': 'sandbox'}
        with CaseStore(self.db).connect() as db:
            db.execute('INSERT INTO cases(case_id,status,response) VALUES(?,?,?)', ('case-demo-1', 'pending', json.dumps(pending)))
        self.assertEqual(self.call('POST', '/v1/resolutions', self.eligible())[0], 409)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1'), (200, pending))


if __name__ == '__main__':
    unittest.main()
