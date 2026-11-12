"""The temporary public host (docs/resolution/WEBHOOK-EXCEPTION.md) may reach the webhook POST and nothing else."""
import copy
import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from resolution.backend.paypal import FakePayPal
from resolution.backend.refund import approve
from resolution.backend.review import review
from resolution.backend.server import MAX_PUBLIC_HANDLERS, PUBLIC_DENIED, make_server, public_host_name
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


class ReceiveBoundsTests(unittest.TestCase):
    """A sender that trickles bytes cannot hold a handler open, and connections are capped."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'cases.sqlite3'
        self.adapter = FakePayPal()
        self.adapter.webhooks_valid = True

    def serve(self, adapter=None, **options):
        server = make_server(0, self.db, adapter or self.adapter, None, **options)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=2)))
        return server.server_port

    @staticmethod
    def head(method, path, host, length):
        return (f'{method} {path} HTTP/1.1\r\nHost: {host}\r\nContent-Type: application/json\r\n'
                f'Content-Length: {length}\r\n\r\n').encode()

    def trickle(self, port, head, interval=0.3, limit=4.0):
        """Send `head`, then one body byte per interval. Returns (first reply bytes, b'' if closed, None if never), seconds."""
        connection = socket.create_connection(('127.0.0.1', port), timeout=5)
        start = time.monotonic()
        try:
            connection.sendall(head)
            while time.monotonic() - start < limit:
                try:
                    connection.sendall(b'x')
                except OSError:
                    return b'', time.monotonic() - start
                connection.settimeout(interval)
                try:
                    return connection.recv(200), time.monotonic() - start
                except socket.timeout:
                    continue
                except OSError:
                    return b'', time.monotonic() - start
            return None, time.monotonic() - start
        finally:
            connection.close()

    def test_a_public_request_is_rejected_from_its_headers_while_the_body_trickles(self):
        port = self.serve(public_host=HOST, webhook_id='WH-1', public_window_seconds=0.3)
        time.sleep(0.5)  # The public window is closed now.
        reply, seconds = self.trickle(port, self.head('POST', '/v1/paypal/webhook', HOST, 40))
        self.assertTrue(reply and reply.startswith(b'HTTP/1.0 403'), reply)
        self.assertLess(seconds, 1.0)  # Answered at once, not after the body (which never finishes) or a socket timeout.

    def test_a_public_request_to_any_other_path_is_rejected_without_waiting_for_its_body(self):
        port = self.serve(public_host=HOST, webhook_id='WH-1')
        for path in ('/v1/cases/case-demo-1/approve', '/v1/resolutions', '/v1/paypal/webhook?x=1'):
            with self.subTest(path=path):
                reply, seconds = self.trickle(port, self.head('POST', path, HOST, 40))
                self.assertTrue(reply and reply.startswith(b'HTTP/1.0 403'), reply)
                self.assertLess(seconds, 1.0)

    def test_the_whole_request_must_arrive_inside_the_receive_budget_not_just_each_byte(self):
        port = self.serve(receive_seconds=1.0)
        reply, seconds = self.trickle(port, self.head('POST', '/v1/resolutions', f'127.0.0.1:{port}', 100))
        self.assertTrue(reply and reply.startswith(b'HTTP/1.0 408'), reply)
        self.assertLess(seconds, 2.5)

    def test_slowly_trickled_headers_are_cut_off_by_the_same_budget(self):
        port = self.serve(receive_seconds=1.0)
        connection = socket.create_connection(('127.0.0.1', port), timeout=5)
        start = time.monotonic()
        ended = None
        try:
            connection.sendall(b'POST /v1/resolutions HTTP/1.1\r\n')
            while time.monotonic() - start < 4.0 and ended is None:
                try:
                    connection.sendall(b'X-A: b')  # Never finishes the header block.
                except OSError:
                    ended = time.monotonic() - start
                    break
                connection.settimeout(0.3)
                try:
                    connection.recv(200)
                    ended = time.monotonic() - start  # A reply or a close both end the wait.
                except socket.timeout:
                    pass
                except OSError:
                    ended = time.monotonic() - start
        finally:
            connection.close()
        self.assertIsNotNone(ended, 'the server kept waiting for headers')
        self.assertLess(ended, 2.5)

    def test_a_normal_request_still_works_with_a_short_budget(self):
        port = self.serve(receive_seconds=1.0)
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('GET', '/health')
        response = connection.getresponse()
        self.assertEqual((response.status, json.loads(response.read())['service']), (200, 'resolution'))
        connection.close()

    def test_connections_beyond_the_cap_are_closed_and_the_server_recovers_when_idle_ones_time_out(self):
        port = self.serve(max_connections=2, receive_seconds=1.0)
        idle = [socket.create_connection(('127.0.0.1', port), timeout=5) for _ in range(2)]  # Occupy both slots.
        try:
            time.sleep(0.2)
            third = socket.create_connection(('127.0.0.1', port), timeout=5)
            try:
                refused = False
                try:
                    third.sendall(f'GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n'.encode())
                    third.settimeout(1.0)
                    refused = third.recv(100) == b''  # Closed cleanly with no reply...
                except ConnectionError:
                    refused = True  # ...or reset (Windows may report it this way). Either way, no handler ran.
                self.assertTrue(refused, 'the extra connection was served or left waiting')
            finally:
                third.close()
            time.sleep(1.5)  # The idle connections used up their receive budget and were released.
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            connection.request('GET', '/health')
            self.assertEqual(connection.getresponse().status, 200)
            connection.close()
        finally:
            for sock in idle:
                sock.close()

    def test_only_a_few_public_webhook_calls_run_at_once_and_the_rest_are_told_to_retry(self):
        gate, entered = threading.Event(), threading.Semaphore(0)

        class Slow(FakePayPal):
            def verify_webhook(self, headers, raw, webhook_id):
                entered.release()
                gate.wait(5)
                return False

        port = self.serve(adapter=Slow(), public_host=HOST, webhook_id='WH-1')
        results = []

        def send():
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            connection.request('POST', '/v1/paypal/webhook', b'{}', {'Host': HOST, 'Content-Type': 'application/json'})
            results.append(connection.getresponse().status)
            connection.close()
        workers = [threading.Thread(target=send) for _ in range(MAX_PUBLIC_HANDLERS)]
        for worker in workers:
            worker.start()
        for _ in range(MAX_PUBLIC_HANDLERS):
            self.assertTrue(entered.acquire(timeout=5))  # All of them are inside the handler, waiting on PayPal.
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('POST', '/v1/paypal/webhook', b'{}', {'Host': HOST, 'Content-Type': 'application/json'})
        extra = connection.getresponse()
        self.assertEqual((extra.status, json.loads(extra.read())), (503, {'error': 'Busy; try again later'}))
        connection.close()
        gate.set()
        for worker in workers:
            worker.join(timeout=10)
        self.assertEqual(sorted(results), [401] * MAX_PUBLIC_HANDLERS)

    def seed(self, confirmed=False):
        store = CaseStore(self.db)
        sent = copy.deepcopy(FIXTURE)
        sent['remedy_conditions_met'] = confirmed
        store.save_review(sent, review(sent))
        return store

    def unfinished(self, port, request_head, wait=0.8):
        """Send a request whose header block never ends, wait past the receive budget, return the first reply bytes."""
        connection = socket.create_connection(('127.0.0.1', port), timeout=5)
        try:
            connection.sendall(request_head)
            time.sleep(wait)
            connection.settimeout(2)
            try:
                return connection.recv(200)
            except OSError:
                return b''
        finally:
            connection.close()

    def test_an_unfinished_request_cannot_confirm_the_remedy_after_its_deadline(self):
        store = self.seed()
        port = self.serve(receive_seconds=0.3)
        reply = self.unfinished(port, f'POST /v1/cases/case-demo-1/remedy-conditions HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'.encode())
        self.assertTrue(reply.startswith(b'HTTP/1.0 408'), reply)
        self.assertFalse(store.request('case-demo-1')['remedy_conditions_met'])  # Nothing was dispatched.

    def test_an_unfinished_request_cannot_start_a_refund_after_its_deadline(self):
        store = self.seed(confirmed=True)
        port = self.serve(receive_seconds=0.3)
        reply = self.unfinished(port, (f'POST /v1/cases/case-demo-1/approve HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                                       'Content-Type: application/json\r\n').encode())
        self.assertTrue(reply.startswith(b'HTTP/1.0 408'), reply)
        self.assertEqual((store.latest('case-demo-1')['status'], store.operation('case-demo-1'), self.adapter.calls),
                         ('awaiting_approval', None, 0))

    def test_an_unfinished_get_is_not_served_after_its_deadline(self):
        self.seed()
        port = self.serve(receive_seconds=0.3)
        reply = self.unfinished(port, f'GET /v1/cases HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'.encode())
        self.assertTrue(reply.startswith(b'HTTP/1.0 408'), reply)  # No case data goes out.

    def test_an_unfinished_public_webhook_request_never_reaches_verification(self):
        calls = []

        class Counting(FakePayPal):
            def verify_webhook(self, headers, raw, webhook_id):
                calls.append(1)
                return True

        port = self.serve(adapter=Counting(), public_host=HOST, webhook_id='WH-1', receive_seconds=0.3)
        reply = self.unfinished(port, f'POST /v1/paypal/webhook HTTP/1.1\r\nHost: {HOST}\r\nContent-Type: application/json\r\n'.encode())
        self.assertTrue(reply.startswith(b'HTTP/1.0 408'), reply)
        self.assertEqual(calls, [])

    def test_a_complete_request_is_still_dispatched_after_the_fix(self):
        store = self.seed()
        port = self.serve(receive_seconds=1.0)
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('POST', '/v1/cases/case-demo-1/remedy-conditions')
        self.assertEqual(connection.getresponse().status, 200)
        connection.close()
        self.assertTrue(store.request('case-demo-1')['remedy_conditions_met'])

    def test_the_new_limits_are_validated(self):
        for options in ({'receive_seconds': 0}, {'receive_seconds': 61}, {'receive_seconds': -1},
                        {'max_connections': 0}, {'max_connections': 257}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                make_server(0, self.db, self.adapter, None, **options)


if __name__ == '__main__':
    unittest.main()
