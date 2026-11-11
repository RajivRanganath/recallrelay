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

    def test_recovery_checks_bound_snapshot_and_never_reposts_on_read_errors(self):
        request = fixture()
        saved = assess(request)
        resolution = json.loads((ROOT / 'contracts/fixtures/resolution-response.json').read_text())
        summary_fields = ('assessment_id', 'decision', 'model', 'batch', 'reason', 'evidence', 'mode', 'missing_fields', 'clarification')
        order_fields = ('order_id', 'paid_minor', 'previously_refunded_minor', 'age_days', 'quantity')
        detail = {'resolution': resolution, 'assessment': {key: saved[key] for key in summary_fields},
                  'binding': {'assessment_id': saved['assessment_id'], 'campaign_version': saved['campaign_version'],
                              'capture_id': request['order']['capture_id'], 'currency': request['order']['currency']},
                  'order': {key: request['order'][key] for key in order_fields}}
        bad_capture = copy.deepcopy(detail)
        bad_capture['binding']['capture_id'] = 'wrong-capture'
        bad_identity = copy.deepcopy(detail)
        bad_identity['binding']['assessment_id'] = 'wrong-assessment'
        wrong_case = copy.deepcopy(detail)
        wrong_case['resolution']['case_id'] = 'wrong-case'
        for code, output, succeeds in [(200, detail, True), (200, bad_capture, False),
                                       (200, bad_identity, False), (200, wrong_case, False),
                                       (200, {}, False), (503, {}, False)]:
            received = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    received.append(('GET', self.path))
                    raw = json.dumps(output).encode()
                    self.send_response(code)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                def do_POST(self):
                    received.append(('POST', self.path))
                    self.send_error(500)
            with self.subTest(code=code, succeeds=succeeds), RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
                if succeeds:
                    self.assertEqual(ResolutionClient(url).handoff_if_needed(request['order'], saved), resolution)
                else:
                    with self.assertRaises(ResolutionUnavailable):
                        ResolutionClient(url).handoff_if_needed(request['order'], saved)
                self.assertEqual(received, [('GET', '/v1/cases/case-demo-1')])
