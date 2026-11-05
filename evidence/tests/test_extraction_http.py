import base64
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.backend.server import make_server
from evidence.backend.store import AssessmentStore
from test_assessment import encoded_image, fixture
from test_extraction import AdapterDouble
from test_resolution_client import RunningServer


class ExtractionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'db.sqlite3'
        self.runner = RunningServer(make_server(0, self.db))
        self.url = self.runner.__enter__()

    def tearDown(self):
        self.runner.__exit__()
        self.temp.cleanup()

    def call(self, path, body):
        request = Request(self.url + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def fixture_image(self, case_id):
        data = json.loads(DEFAULT_MANIFEST.read_text())
        case = next(row for row in data['cases'] if row['case_id'] == case_id)
        return {'image_base64': base64.b64encode((DEFAULT_MANIFEST.parent / case['image']).read_bytes()).decode(),
                'mime_type': case['mime_type']}

    def test_known_image_proposal_is_mock_and_does_not_persist_or_assess(self):
        status, result = self.call('/demo/image-extraction', self.fixture_image('clear-png'))
        self.assertEqual(status, 200)
        self.assertEqual((result['mode'], result['model'], result['batch']), ('mock', 'LAMP-100', 'B101'))
        self.assertNotIn('decision', result)
        self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))
        label = fixture()['label']
        label.update(confirmed_model=result['model'], confirmed_batch=result['batch'])
        status, assessment = self.call('/demo/assessments', {'label': label})
        self.assertEqual((status, assessment['mode'], assessment['decision']), (200, 'manual', 'eligible'))

    def test_conflict_keeps_batch_empty_and_returns_one_clarification(self):
        status, result = self.call('/demo/image-extraction', self.fixture_image('conflicting-batches'))
        self.assertEqual(status, 200)
        self.assertIsNone(result['batch'])
        self.assertEqual(result['uncertain_fields'], ['batch'])
        self.assertIn('batch', result['clarification'])

    def test_unknown_valid_image_is_visible_unavailable_and_not_a_fake_success(self):
        status, error = self.call('/demo/image-extraction', {'image_base64': encoded_image(), 'mime_type': 'image/png'})
        self.assertEqual(status, 503)
        self.assertIn('manually', error['error'])
        self.assertNotIn('model', error)
        self.assertIsNone(AssessmentStore(self.db).latest('case-demo-1'))

    def test_bad_extraction_inputs_are_400_without_proposals(self):
        for body in ({'image_base64': None, 'mime_type': None},
                     {'image_base64': 'bad', 'mime_type': 'image/png'},
                     dict(self.fixture_image('clear-png'), filename='clear-png.png'),
                     dict(self.fixture_image('clear-png'), mode='ai'), []):
            status, error = self.call('/demo/image-extraction', body)
            self.assertEqual(status, 400)
            self.assertNotIn('model', error)

    def test_ambiguous_content_length_and_incomplete_body_are_rejected(self):
        raw = json.dumps(fixture()).encode()
        port = int(self.url.rsplit(':', 1)[1])
        connection = HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            connection.putrequest('POST', '/v1/assessments')
            connection.putheader('Content-Type', 'application/json')
            connection.putheader('Content-Length', str(len(raw)))
            connection.putheader('Content-Length', str(len(raw) + 1))
            connection.endheaders(raw)
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 400)
        finally:
            connection.close()
        connection = HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            connection.request('POST', '/v1/assessments', raw, {'Content-Type': 'application/json', 'Content-Length': str(len(raw) + 1)})
            connection.sock.shutdown(1)
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 400)
        finally:
            connection.close()

    def test_adapter_failure_does_not_expose_exception_details(self):
        with RunningServer(make_server(0, Path(self.temp.name) / 'failure.sqlite3', extraction_adapter=AdapterDouble(error=TimeoutError('PRIVATE-SECRET')))) as url:
            old_url = self.url
            self.url = url
            try:
                status, error = self.call('/demo/image-extraction', self.fixture_image('clear-png'))
            finally:
                self.url = old_url
            self.assertEqual(status, 503)
            self.assertNotIn('PRIVATE-SECRET', json.dumps(error))
