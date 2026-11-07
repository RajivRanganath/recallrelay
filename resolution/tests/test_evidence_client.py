import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

from resolution.backend.evidence_client import EvidenceClient, EvidenceUnavailable
from scripts.mock_server import make_server

ROOT = Path(__file__).resolve().parents[2]
REQUEST = json.loads((ROOT / 'contracts/fixtures/assessment-request.json').read_text())
RESPONSE = json.loads((ROOT / 'contracts/fixtures/assessment-response.json').read_text())


class Running:
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


def fake(code, body, content_type='application/json'):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


class EvidenceClientTests(unittest.TestCase):
    def test_frozen_evidence_mock_over_http(self):
        with Running(make_server('evidence', 0)) as url:
            result = EvidenceClient(url).assess(REQUEST)
        self.assertEqual((result['mode'], result['decision'], result['case_id']), ('mock', 'eligible', 'case-demo-1'))

    def test_bad_responses_and_upstream_errors_are_visible(self):
        wrong_case = json.dumps(dict(RESPONSE, case_id='other-case')).encode()
        cases = [(503, b'{"error":"down"}', 'application/json'), (200, b'not json', 'application/json'),
                 (200, b'{}', 'application/json'), (200, wrong_case, 'application/json'),
                 (200, json.dumps(RESPONSE).encode(), 'text/plain')]
        for code, body, content_type in cases:
            with self.subTest(code=code, body=body[:12]), Running(fake(code, body, content_type)) as url:
                with self.assertRaises(EvidenceUnavailable):
                    EvidenceClient(url).assess(REQUEST)

    def test_unreachable_service_and_invalid_request(self):
        with Running(fake(200, b'{}')) as url:
            pass  # Server is closed now, so the port refuses connections.
        with self.assertRaises(EvidenceUnavailable):
            EvidenceClient(url, timeout=1).assess(REQUEST)
        with self.assertRaises(Exception):
            EvidenceClient('http://user:pw@127.0.0.1:1')
        bad = copy.deepcopy(REQUEST)
        del bad['order']
        with self.assertRaises(Exception):
            EvidenceClient('http://127.0.0.1:1').assess(bad)


if __name__ == '__main__':
    unittest.main()
