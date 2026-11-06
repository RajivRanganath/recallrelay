from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import sqlite3
from unittest.mock import patch
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evidence.backend.server import make_server
from test_assessment import fixture
from test_resolution_client import RunningServer


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runner = RunningServer(make_server(0, Path(self.temp.name) / 'db.sqlite3', 'http://127.0.0.1:1'))
        self.url = self.runner.__enter__()

    def tearDown(self):
        self.runner.__exit__()
        self.temp.cleanup()

    def call(self, path, body=None, headers=None):
        headers = {'Content-Type': 'application/json', **(headers or {})}
        req = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_v1_post_read_and_unknown_case(self):
        status, saved = self.call('/v1/assessments', fixture())
        self.assertEqual(status, 200)
        self.assertEqual(self.call('/v1/assessments/case-demo-1'), (200, saved))
        self.assertEqual(self.call('/v1/assessments/unknown')[0], 404)

    def test_demo_only_accepts_label_and_uses_server_context(self):
        body = fixture()
        status, saved = self.call('/demo/assessments', {'label': body['label']})
        self.assertEqual(status, 200)
        self.assertEqual(saved['campaign_id'], 'campaign-demo-1')
        self.assertEqual(self.call('/demo/assessments', body)[0], 400)
        self.assertEqual(self.call('/demo/assessments', {'label': body['label'], 'approved': True})[0], 400)

    def test_mock_proposal_does_not_create_an_assessment(self):
        status, result = self.call('/demo/extraction', {'sample_id': 'blurred'})
        self.assertEqual((status, result['mode'], result['batch']), (200, 'mock', None))
        self.assertEqual(self.call('/v1/assessments/case-demo-1')[0], 404)
        self.assertEqual(self.call('/demo/extraction', {'sample_id': 'other'})[0], 400)

    def test_storage_failure_is_a_visible_503_for_reads_and_writes(self):
        with patch('evidence.backend.server.AssessmentStore.latest', side_effect=sqlite3.OperationalError('private details')):
            status, error = self.call('/v1/assessments/case-demo-1')
            self.assertEqual(status, 503)
            self.assertNotIn('private details', json.dumps(error))
        with patch('evidence.backend.server.AssessmentStore.save', side_effect=sqlite3.OperationalError('private details')):
            status, error = self.call('/v1/assessments', fixture())
            self.assertEqual(status, 503)
            self.assertNotIn('private details', json.dumps(error))

    def test_stale_snapshot_returns_conflict(self):
        body = fixture()
        self.call('/v1/assessments', body)
        body['campaign']['version'] = 0
        self.assertEqual(self.call('/v1/assessments', body)[0], 409)

    def test_provider_failure_does_not_become_success(self):
        status, body = self.call('/demo/resolution-status')
        self.assertEqual(status, 503)
        self.assertIn('error', body)
        self.assertNotIn('status', body)

    def test_cross_origin_host_and_content_type_are_rejected(self):
        for headers, code in [({'Origin': 'https://untrusted.example'}, 403),
                              ({'Host': 'untrusted.example'}, 403),
                              ({'Content-Type': 'text/plain'}, 400)]:
            with self.subTest(headers=headers):
                self.assertEqual(self.call('/v1/assessments', fixture(), headers)[0], code)

    def test_ambiguous_request_headers_are_rejected_without_persistence(self):
        raw = json.dumps(fixture()).encode()
        origin = self.url
        variants = [
            ([('Content-Type', 'application/json'), ('Content-Type', 'text/plain')], 400),
            ([('Content-Type', 'application/json'), ('Content-Type', 'application/json')], 400),
            ([('Origin', origin), ('Origin', 'https://untrusted.example')], 403),
            ([('Origin', '')], 403),
            ([('Transfer-Encoding', '')], 400),
            ([('Transfer-Encoding', ''), ('Transfer-Encoding', 'chunked')], 400),
        ]
        port = int(self.url.rsplit(':', 1)[1])
        for headers, expected in variants:
            with self.subTest(headers=headers):
                connection = HTTPConnection('127.0.0.1', port, timeout=3)
                try:
                    connection.putrequest('POST', '/v1/assessments')
                    if not any(name == 'Content-Type' for name, value in headers):
                        connection.putheader('Content-Type', 'application/json')
                    connection.putheader('Content-Length', str(len(raw)))
                    for name, value in headers:
                        connection.putheader(name, value)
                    connection.endheaders(raw)
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, expected)
                finally:
                    connection.close()
                self.assertEqual(self.call('/v1/assessments/case-demo-1')[0], 404)

    def test_bad_requests_do_not_echo_untrusted_values(self):
        body = fixture()
        body['secret'] = 'DO-NOT-ECHO-THIS'
        status, error = self.call('/v1/assessments', body)
        self.assertEqual(status, 400)
        self.assertNotIn('DO-NOT-ECHO-THIS', json.dumps(error))
        for invalid in ([], {'label': 'wrong-type'}, {'label': None}):
            self.assertEqual(self.call('/demo/assessments', invalid)[0], 400)

    def test_request_body_limit_and_malformed_json(self):
        port = int(self.url.rsplit(':', 1)[1])
        for data, length, expected in [(b'{', 1, 400), (b'', 4 * 1024 * 1024, 413)]:
            connection = HTTPConnection('127.0.0.1', port, timeout=3)
            connection.request('POST', '/v1/assessments', data, {'Content-Type': 'application/json', 'Content-Length': str(length)})
            response = connection.getresponse()
            self.assertEqual(response.status, expected)
            response.read()
            connection.close()

    def test_only_allowlisted_static_assets_are_served(self):
        for path in ('/', '/app.js', '/style.css'):
            with urlopen(self.url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.call('/../contracts/fixtures/assessment-request.json')[0], 404)
        self.assertEqual(self.call('/health')[1]['extraction_mode'], 'mock')
