import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from resolution.backend.server import make_server
from resolution.backend.store import CaseStore
from resolution.backend.validation import validate_contract

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'cases.sqlite3'
        self.server = make_server(0, self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def call(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = Request(self.url + path, data=data, method=method, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def eligible(self):
        data = copy.deepcopy(FIXTURE)
        data['remedy_conditions_met'] = True
        return data

    def test_post_then_get_returns_the_same_review(self):
        code, posted = self.call('POST', '/v1/resolutions', self.eligible())
        self.assertEqual((code, posted['status']), (200, 'awaiting_approval'))
        validate_contract('resolution-response', posted)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1'), (200, posted))
        self.assertEqual(self.call('POST', '/v1/resolutions', self.eligible()), (200, posted))

    def test_get_unknown_case_is_404_and_never_creates_one(self):
        self.assertEqual(self.call('GET', '/v1/resolutions/unknown')[0], 404)
        self.assertEqual(self.call('GET', '/v1/resolutions/unknown')[0], 404)

    def test_invalid_bodies_are_rejected_without_echoing_input(self):
        bad = self.eligible()
        bad['order']['paid_minor'] = 'SECRET-VALUE'
        for raw in (json.dumps(bad).encode(), b'not json', b'{"a":1,"a":2}', b'{}'):
            code, body = self.call('POST', '/v1/resolutions', raw=raw)
            self.assertEqual(code, 400)
            self.assertNotIn('SECRET-VALUE', json.dumps(body))

    def test_unknown_route_is_404(self):
        self.assertEqual(self.call('POST', '/v1/other', self.eligible())[0], 404)

    def test_review_cannot_overwrite_a_refund_in_progress(self):
        pending = {'schema_version': '1.0', 'case_id': 'case-demo-1', 'status': 'pending', 'brief': 'x',
                   'citations': [], 'proposed_amount_minor': 4000, 'currency': 'USD', 'refund_id': None,
                   'operation_id': 'operation-1', 'mode': 'sandbox'}
        with CaseStore(self.db).connect() as db:
            db.execute('INSERT INTO cases(case_id,status,response) VALUES(?,?,?)', ('case-demo-1', 'pending', json.dumps(pending)))
        self.assertEqual(self.call('POST', '/v1/resolutions', self.eligible())[0], 409)
        self.assertEqual(self.call('GET', '/v1/resolutions/case-demo-1'), (200, pending))


if __name__ == '__main__':
    unittest.main()
