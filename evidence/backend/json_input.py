"""Reject ambiguous/non-standard JSON at both HTTP boundaries."""
import json
import math

from evidence.backend.errors import InvalidInput


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InvalidInput('Duplicate JSON keys are not supported')
            result[key] = value
        return result

    def invalid_constant(value):
        raise InvalidInput('Non-finite JSON numbers are not supported')

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise InvalidInput('JSON number exceeded the finite range')
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidInput('Malformed or ambiguous JSON') from None
