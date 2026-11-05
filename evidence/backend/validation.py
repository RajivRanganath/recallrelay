"""Frozen contract validation and bounded, transient image intake."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from evidence.backend.errors import InvalidInput
from evidence.backend.images import MAX_IMAGE_BYTES, decode_image

ROOT = Path(__file__).resolve().parents[2]
MAX_BODY_BYTES = 3 * 1024 * 1024
VALIDATORS = {
    name: Draft202012Validator(json.loads(
        (ROOT / 'contracts' / 'schemas' / f'{name}.schema.json').read_text()))
    for name in ('assessment-request', 'assessment-response', 'resolution-response')
}


def validate_contract(name, data):
    if not VALIDATORS[name].is_valid(data):
        # Never include rejected field values (possibly image bytes or secrets).
        raise InvalidInput(f'Invalid {name} payload')


def validate_label(label):
    if not isinstance(label, dict) or set(label) != {
        'image_base64', 'mime_type', 'confirmed_model', 'confirmed_batch'
    }:
        raise InvalidInput('Expected label image, MIME type, model and batch')
    for field in ('confirmed_model', 'confirmed_batch'):
        if not isinstance(label[field], str) or len(label[field]) > 128:
            raise InvalidInput('Identifiers must be text of at most 128 characters')
        if any(ord(c) < 32 for c in label[field]):
            raise InvalidInput('Identifiers cannot contain control characters')
    return decode_image(label['image_base64'], label['mime_type'])
