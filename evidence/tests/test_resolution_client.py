import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
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
