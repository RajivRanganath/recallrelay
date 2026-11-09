import base64
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest

from resolution.backend.envfile import read_secrets
from resolution.backend.paypal import RefundRejected, RefundUnknown
from resolution.backend.paypal_sandbox import SandboxPayPal, amount_text, load_credentials
from resolution.backend.refund import approve, reconcile
from resolution.backend.review import review
from resolution.backend.store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())
CAPTURE = 'STUBCAPTURE123'  # Not a fixture ID, so the sandbox guard lets it through to the local stub.


class StubPayPal:
    """Local stand-in for PayPal's sandbox API. Scripted refund replies, recorded requests."""

    def __init__(self, replies=()):
        self.replies, self.requests, self.tokens = list(replies), [], 0
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, body):
                raw = json.dumps(body).encode() if body is not None else b''
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                if self.path == '/v1/oauth2/token':
                    stub.tokens += 1
                    stub.requests.append(('token', {k.lower(): v for k, v in self.headers.items()}, body))
                    return self.reply(200, {'access_token': f'stub-token-{stub.tokens}', 'expires_in': 3600})
                stub.requests.append(('refund', {k.lower(): v for k, v in self.headers.items()}, json.loads(body), self.path))
                code, reply = stub.replies.pop(0) if stub.replies else (201, {'id': 'REFUND-1', 'status': 'COMPLETED'})
                if code == 'slow':
                    time.sleep(1.0)
                    return
                self.reply(code, reply)

            def do_GET(self):
                self.reply(200, {'id': 'REFUND-1', 'status': 'COMPLETED', 'amount': {'value': '40.00', 'currency_code': 'USD'}, 'secret': 'x'})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f'http://127.0.0.1:{self.server.server_port}'

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class AdapterTests(unittest.TestCase):
    def adapter(self, url, **kwargs):
        return SandboxPayPal('stub-id', 'stub-SECRET', base_url=url, timeout=kwargs.pop('timeout', 5))

    def test_wire_format(self):
        stub = StubPayPal()
        with stub as url:
            SandboxPayPal('stub-id', 'stub-SECRET', base_url=url).refund('op-abc', CAPTURE, 4005, 'USD')
        token, refund = stub.requests
        self.assertEqual(token[1]['authorization'], 'Basic ' + base64.b64encode(b'stub-id:stub-SECRET').decode())
        self.assertEqual(token[2], b'grant_type=client_credentials')
        self.assertEqual(refund[3], f'/v2/payments/captures/{CAPTURE}/refund')
        self.assertEqual(refund[1]['authorization'], 'Bearer stub-token-1')
        self.assertEqual(refund[1]['paypal-request-id'], 'op-abc')
        self.assertEqual(refund[2], {'amount': {'value': '40.05', 'currency_code': 'USD'}})

    def test_token_is_cached_and_replaced_after_a_401(self):
        stub = StubPayPal([(201, {'id': 'R1', 'status': 'COMPLETED'}), (401, {'name': 'AUTHENTICATION_FAILURE'}),
                           (201, {'id': 'R1', 'status': 'COMPLETED'})])
        with stub as url:
            adapter = SandboxPayPal('i', 's', base_url=url)
            adapter.refund('op-1', CAPTURE, 100, 'USD')
            with self.assertRaises(RefundUnknown):
                adapter.refund('op-1', CAPTURE, 100, 'USD')
            adapter.refund('op-1', CAPTURE, 100, 'USD')
        self.assertEqual(stub.tokens, 2)

    def test_outcome_mapping_keeps_uncertain_results_pending(self):
        cases = [((201, {'id': 'R', 'status': 'COMPLETED'}), None), ((200, {'id': 'R', 'status': 'COMPLETED'}), None),
                 ((201, {'id': 'R', 'status': 'PENDING'}), RefundUnknown), ((201, {'id': 'R', 'status': 'ODD'}), RefundUnknown),
                 ((201, {'id': 'R', 'status': 'FAILED'}), RefundRejected), ((201, {'id': 'R', 'status': 'CANCELLED'}), RefundRejected),
                 ((422, {'name': 'UNPROCESSABLE_ENTITY', 'details': [{'issue': 'REFUND_NOT_ALLOWED_AFTER_180_DAYS'}]}), RefundRejected),
                 ((400, {}), RefundRejected), ((404, {}), RefundRejected),
                 ((401, {}), RefundUnknown), ((403, {}), RefundUnknown), ((409, {}), RefundUnknown),
                 ((429, {}), RefundUnknown), ((500, {}), RefundUnknown), ((503, None), RefundUnknown),
                 ((201, {'status': 'COMPLETED'}), RefundUnknown), ((200, None), RefundUnknown)]
        for reply, expected in cases:
            with self.subTest(reply=reply), StubPayPal([reply]) as url:
                adapter = SandboxPayPal('i', 's', base_url=url)
                if expected is None:
                    self.assertEqual(adapter.refund('op-1', CAPTURE, 100, 'USD'), 'R')
                else:
                    with self.assertRaises(expected):
                        adapter.refund('op-1', CAPTURE, 100, 'USD')

    def test_timeout_and_unreachable_are_unknown_never_rejected(self):
        with StubPayPal([('slow', None)]) as url:
            with self.assertRaises(RefundUnknown):
                SandboxPayPal('i', 's', base_url=url, timeout=0.3).refund('op-1', CAPTURE, 100, 'USD')
        with self.assertRaises(RefundUnknown):  # Server is gone now.
            SandboxPayPal('i', 's', base_url=url, timeout=1).refund('op-1', CAPTURE, 100, 'USD')

    def test_only_usd_and_the_sandbox_host_are_allowed(self):
        with self.assertRaises(RefundRejected):
            SandboxPayPal('i', 's', base_url='http://127.0.0.1:1').refund('op-1', CAPTURE, 100, 'EUR')
        for url in ('https://api-m.paypal.com', 'https://api.paypal.com', 'https://api-m.sandbox.paypal.com.evil.example',
                    'http://api-m.sandbox.paypal.com', 'https://user:pw@api-m.sandbox.paypal.com', 'https://evil.example',
                    'http://example.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SandboxPayPal('i', 's', base_url=url)
        SandboxPayPal('i', 's')  # The real sandbox host is the default.
        self.assertEqual((amount_text(4000), amount_text(5), amount_text(123456)), ('40.00', '0.05', '1234.56'))

    def test_secrets_never_appear_in_repr_or_errors(self):
        with StubPayPal([(500, {'echo': 'stub-SECRET'})]) as url:
            adapter = SandboxPayPal('stub-id', 'stub-SECRET', base_url=url)
            with self.assertRaises(RefundUnknown) as caught:
                adapter.refund('op-1', CAPTURE, 100, 'USD')
        for text in (repr(adapter), str(caught.exception), repr(caught.exception)):
            self.assertNotIn('stub-SECRET', text)
            self.assertNotIn(base64.b64encode(b'stub-id:stub-SECRET').decode(), text)

    def test_read_back_returns_only_expected_fields(self):
        with StubPayPal() as url:
            result = SandboxPayPal('i', 's', base_url=url).get_refund('REFUND-1')
        self.assertEqual((result['status'], result['amount']['value']), ('COMPLETED', '40.00'))
        self.assertNotIn('secret', result)


class EnvFileTests(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'paypal.env'
        path.write_text(text)
        return path

    def test_reads_only_the_named_entries_without_executing_anything(self):
        path = self.write('# comment\nOTHER=ignored\nexport PAYPAL_CLIENT_ID="abc123"\nPAYPAL_CLIENT_SECRET=\'s3cret\'\n$(touch pwned)\n')
        self.assertEqual(load_credentials(path), ('abc123', 's3cret'))

    def test_missing_duplicate_or_malformed_entries_are_rejected(self):
        for text in ('PAYPAL_CLIENT_ID=a\n', 'PAYPAL_CLIENT_ID=a\nPAYPAL_CLIENT_ID=b\nPAYPAL_CLIENT_SECRET=c\n',
                     'PAYPAL_CLIENT_ID="a\nPAYPAL_CLIENT_SECRET=c\n', 'PAYPAL_CLIENT_ID=a b\nPAYPAL_CLIENT_SECRET=c\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                load_credentials(self.write(text))
        with self.assertRaises(ValueError):
            read_secrets(('SOME_UNSET_NAME_FOR_TEST',), None)


class SandboxFlowTests(unittest.TestCase):
    """The approval flow driven by the real adapter code against the local stub."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'cases.sqlite3')
        request = copy.deepcopy(FIXTURE)
        request['order']['capture_id'] = CAPTURE
        request['remedy_conditions_met'] = True
        self.store.save_review(request, review(request))
        self.approval = {'assessment_id': 'assessment-demo-1', 'campaign_version': 1, 'capture_id': CAPTURE,
                         'amount_minor': 4000, 'approved_by': 'merchant-demo'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_completed_refund_is_reported_as_sandbox_with_the_paypal_id(self):
        with StubPayPal() as url:
            done = approve(self.store, SandboxPayPal('i', 's', base_url=url), 'case-demo-1', self.approval)
        self.assertEqual((done['status'], done['mode'], done['refund_id']), ('refunded', 'sandbox', 'REFUND-1'))

    def test_pending_reply_then_reconcile_reuses_the_same_request_id(self):
        stub = StubPayPal([(500, {}), (201, {'id': 'REFUND-1', 'status': 'COMPLETED'})])
        with stub as url:
            adapter = SandboxPayPal('i', 's', base_url=url)
            pending = approve(self.store, adapter, 'case-demo-1', self.approval)
            self.assertEqual((pending['status'], pending['mode'], pending['refund_id']), ('pending', 'sandbox', None))
            done = reconcile(self.store, adapter, 'case-demo-1')
        self.assertEqual((done['status'], done['refund_id']), ('refunded', 'REFUND-1'))
        ids = {r[1]['paypal-request-id'] for r in stub.requests if r[0] == 'refund'}
        self.assertEqual(ids, {pending['operation_id']})

    def test_paypal_refusal_marks_the_case_failed_without_retrying(self):
        stub = StubPayPal([(422, {'name': 'UNPROCESSABLE_ENTITY'})])
        with stub as url:
            failed = approve(self.store, SandboxPayPal('i', 's', base_url=url), 'case-demo-1', self.approval)
        self.assertEqual((failed['status'], failed['refund_id']), ('failed', None))
        self.assertEqual(len([r for r in stub.requests if r[0] == 'refund']), 1)

    def test_fixture_capture_ids_still_cannot_reach_the_sandbox(self):
        stub = StubPayPal()
        request = copy.deepcopy(FIXTURE)
        request['remedy_conditions_met'] = True
        self.store.save_review(request, review(request))  # Re-review with the fixture capture ID.
        with stub as url:
            with self.assertRaises(Exception):
                approve(self.store, SandboxPayPal('i', 's', base_url=url), 'case-demo-1',
                        dict(self.approval, capture_id='capture-demo-NOT-PAYPAL'))
        self.assertEqual(stub.requests, [])


if __name__ == '__main__':
    unittest.main()
