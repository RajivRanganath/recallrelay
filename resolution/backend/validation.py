"""Frozen v1 contract validation."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from resolution.backend.errors import InvalidInput

ROOT = Path(__file__).resolve().parents[2]
MAX_BODY_BYTES = 64 * 1024
VALIDATORS = {
    name: Draft202012Validator(json.loads(
        (ROOT / 'contracts' / 'schemas' / f'{name}.schema.json').read_text()))
    for name in ('assessment-request', 'assessment-response', 'resolution-request', 'resolution-response')
}


def validate_contract(name, data):
    if not VALIDATORS[name].is_valid(data):
        # Never include rejected field values.
        raise InvalidInput(f'Invalid {name} payload')
