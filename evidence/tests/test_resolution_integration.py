"""Customer HTTP boundary against frozen mocks and explicit synthetic failures."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evidence.backend.server import make_server
from scripts.mock_server import make_server as make_mock
from test_assessment import fixture
from test_resolution_client import ROOT, RunningServer


def call(url, path, body=None):
    request = Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json'})
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


class ResolutionIntegrationTests(unittest.TestCase):
    def test_customer_status_reads_frozen_mock_without_creating_or_changing_assessment(self):
        with tempfile.TemporaryDirectory() as folder, RunningServer(make_mock('resolution', 0)) as upstream:
            with RunningServer(make_server(0, Path(folder) / 'db.sqlite3', upstream)) as customer:
                status, before = call(customer, '/demo/resolution-status')
                self.assertEqual((status, before['mode'], before['status']), (200, 'mock', 'awaiting_approval'))
                self.assertEqual(call(customer, '/v1/assessments/case-demo-1')[0], 404)
                status, saved = call(customer, '/demo/assessments', {'label': fixture()['label']})
                self.assertEqual((status, saved['mode'], saved['decision']), (200, 'manual', 'eligible'))
                self.assertEqual(call(customer, '/demo/resolution-status'), (200, before))
                self.assertEqual(call(customer, '/v1/assessments/case-demo-1'), (200, saved))

    def test_frozen_status_values_are_relayed_without_payment_or_persistence(self):
        data = json.loads((ROOT / 'contracts/fixtures/resolution-response.json').read_text())
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests.append(('GET', self.path))
                raw = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_POST(self):
                requests.append(('POST', self.path))
                self.send_response(405)
                self.end_headers()
        statuses = ('needs_information', 'awaiting_approval', 'pending', 'refunded',
                    'failed', 'manual_required', 'excluded')
        with tempfile.TemporaryDirectory() as folder, RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as upstream:
            with RunningServer(make_server(0, Path(folder) / 'db.sqlite3', upstream)) as customer:
                for status in statuses:
                    # Authored responses only, including the refunded state. No provider runs.
                    data['status'] = status
                    with self.subTest(status=status):
                        self.assertEqual(call(customer, '/demo/resolution-status'), (200, data))
                        self.assertEqual(call(customer, '/v1/assessments/case-demo-1')[0], 404)
        self.assertEqual(requests, [('GET', '/v1/resolutions/case-demo-1')] * len(statuses))

    def test_dependency_errors_remain_visible_and_manual_assessment_still_works(self):
        data = json.loads((ROOT / 'contracts/fixtures/resolution-response.json').read_text())
        reply = [404, b'{"error":"private-upstream-details"}']
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests.append(('GET', self.path))
                self.send_response(reply[0])
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(reply[1])))
                self.end_headers()
                self.wfile.write(reply[1])
        variants = [(404, reply[1], 404), (503, reply[1], 503),
                    (200, b'not-json private-upstream-details', 503),
                    (200, json.dumps(dict(data, case_id='wrong-case')).encode(), 503)]
        with tempfile.TemporaryDirectory() as folder, RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as upstream:
            with RunningServer(make_server(0, Path(folder) / 'db.sqlite3', upstream)) as customer:
                for code, raw, expected in variants:
                    reply[:] = [code, raw]
                    with self.subTest(code=code, expected=expected):
                        status, error = call(customer, '/demo/resolution-status')
                        self.assertEqual(status, expected)
                        self.assertIn('error', error)
                        self.assertNotIn('status', error)
                        self.assertNotIn('private-upstream-details', json.dumps(error))
                        status, saved = call(customer, '/demo/assessments', {'label': fixture()['label']})
                        self.assertEqual((status, saved['decision']), (200, 'eligible'))
                        self.assertEqual(call(customer, '/v1/assessments/case-demo-1'), (200, saved))
        self.assertEqual(requests, [('GET', '/v1/resolutions/case-demo-1')] * len(variants))
