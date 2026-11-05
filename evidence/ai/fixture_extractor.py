"""Offline fixture lookup by image bytes. This is NOT OCR or model inference."""
import copy
import hashlib
import json
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'evals' / 'fixtures' / 'manifest.json'


class FixtureExtractor:
    mode = 'mock'
    provider_name = 'synthetic-fixture-lookup-v1'

    def __init__(self, manifest=DEFAULT_MANIFEST):
        data = json.loads(Path(manifest).read_text())
        if data.get('dataset_version') != 'synthetic-labels-v1' or not data.get('synthetic_only'):
            raise ValueError('Expected the versioned synthetic dataset')
        self.responses = {}
        for case in data['cases']:
            digest = case['sha256']
            if digest in self.responses:
                raise ValueError('Fixture image hashes must be unique')
            self.responses[digest] = case['mock_output']

    def extract(self, image):
        digest = hashlib.sha256(image.content).hexdigest()
        if digest not in self.responses:
            raise ValueError('Unknown image; the fixture adapter cannot read arbitrary pixels')
        return copy.deepcopy(self.responses[digest])
