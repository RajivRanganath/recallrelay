import importlib.util
import json
from pathlib import Path
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mock', ROOT/'scripts/mock_server.py')
mock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock)
class Contracts(unittest.TestCase):
    def test_fixtures_and_schema_definitions(self):
        for path in (ROOT/'contracts/fixtures').glob('*.json'):
            schema = json.loads((ROOT/f'contracts/schemas/{path.stem}.schema.json').read_text())
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(json.loads(path.read_text()))
    def test_all_mock_scenarios_conform(self):
        for lane, name, scenarios in [('evidence','assessment',['default','missing','excluded']), ('resolution','resolution',['default','manual','pending','failed'])]:
            schema = json.loads((ROOT/f'contracts/schemas/{name}-response.schema.json').read_text())
            for scenario in scenarios:
                with self.subTest(lane=lane, scenario=scenario):
                    Draft202012Validator(schema).validate(mock.result(lane, scenario))
    def test_http_roundtrips_and_invalid_input(self):
        for lane, resource, name in [('evidence','assessments','assessment'),('resolution','resolutions','resolution')]:
            server = mock.make_server(lane, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/health') as response:
                    self.assertEqual(json.load(response)['mode'], 'mock')
                payload = (ROOT/f'contracts/fixtures/{name}-request.json').read_bytes()
                with urlopen(Request(base+f'/v1/{resource}', data=payload, headers={'Content-Type':'application/json'})) as response:
                    self.assertEqual(json.load(response)['case_id'], 'case-demo-1')
                    self.assertEqual(response.headers['X-RecallRelay-Mode'], 'mock')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+f'/v1/{resource}', data=b'{}'))
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    urlopen(base+f'/v1/{resource}/unknown')
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()
if __name__ == '__main__': unittest.main()
