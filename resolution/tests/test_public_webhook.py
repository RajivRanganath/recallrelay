"""The temporary public host (docs/vismaya/WEBHOOK-EXCEPTION.md) may reach the webhook POST and nothing else."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from resolution.backend.paypal import FakePayPal
from resolution.backend.refund import approve
from resolution.backend.review import review
from resolution.backend.server import PUBLIC_DENIED, make_server, public_host_name
from resolution.backend.store import CaseStore
from resolution.backend.validation import MAX_BODY_BYTES

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())
APPROVAL = {'assessment_id': 'assessment-demo-1', 'campaign_version': 1,
            'capture_id': 'capture-demo-NOT-PAYPAL', 'amount_minor': 4000, 'approved_by': 'merchant-demo'}
HOST = 'abc-def.example.com'
LOOPBACK_PATHS_GET = ('/', '/app.js', '/style.css', '/health', '/v1/cases', '/v1/cases/case-demo-1', '/v1/resolutions/case-demo-1')
LOOPBACK_PATHS_POST = ('/v1/resolutions', '/v1/demo/case', '/v1/cases/case-demo-1/approve', '/v1/cases/case-demo-1/reconcile',
                       '/v1/cases/case-demo-1/remedy-conditions', '/v1/cases/case-demo-1/brief')


class PublicWebhookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'cases.sqlite3'
        self.store = CaseStore(self.db)
        sent = copy.deepcopy(FIXTURE)
        sent['remedy_conditions_met'] = True
        self.store.save_review(sent, review(sent))
        self.adapter = FakePayPal(['lost'])  # The refund exists at the provider but our answer was lost: the case is pending.
        self.adapter.webhooks_valid = True
        self.pending = approve(self.store, self.adapter, 'case-demo-1', APPROVAL)
        self.refund_id = self.adapter.refunds[self.pending['operation_id']]
        self.event = {'event_type': 'PAYMENT.CAPTURE.REFUNDED', 'resource': {'id': self.refund_id, 'links': [
            {'rel': 'up', 'href': f'https://api.sandbox.paypal.com/v2/payments/captures/{APPROVAL["capture_id"]}'}]}}

    def serve(self, **options):
        options.setdefault('public_host', HOST)
        options.setdefault('webhook_id', 'WH-1')
        server = make_server(0, self.db, self.adapter, None, **options)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        self.port = server.server_port
        return server

    def call(self, method, path, host=HOST, body=None, headers=(), content_length=None, extra_hosts=()):
        data = b'' if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.putrequest(method, path, skip_host=True)
            for value in ([host] if host is not None else []) + list(extra_hosts):
                connection.putheader('Host', value)
            if method == 'POST':
                connection.putheader('Content-Type', 'application/json')
                connection.putheader('Content-Length', str(len(data) if content_length is None else content_length))
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders(data if method == 'POST' and content_length is None else None)
            response = connection.getresponse()
            return response.status, json.loads(response.read() or b'null')
        finally:
            connection.close()

    def assert_unchanged(self):
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')
        self.assertEqual(self.adapter.calls, 1)  # Only the initial approval ever reached the provider.

    def test_the_public_host_reaches_the_webhook_and_settles_a_matching_pending_case(self):
        self.serve()
        self.assertEqual(self.call('POST', '/v1/paypal/webhook', body=self.event), (200, {'accepted': True, 'settled': True}))
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'refunded')

    def test_every_other_request_on_the_public_host_is_refused_before_any_handler_runs(self):
        self.serve()
        for path in LOOPBACK_PATHS_GET:
            with self.subTest(method='GET', path=path):
                self.assertEqual(self.call('GET', path), (403, PUBLIC_DENIED))
        for path in LOOPBACK_PATHS_POST + ('/v1/paypal/webhook?x=1', '/v1/paypal/webhook/', '/V1/paypal/webhook',
                                           '/v1/paypal/webhook/../cases', '/v1/paypal/webhook%2f', '/v1/paypal/webhook#x',
                                           '/v1/paypal', '/v1/paypal/', '/v1/paypal/webhooks', '/v1/paypal/webhook;a=b'):
            with self.subTest(method='POST', path=path):
                self.assertEqual(self.call('POST', path, body=self.event), (403, PUBLIC_DENIED))
        self.assert_unchanged()

    def test_extra_leading_slashes_are_collapsed_by_the_http_library_and_still_reach_only_the_verified_webhook(self):
        # http.server turns '//v1/paypal/webhook' into '/v1/paypal/webhook'. It is the same single route, and an
        # event is still checked with PayPal before anything can change.
        self.adapter.webhooks_valid = False
        self.serve()
        for path in ('//v1/paypal/webhook', '///v1/paypal/webhook'):
            with self.subTest(path=path):
                self.assertEqual(self.call('POST', path, body=self.event), (401, {'error': 'Event could not be verified'}))
        self.assertEqual(self.call('POST', '//v1/cases/case-demo-1/approve', body=self.event), (403, PUBLIC_DENIED))
        self.assert_unchanged()

    def test_only_the_exact_host_is_treated_as_public_and_other_hosts_stay_refused(self):
        self.serve()
        for host in ('evil.example.com', f'{HOST}:443', f'{HOST}.evil.com', f'x{HOST}', 'example.com', 'localhost', '127.0.0.1', ''):
            with self.subTest(host=host):
                self.assertEqual(self.call('POST', '/v1/paypal/webhook', host=host, body=self.event), (403, {'error': 'Loopback Host required'}))
                self.assertEqual(self.call('GET', '/health', host=host), (403, {'error': 'Loopback Host required'}))
        for extra in ((HOST,), ('evil.example.com',)):  # Two Host headers are never trusted.
            with self.subTest(extra=extra):
                self.assertEqual(self.call('POST', '/v1/paypal/webhook', body=self.event, extra_hosts=extra)[0], 403)
        self.assert_unchanged()

    def test_host_names_are_case_insensitive_but_unverified_events_still_change_nothing(self):
        self.adapter.webhooks_valid = False
        self.serve()
        self.assertEqual(self.call('POST', '/v1/paypal/webhook', host=HOST.upper(), body=self.event), (401, {'error': 'Event could not be verified'}))
        self.assert_unchanged()

    def test_browser_style_cross_origin_requests_are_refused_even_on_the_webhook_path(self):
        self.serve()
        status, _ = self.call('POST', '/v1/paypal/webhook', body=self.event, headers=[('Origin', 'https://evil.example.com')])
        self.assertEqual(status, 403)
        self.assert_unchanged()

    def test_oversized_bodies_are_refused_without_being_read(self):
        self.serve()
        status, _ = self.call('POST', '/v1/paypal/webhook', body=b'', content_length=MAX_BODY_BYTES + 1)
        self.assertEqual(status, 400)
        self.assert_unchanged()

    def test_the_public_host_stops_working_when_the_window_closes_but_loopback_keeps_working(self):
        self.adapter.webhooks_valid = False
        self.serve(public_window_seconds=0.6)
        self.assertEqual(self.call('POST', '/v1/paypal/webhook', body=self.event)[0], 401)  # Window open: reaches the handler.
        time.sleep(0.8)
        self.assertEqual(self.call('POST', '/v1/paypal/webhook', body=self.event), (403, PUBLIC_DENIED))
        self.assertEqual(self.call('GET', '/health', host=f'127.0.0.1:{self.port}')[0], 200)  # The merchant UI is unaffected.
        self.assert_unchanged()

    def test_loopback_behaviour_is_unchanged_while_a_public_host_is_configured(self):
        self.serve()
        loopback = f'127.0.0.1:{self.port}'
        self.assertEqual(self.call('GET', '/health', host=loopback)[1]['service'], 'resolution')
        self.assertEqual(self.call('GET', '/v1/cases/case-demo-1', host=loopback)[0], 200)
        self.assertEqual(self.call('POST', '/v1/cases/case-demo-1/reconcile', host=loopback, body=b'')[1]['status'], 'refunded')

    def test_without_a_public_host_every_non_loopback_host_is_refused_as_before(self):
        self.serve(public_host=None, webhook_id='WH-1')
        for method, path in (('GET', '/health'), ('POST', '/v1/paypal/webhook')):
            with self.subTest(path=path):
                self.assertEqual(self.call(method, path, host=HOST, body=self.event), (403, {'error': 'Loopback Host required'}))
        self.assert_unchanged()

    def test_public_host_names_must_be_plain_dns_names(self):
        for bad in ('', ' ', 'localhost', '127.0.0.1', '1.2.3.4', '[::1]', 'a b.example.com', 'example.com:443', 'https://example.com',
                    'example.com/path', 'x.localhost', '-bad.example.com', 'bad-.example.com', 'a..example.com', 'example', 'example.c0m',
                    ('a' * 64) + '.example.com', 'a.' * 130 + 'com', 123, None, b'example.com'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                public_host_name(bad)
        self.assertEqual(public_host_name('  ABC-def.Example.COM '), 'abc-def.example.com')
        self.assertEqual(public_host_name('a1.b2.trycloudflare.com'), 'a1.b2.trycloudflare.com')

    def test_a_public_host_needs_a_webhook_id_a_verifying_adapter_and_a_short_window(self):
        with self.assertRaises(ValueError):
            make_server(0, self.db, self.adapter, None, webhook_id=None, public_host=HOST)
        with self.assertRaises(ValueError):
            make_server(0, self.db, type('NoVerify', (), {'mode': 'x'})(), None, webhook_id='WH-1', public_host=HOST)
        for window in (0, -1, 7201, 10 ** 9):
            with self.subTest(window=window), self.assertRaises(ValueError):
                make_server(0, self.db, self.adapter, None, webhook_id='WH-1', public_host=HOST, public_window_seconds=window)
        for bad_host in ('localhost', '127.0.0.1', 'example.com:443'):
            with self.subTest(host=bad_host), self.assertRaises(ValueError):
                make_server(0, self.db, self.adapter, None, webhook_id='WH-1', public_host=bad_host)


if __name__ == '__main__':
    unittest.main()
