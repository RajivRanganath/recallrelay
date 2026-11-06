import json
import multiprocessing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest

from evidence.backend.resolution_client import ResolutionClient, ResolutionNotFound, ResolutionUnavailable
from scripts.mock_server import make_server

ROOT = Path(__file__).resolve().parents[2]


class RunningServer:
    def __init__(self, server):
        self.server = server

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f'http://127.0.0.1:{self.server.server_port}'

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ResolutionClientTests(unittest.TestCase):
    def test_frozen_resolution_mock_over_http(self):
        with RunningServer(make_server('resolution', 0)) as url:
            result = ResolutionClient(url).get_status('case-demo-1')
            self.assertEqual((result['mode'], result['status']), ('mock', 'awaiting_approval'))
            with self.assertRaises(ResolutionNotFound):
                ResolutionClient(url).get_status('unknown')

    def test_bad_response_modes_and_upstream_errors_are_visible(self):
        fixture = json.loads((ROOT / 'contracts/fixtures/resolution-response.json').read_text())
        wrong_case = dict(fixture, case_id='other-case')
        cases = [(503, b'{"error":"unavailable"}', 'application/json'),
                 (200, b'not json', 'application/json'), (200, b'{}', 'application/json'),
                 (200, json.dumps(wrong_case).encode(), 'application/json'),
                 (200, json.dumps(fixture).encode(), 'text/html'),
                 (200, b'x' * 65537, 'application/json'),
                 (302, b'', 'application/json')]
        for code, raw, content_type in cases:
            with self.subTest(code=code, content_type=content_type, size=len(raw)):
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass
                    def do_GET(self):
                        self.send_response(code)
                        self.send_header('Content-Type', content_type)
                        self.send_header('Location', 'http://127.0.0.1:1/should-not-follow')
                        self.end_headers()
                        self.wfile.write(raw)
                    def do_POST(self):
                        raise AssertionError('Status client must never POST')
                with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                    with self.assertRaises(ResolutionUnavailable):
                        ResolutionClient(url).get_status('case-demo-1')

    def test_timeout_and_connection_failure(self):
        event = threading.Event()
        class SlowHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                event.wait(1)
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), SlowHandler)) as url:
            with self.assertRaises(ResolutionUnavailable):
                ResolutionClient(url, timeout=.05).get_status('case-demo-1')
            event.set()
        with self.assertRaises(ResolutionUnavailable):
            ResolutionClient(url, timeout=.05).get_status('case-demo-1')

    def test_url_configuration_rejects_credentials_and_paths(self):
        for url in ('file:///etc/passwd', 'http://user:secret@localhost', 'http://localhost/path', 'http://localhost?token=x'):
            with self.assertRaises(ValueError):
                ResolutionClient(url)

    def test_case_identifier_is_encoded_as_one_path_segment(self):
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                paths.append(self.path)
                self.send_response(404)
                self.end_headers()
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
            with self.assertRaises(ResolutionNotFound):
                ResolutionClient(url).get_status('a/b?secret=x')
        self.assertEqual(paths, ['/v1/resolutions/a%2Fb%3Fsecret%3Dx'])

    def test_timeout_configuration_is_finite_positive_and_bounded(self):
        for timeout in (0, -1, True, float('nan'), float('inf'), 36, '2'):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                ResolutionClient('http://127.0.0.1:8102', timeout=timeout)
        with self.assertRaises(ValueError):
            ResolutionClient('http://127.0.0.1:invalid')

    def test_ambiguous_http_framing_is_rejected_without_retry(self):
        data = (ROOT / 'contracts/fixtures/resolution-response.json').read_bytes()
        variants = [
            [('Content-Length', str(len(data))), ('Content-Length', str(len(data)))],
            [('Content-Length', str(len(data))), ('Transfer-Encoding', 'chunked')],
            [('Transfer-Encoding', 'gzip')],
            [('Transfer-Encoding', 'chunked'), ('Transfer-Encoding', 'chunked')],
            [('Content-Length', '+123')], [('Content-Length', '0')],
            [('Content-Length', '65537')], [('Content-Length', '123, 123')],
            [('Content-Type', 'text/html')],
        ]
        for headers in variants:
            paths = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    paths.append(self.path)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    for name, value in headers:
                        self.send_header(name, value)
                    self.end_headers()
                    self.wfile.write(data)
            with self.subTest(headers=headers), RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                with self.assertRaises(ResolutionUnavailable):
                    ResolutionClient(url).get_status('case-demo-1')
                self.assertEqual(paths, ['/v1/resolutions/case-demo-1'])

    def test_unambiguous_chunked_and_connection_delimited_responses_work(self):
        data = (ROOT / 'contracts/fixtures/resolution-response.json').read_bytes()
        for chunked in (False, True):
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    if chunked:
                        self.send_header('Transfer-Encoding', 'chunked')
                    self.end_headers()
                    if chunked:
                        self.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n0\r\n\r\n')
                    else:
                        self.wfile.write(data)
            with self.subTest(chunked=chunked), RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                self.assertEqual(ResolutionClient(url).get_status('case-demo-1'), json.loads(data))

    def test_trickling_headers_and_body_are_bounded_and_workers_reaped(self):
        data = (ROOT / 'contracts/fixtures/resolution-response.json').read_bytes()
        headers = (b'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: '
                   + str(len(data)).encode() + b'\r\n\r\n')
        before = {child.pid for child in multiprocessing.active_children()}
        for drip_headers in (False, True):
            started = threading.Event()
            paths = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    paths.append(self.path)
                    started.set()
                    try:
                        if not drip_headers:
                            self.wfile.write(headers)
                            self.wfile.flush()
                        slow = headers if drip_headers else data
                        for byte in slow[:60]:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(.04)
                        self.wfile.write(slow[60:] + (data if drip_headers else b''))
                    except (BrokenPipeError, ConnectionResetError):
                        pass
            with self.subTest(drip_headers=drip_headers), RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                client = ResolutionClient(url, timeout=.8)
                start = time.monotonic()
                with self.assertRaises(ResolutionUnavailable):
                    client.get_status('case-demo-1')
                self.assertLess(time.monotonic() - start, 1.8)
                self.assertTrue(started.is_set())
                self.assertEqual(paths, ['/v1/resolutions/case-demo-1'])
                self.assertEqual({child.pid for child in multiprocessing.active_children()}, before)
                # Cancellation releases capacity; a later normal call can succeed.
                with RunningServer(make_server('resolution', 0)) as healthy_url:
                    client.base_url = healthy_url
                    self.assertEqual(client.get_status('case-demo-1')['mode'], 'mock')

    def test_saturation_returns_visible_failure_without_upstream_calls(self):
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                paths.append(self.path)
                self.send_response(404)
                self.end_headers()
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
            client = ResolutionClient(url)
            client._slots.acquire()
            client._slots.acquire()
            try:
                start = time.monotonic()
                with self.assertRaises(ResolutionUnavailable):
                    client.get_status('case-demo-1')
                self.assertLess(time.monotonic() - start, .2)
                self.assertEqual(paths, [])
            finally:
                client._slots.release()
                client._slots.release()
            with self.assertRaises(ResolutionNotFound):
                client.get_status('case-demo-1')
