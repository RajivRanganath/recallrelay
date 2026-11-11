"""Loopback regressions for receive deadlines, admission and capacity recovery."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection, HTTPResponse, IncompleteRead, RemoteDisconnected
import errno
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from evidence.backend.server import make_server
from evidence.backend.store import AssessmentStore
from evidence.backend.http_server import IntakeDeadline
from test_assessment import fixture
from test_resolution_client import RunningServer


class RequestLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'db.sqlite3'

    def call(self, server, path='/health', body=None):
        connection = HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request('GET' if body is None else 'POST', path,
                               None if body is None else json.dumps(body).encode(),
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def buffered_post(self, server, body):
        # Send the entire request in one write. Admission occurs before parsing;
        # split writers may instead see a connection error during overload.
        raw = json.dumps(body).encode()
        headers = (f'POST /v1/assessments HTTP/1.0\r\n'
                   f'Host: 127.0.0.1:{server.server_port}\r\n'
                   f'Content-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n').encode()
        with socket.create_connection(server.server_address, timeout=2) as peer:
            try:
                peer.sendall(headers + raw)
                with HTTPResponse(peer) as response:
                    response.begin()
                    return response.status, json.loads(response.read())
            except (ConnectionResetError, ConnectionAbortedError, RemoteDisconnected, IncompleteRead):
                return None, {}  # Overload may close without delivering its best-effort 503.

    def slow_request(self, server, prefix):
        # Keep supplying data well inside the inactivity timeout. The receive
        # deadline must wake the reader while the writer is still trickling.
        stop = threading.Event()
        sent = []
        with socket.create_connection(server.server_address, timeout=2) as peer:
            peer.sendall(prefix)
            def write():
                while not stop.wait(.03):
                    try:
                        peer.sendall(b' ')
                        sent.append(1)
                    except OSError:
                        return
            thread = threading.Thread(target=write)
            start = time.monotonic()
            thread.start()
            status, raw = None, b''
            try:
                with HTTPResponse(peer) as response:
                    response.begin()
                    status = response.status
                    raw = response.read()
            except (ConnectionResetError, ConnectionAbortedError, RemoteDisconnected, IncompleteRead):
                pass  # Closing an actively uploading peer can reset the socket.
            finally:
                stop.set()
                thread.join(1)
            self.assertFalse(thread.is_alive())
            self.assertGreaterEqual(len(sent), 2)
            self.assertGreater(time.monotonic() - start, .2)
            self.assertLess(time.monotonic() - start, 1.5)
            return status, raw

    def assert_recovers_without_assessment(self, server):
        # The response can precede handler cleanup by a few instructions.
        end = time.monotonic() + 1
        status, body = None, {}
        while True:
            try:
                status, body = self.call(server)
            except (ConnectionResetError, ConnectionAbortedError, RemoteDisconnected, IncompleteRead):
                status, body = None, {}
            if status == 200 or time.monotonic() >= end:
                break
            time.sleep(.01)
        self.assertEqual(status, 200)
        self.assertEqual(body['service'], 'evidence')
        self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))

    def test_trickling_headers_expire_and_release_capacity(self):
        server = make_server(0, self.db, max_handlers=1, request_timeout=.3)
        prefix = (f'POST /v1/assessments HTTP/1.0\r\n'
                  f'Host: 127.0.0.1:{server.server_port}\r\nX-Slow: ').encode()
        with RunningServer(server):
            status, raw = self.slow_request(server, prefix)
            self.assertIn(status, (408, None))
            if raw:
                self.assertIn(b'deadline', raw)
            self.assert_recovers_without_assessment(server)

    def test_trickling_body_expires_without_persistence(self):
        server = make_server(0, self.db, max_handlers=1, request_timeout=.3)
        prefix = (f'POST /v1/assessments HTTP/1.0\r\n'
                  f'Host: 127.0.0.1:{server.server_port}\r\n'
                  'Content-Type: application/json\r\nContent-Length: 10000\r\n\r\n{').encode()
        with RunningServer(server):
            self.assertIn(self.slow_request(server, prefix)[0], (408, None))
            self.assert_recovers_without_assessment(server)

    def test_request_line_is_also_inside_receive_budget(self):
        server = make_server(0, self.db, max_handlers=1, request_timeout=.3)
        with RunningServer(server):
            self.assertIn(self.slow_request(server, b'POST /v1/assessments HTTP/1.0')[0], (400, 408, None))
            self.assert_recovers_without_assessment(server)

    def test_headers_and_body_share_one_receive_budget(self):
        server = make_server(0, self.db, max_handlers=1, request_timeout=.5)
        with RunningServer(server), socket.create_connection(server.server_address, timeout=2) as peer:
            peer.sendall((f'POST /v1/assessments HTTP/1.0\r\n'
                          f'Host: 127.0.0.1:{server.server_port}\r\n').encode())
            time.sleep(.3)
            peer.sendall(b'Content-Type: application/json\r\nContent-Length: 10000\r\n\r\n{')
            start = time.monotonic()
            with HTTPResponse(peer) as response:
                response.begin()
                response.read()
                self.assertEqual(response.status, 408)
            self.assertLess(time.monotonic() - start, .4)
            self.assert_recovers_without_assessment(server)

    def test_excess_connections_get_503_without_running_application_work(self):
        entered = threading.Barrier(3)
        release = threading.Event()
        calls = []
        original = AssessmentStore.save
        def save(store, request, response):
            calls.append(request)
            entered.wait(3)
            if not release.wait(3):
                raise AssertionError('Test did not release accepted work')
            return original(store, request, response)
        server = make_server(0, self.db, max_handlers=2, request_timeout=.15)
        with RunningServer(server), patch.object(AssessmentStore, 'save', save):
            with ThreadPoolExecutor(max_workers=2) as pool:
                accepted = [pool.submit(self.call, server, '/v1/assessments', fixture()) for _ in range(2)]
                try:
                    entered.wait(3)
                    for _ in range(4):
                        status, body = self.buffered_post(server, fixture())
                        self.assertIn(status, (503, None))
                        if status == 503:
                            self.assertIn('busy', body['error'])
                        self.assertNotIn('assessment_id', body)
                    self.assertEqual(len(calls), 2)
                    self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))
                    # Receiving finished. A later watchdog must not disconnect
                    # admitted storage/provider work or imply it was rolled back.
                    time.sleep(.3)
                finally:
                    release.set()
                results = [future.result(timeout=3) for future in accepted]
            self.assertEqual([result[0] for result in results], [200, 200])
            self.assertEqual(results[0][1], results[1][1])
            self.assertEqual(self.call(server)[0], 200)

    def test_capacity_recovers_after_rejected_and_disconnected_requests(self):
        server = make_server(0, self.db, max_handlers=1, request_timeout=.3)
        with RunningServer(server):
            self.assertEqual(self.call(server, '/demo/assessments', {})[0], 400)
            self.assert_recovers_without_assessment(server)
            with socket.create_connection(server.server_address, timeout=2) as peer:
                peer.sendall(b'POST /v1/assessments HTTP/1.0\r\n')
                try:
                    peer.shutdown(socket.SHUT_RDWR)
                except OSError as error:
                    # The receive watchdog or rejected-request cleanup can
                    # disconnect this peer before the local shutdown call.
                    if error.errno != errno.ENOTCONN:
                        raise
            self.assert_recovers_without_assessment(server)
            status, saved = self.call(server, '/v1/assessments', fixture())
            self.assertEqual((status, saved['decision']), (200, 'eligible'))

    def test_server_close_joins_admitted_incomplete_request(self):
        server = make_server(0, self.db, request_timeout=.3)
        with socket.create_connection(server.server_address, timeout=2) as peer:
            peer.sendall(b'POST /v1/assessments HTTP/1.0')
            server.handle_request()
            start = time.monotonic()
            server.server_close()
            elapsed = time.monotonic() - start
            self.assertGreater(elapsed, .1)
            self.assertLess(elapsed, 1.5)
            try:
                raw = peer.recv(4096)
            except (ConnectionResetError, ConnectionAbortedError):
                raw = b''
            # With an incomplete request Windows may close/reset without a
            # response. Preserve the deadline bounds above; any HTTP reply
            # must still be 408, and the request must never reach persistence.
            if raw:
                self.assertTrue(raw.startswith(b'HTTP/1.0 408'), raw)
            self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))

    def test_deadline_still_bounds_reads_when_shutdown_does_not_wake_recv(self):
        def expire_without_shutdown(deadline):
            with deadline._lock:
                if not deadline._done:
                    deadline._expired = True
        with patch.object(IntakeDeadline, '_expire', expire_without_shutdown):
            self.test_server_close_joins_admitted_incomplete_request()

    def assert_closed(self, peer):
        try:
            self.assertEqual(peer.recv(4096), b'')
        except (ConnectionResetError, ConnectionAbortedError):
            pass

    def test_overload_formats_503_without_admitting_a_handler(self):
        class Peer:
            def __init__(self):
                self.sent = b''
                self.closed = False
            def settimeout(self, value):
                self.timeout = value
            def sendall(self, raw):
                self.sent += raw
            def shutdown(self, how):
                pass
            def close(self):
                self.closed = True
        server = make_server(0, self.db, max_handlers=1)
        peer = Peer()
        self.assertTrue(server._slots.acquire(blocking=False))
        try:
            with patch.object(server, 'finish_request') as work:
                server.process_request(peer, ('127.0.0.1', 1))
                work.assert_not_called()
            self.assertTrue(peer.sent.startswith(b'HTTP/1.0 503'))
            self.assertIn(b'busy', peer.sent)
            self.assertTrue(peer.closed)
            self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))
        finally:
            server._slots.release()
            server.server_close()

    def test_worker_start_failure_still_allows_clean_shutdown(self):
        server = make_server(0, self.db, max_handlers=1)
        self.addCleanup(server.server_close)
        with socket.create_connection(server.server_address, timeout=2) as peer:
            peer.sendall(b'GET /health HTTP/1.0\r\n\r\n')
            with patch('evidence.backend.http_server.threading.Thread.start', side_effect=RuntimeError('synthetic start failure')):
                with patch.object(server, 'handle_error') as errors:
                    server.handle_request()
                    errors.assert_called_once()
            self.assert_closed(peer)
        server.server_close()

    def test_worker_start_failure_releases_admission_capacity(self):
        server = make_server(0, self.db, max_handlers=1)
        with socket.create_connection(server.server_address, timeout=2) as peer:
            peer.sendall(b'GET /health HTTP/1.0\r\n\r\n')
            with patch('evidence.backend.http_server.threading.Thread.start', side_effect=RuntimeError('synthetic start failure')):
                with patch.object(server, 'handle_error'):
                    server.handle_request()
            self.assert_closed(peer)
        with RunningServer(server):
            self.assertEqual(self.call(server)[0], 200)
