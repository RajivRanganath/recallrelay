"""Adversarial cases identified in the second-pass review."""
import base64
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import unittest

from evidence.backend.assessment import assess
from evidence.backend.resolution_client import ResolutionClient, ResolutionUnavailable
from evidence.backend.server import make_server
from evidence.backend.validation import InvalidInput
from test_assessment import fixture
from test_resolution_client import RunningServer

ROOT = Path(__file__).resolve().parents[2]


class CriticalRegressions(unittest.TestCase):
    def test_image_header_without_decodable_pixels_is_rejected(self):
        body = fixture()
        body['label'].update(image_base64=base64.b64encode(b'\x89PNG\r\n\x1a\nnot-an-image').decode(), mime_type='image/png')
        with self.assertRaises(InvalidInput):
            assess(body)

    def test_duplicate_json_keys_are_rejected_over_http(self):
        raw = json.dumps(fixture()).replace('"schema_version": "1.0"', '"schema_version": "2.0", "schema_version": "1.0"').encode()
        with tempfile.TemporaryDirectory() as directory:
            with RunningServer(make_server(0, Path(directory) / 'db.sqlite3')) as url:
                connection = HTTPConnection('127.0.0.1', int(url.rsplit(':', 1)[1]), timeout=3)
                try:
                    connection.request('POST', '/v1/assessments', raw, {'Content-Type': 'application/json'})
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 400)
                finally:
                    connection.close()

    def test_truncated_resolution_response_is_a_visible_dependency_error(self):
        data = (ROOT / 'contracts/fixtures/resolution-response.json').read_bytes()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data) + 1000))
                self.end_headers()
                self.wfile.write(data)
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
            with self.assertRaises(ResolutionUnavailable):
                ResolutionClient(url).get_status('case-demo-1')

    def test_partial_http_success_cannot_be_treated_as_a_full_status(self):
        data = (ROOT / 'contracts/fixtures/resolution-response.json').read_bytes()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(206)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(data)
        with RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
            with self.assertRaises(ResolutionUnavailable):
                ResolutionClient(url).get_status('case-demo-1')
