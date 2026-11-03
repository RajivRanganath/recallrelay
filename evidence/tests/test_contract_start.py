import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parents[2]
class StarterContract(unittest.TestCase):
    def test_lane_fixture(self):
        for kind in ['request', 'response']:
            name = 'assessment-' + kind
            schema = json.loads((ROOT/f'contracts/schemas/{name}.schema.json').read_text())
            fixture = json.loads((ROOT/f'contracts/fixtures/{name}.json').read_text())
            Draft202012Validator(schema).validate(fixture)
