"""Provider-neutral proposal boundary. No assessment, storage or payment tools."""
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Protocol

from jsonschema import Draft202012Validator

from evidence.backend.errors import InvalidInput
from evidence.backend.images import DecodedImage

MIN_CONFIDENCE = 0.85  # Conservative demo policy, NOT calibrated model confidence.
POLICY_VERSION = 'fixture-policy-1'
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}', re.ASCII)
OUTPUT_VALIDATOR = Draft202012Validator(json.loads(
    (Path(__file__).parent / 'schemas' / 'extraction-output.schema.json').read_text()))


class ExtractionUnavailable(RuntimeError):
    def __init__(self, message, *, code='unavailable'):
        super().__init__(message)
        valid = isinstance(code, str) and (
            code in {'unavailable', 'network', 'deadline', 'busy', 'invalid_response', 'invalid_proposal'}
            or re.fullmatch(r'http_[45][0-9]{2}', code))
        self.code = code if valid else 'unavailable'


class InvalidProposal(ValueError):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    fields: dict = field(repr=False)
    provenance: dict


class LabelExtractor(Protocol):
    """Adapters must use bounded provider timeouts and return untrusted field data.

    Implementations receive only a validated synthetic image, no campaign, order,
    approval state, database handle or tool registry. Adapters have no authority to assess or approve.
    """
    mode: str
    provider_name: str

    def extract(self, image: DecodedImage) -> dict | ExtractionResult:
        ...


def normalize_proposal(raw, mode):
    if mode not in ('mock', 'ai') or not OUTPUT_VALIDATOR.is_valid(raw):
        raise InvalidProposal('Unusable structured label proposal')
    result = {'mode': mode, 'model': None, 'batch': None,
              'confidence': {}, 'uncertain_fields': [], 'clarification': None,
              'policy_version': POLICY_VERSION}
    for name in ('model', 'batch'):
        item = raw[name]
        confidence = item['confidence']
        if confidence is not None and not math.isfinite(confidence):
            raise InvalidProposal('Non-finite label confidence')
        result['confidence'][name] = confidence
        value = item['value'].strip() if item['value'] is not None else None
        if (item['uncertain'] or confidence is None or confidence < MIN_CONFIDENCE
                or not value or '?' in value or not IDENTIFIER.fullmatch(value)
                or value.lower() in {'unknown', 'unclear', 'unreadable', 'unsure', 'n/a'}):
            result['uncertain_fields'].append(name)
        else:
            result[name] = value
    if result['uncertain_fields']:
        result['clarification'] = f"Please read and confirm the {result['uncertain_fields'][0]} printed on the label."
    result['notice'] = ('Fixture lookup, not OCR. Confirm or correct every identifier.' if mode == 'mock'
                        else 'AI suggestions only. Confirm or correct every identifier; confidence is not proof.')
    return result


class ExtractionService:
    def __init__(self, adapter: LabelExtractor):
        if adapter.mode not in ('mock', 'ai'):
            raise ValueError('Extraction adapter must declare mock or ai mode')
        self.adapter = adapter

    def propose(self, image: DecodedImage):
        if not isinstance(image, DecodedImage):
            raise InvalidInput('A decoded image is required for extraction')
        try:
            raw = self.adapter.extract(image)
            if isinstance(raw, ExtractionResult):
                result = normalize_proposal(raw.fields, self.adapter.mode)
                result['source'] = raw.provenance
                return result
            return normalize_proposal(raw, self.adapter.mode)
        except Exception as error:
            # Preserve only allowlisted diagnostic codes, never provider messages.
            code = error.code if isinstance(error, ExtractionUnavailable) else 'unavailable'
            raise ExtractionUnavailable('Extraction unavailable; enter the identifiers manually.', code=code) from None
