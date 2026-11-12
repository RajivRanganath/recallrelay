"""Opt-in live modes of the unified workspace against LOCAL stubs: no PayPal, model or credential is used."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import unittest

from evidence.ai.extraction import ExtractionResult
from evidence.demo import running
from evidence.integrated import integrated_session, sandbox_order
from test_assessment import fixture
from test_resolution_integration import call

ORDER = {'order_id': 'ORDER-STUB-1', 'capture_id': 'CAPTURE-STUB-1', 'paid_minor': 4000, 'previously_refunded_minor': 0}


class StubModel:
    mode, provider_name = 'ai', 'stub-model'

    def extract(self, image):
        return ExtractionResult({'model': {'value': 'LAMP-100', 'confidence': .97, 'uncertain': False},
                                 'batch': {'value': None, 'confidence': None, 'uncertain': True}},
                                {'provider': 'stub-model', 'served_model': 'stub-1'})


def paypal_stub():
    """Just enough of PayPal's API for approval checks, an idempotent refund and its read-back."""
    refunds, posts = {}, []  # request ID -> refund; every refund POST's request ID

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body, code=200):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            amount = {'value': '40.00', 'currency_code': 'USD'}
            if self.path == '/v2/payments/captures/CAPTURE-STUB-1':
                return self.reply({'status': 'COMPLETED', 'amount': amount,
                                   'supplementary_data': {'related_ids': {'order_id': 'ORDER-STUB-1'}}})
            if self.path == '/v2/checkout/orders/ORDER-STUB-1':
                return self.reply({'purchase_units': [{'payments': {'captures': [{'id': 'CAPTURE-STUB-1'}], 'refunds': []}}]})
            if self.path.startswith('/v1/customer/disputes'):
                return self.reply({'items': []})
            found = next((r for r in refunds.values() if self.path == '/v2/payments/refunds/' + r['id']), None)
            self.reply(found or {}, 200 if found else 404)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.path == '/v1/oauth2/token':
                return self.reply({'access_token': 'stub-token', 'expires_in': 3600})
            if self.path == '/v2/payments/captures/CAPTURE-STUB-1/refund':
                request_id = self.headers['PayPal-Request-Id']
                posts.append(request_id)
                sent = json.loads(body)
                refund = refunds.setdefault(request_id, {'id': f'REFUND-STUB-{len(refunds) + 1}', 'status': 'COMPLETED',
                                                         'amount': sent['amount'], 'custom_id': sent['custom_id']})
                return self.reply(refund, 201)
            self.reply({}, 404)

    return ThreadingHTTPServer(('127.0.0.1', 0), Handler), refunds, posts


class LiveWorkspaceTests(unittest.TestCase):
    def test_sandbox_refund_with_lost_acknowledgement_recovers_without_a_second_refund(self):
        server, refunds, posts = paypal_stub()
        with tempfile.TemporaryDirectory() as folder, running(server) as paypal:
            env = Path(folder) / 'paypal.env'
            env.write_text('PAYPAL_CLIENT_ID=stub-id\nPAYPAL_CLIENT_SECRET=stub-secret\n')
            options = {'paypal': 'sandbox', 'paypal_env': str(env), 'paypal_options': {'base_url': paypal},
                       'lose_first_refund_response': True}
            with integrated_session(extraction_adapter=StubModel(), merchant_options=options, order=ORDER) as session:
                app = session.application_url
                self.assertEqual(call(app, '/api/customer/health')[1]['extraction_mode'], 'ai')
                self.assertEqual(call(app, '/api/merchant/health')[1]['mode'], 'sandbox')
                self.assertEqual(call(app, '/api/session'), (200, {'lose_first_refund_response': True}))
                saved = call(app, '/api/customer/demo/assessments', {'label': fixture()['label']})[1]
                self.assertEqual(call(app, '/api/customer/demo/handoff', {'assessment_id': saved['assessment_id']})[0], 200)
                case = '/api/merchant/v1/cases/case-demo-1'
                call(app, case + '/remedy-conditions', {})
                binding = call(app, case)[1]['binding']
                self.assertEqual((binding['capture_id'], binding['amount_minor']), ('CAPTURE-STUB-1', 4000))
                approval = {k: v for k, v in binding.items() if k != 'currency'} | {'approved_by': 'synthetic-merchant'}
                code, pending = call(app, case + '/approve', approval)
                # The provider accepted one refund, but the acknowledgement was lost: unknown, never "refunded".
                self.assertEqual((code, pending['status'], pending['refund_id'], len(refunds)), (200, 'pending', None, 1))
                self.assertEqual(call(app, '/api/customer/demo/resolution-status'), (200, pending))
                self.assertEqual(call(app, case + '/approve', approval), (200, pending))  # A repeat approval sends nothing.
                self.assertEqual(len(posts), 1)
                code, done = call(app, case + '/reconcile', {})
                self.assertEqual((code, done['status'], done['mode']), (200, 'refunded', 'sandbox'))
                self.assertEqual(done['operation_id'], pending['operation_id'])
                # Same operation ID re-sent as the request ID; the provider still holds exactly one refund.
                self.assertEqual((posts, list(refunds)), ([done['operation_id']] * 2, [done['operation_id']]))
                self.assertEqual(done['refund_id'], refunds[done['operation_id']]['id'])
                self.assertEqual(call(app, '/api/customer/demo/resolution-status'), (200, done))

    def test_ai_proposal_keeps_uncertain_field_blank_and_never_decides(self):
        with integrated_session(extraction_adapter=StubModel()) as session:
            image = fixture_image()
            code, proposal = call(session.application_url, '/api/customer/demo/image-extraction', image)
            self.assertEqual((code, proposal['mode'], proposal['model'], proposal['batch']), (200, 'ai', 'LAMP-100', None))
            self.assertEqual((proposal['uncertain_fields'], proposal['source']['served_model']), (['batch'], 'stub-1'))
            self.assertNotIn('decision', proposal)
            self.assertEqual(call(session.resolution_url, '/v1/cases')[1], {'cases': []})

    def test_sandbox_needs_a_real_capture_and_fake_payments_refuse_one(self):
        for options, order in (({'paypal': 'sandbox'}, None), ({}, ORDER),
                               ({'paypal': 'sandbox'}, dict(ORDER, capture_id='capture-demo-NOT-PAYPAL'))):
            with self.subTest(options=options), self.assertRaises(ValueError):
                with integrated_session(merchant_options=options, order=order):
                    pass

    def test_unusable_credentials_stop_startup_without_echoing_them(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / 'paypal.env'
            env.write_text('PAYPAL_CLIENT_ID=only-one-value-SECRETISH\n')
            with self.assertRaises(RuntimeError) as failure:
                with integrated_session(merchant_options={'paypal': 'sandbox', 'paypal_env': str(env)}, order=ORDER):
                    pass
            self.assertIn('configuration', str(failure.exception))
            self.assertNotIn('SECRETISH', str(failure.exception))

    def test_sandbox_case_file_supplies_only_payment_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'case.json'
            path.write_text(json.dumps({'order': dict(ORDER, case_id='case-sandbox-1', currency='USD', age_days=30, quantity=1)}))
            self.assertEqual(sandbox_order(path), ORDER)


def fixture_image():
    import base64
    from evidence.backend.validation import ROOT
    raw = (ROOT / 'evidence' / 'evals' / 'fixtures' / 'blurred.png').read_bytes()
    return {'image_base64': base64.b64encode(raw).decode(), 'mime_type': 'image/png'}


if __name__ == '__main__':
    unittest.main()
