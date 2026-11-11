"""Bounded synthetic review POSTs; no approval endpoints or automatic retries."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
import unittest

from evidence.backend.assessment import assess
from evidence.backend.resolution_client import ResolutionClient, ResolutionConflict, ResolutionUnavailable
from test_assessment import fixture
from test_resolution_client import RunningServer

ROOT = Path(__file__).resolve().parents[2]


class HandoffClientTests(unittest.TestCase):
    def test_explicit_review_payload_and_sanitized_upstream_failures(self):
        request = fixture()
        assessment = assess(request)
        response = json.loads((ROOT / 'contracts/fixtures/resolution-response.json').read_text())
        cases = [(200, response, 'application/json', None),
                 (409, {'error': 'private-upstream'}, 'application/json', ResolutionConflict),
                 (503, {'error': 'private-upstream'}, 'application/json', ResolutionUnavailable),
                 (200, dict(response, case_id='wrong-case'), 'application/json', ResolutionUnavailable),
                 (200, response, 'text/html', ResolutionUnavailable),
                 (302, response, 'application/json', ResolutionUnavailable)]
        for code, output, content_type, error_type in cases:
            received = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_POST(self):
                    received.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                    raw = json.dumps(output).encode()
                    self.send_response(code)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(raw)))
                    self.send_header('Location', 'http://127.0.0.1:1/do-not-follow')
                    self.end_headers()
                    self.wfile.write(raw)
            with self.subTest(code=code, content_type=content_type), RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                client = ResolutionClient(url)
                if error_type:
                    with self.assertRaises(error_type) as failure:
                        client.handoff(request['order'], assessment)
                    self.assertNotIn('private-upstream', str(failure.exception))
                else:
                    self.assertEqual(client.handoff(request['order'], assessment), response)
                self.assertEqual(received, [('/v1/resolutions', {
                    'schema_version': '1.0', 'order': request['order'], 'assessment': assessment,
                    'remedy_conditions_met': False})])

    def test_total_wait_is_bounded_and_request_is_not_retried(self):
        request = fixture()
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                received.append(self.path)
                try:
                    for byte in b'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n':
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(.04)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
            start = time.monotonic()
            with self.assertRaises(ResolutionUnavailable):
                ResolutionClient(url, timeout=.8).handoff(request['order'], assess(request))
            self.assertLess(time.monotonic() - start, 2.5)
            self.assertEqual(received, ['/v1/resolutions'])

    def test_remote_service_and_invalid_saved_snapshot_fail_before_network(self):
        request = fixture()
        for origin in ('https://example.com', 'https://localhost:8102'):
            with self.assertRaises(ResolutionUnavailable):
                ResolutionClient(origin).handoff(request['order'], assess(request))
        bad = copy.deepcopy(assess(request))
        bad['unexpected'] = 'not-part-of-contract'
        with self.assertRaises(ResolutionUnavailable):
            ResolutionClient('http://127.0.0.1:1').handoff(request['order'], bad)
