"""Canned synthetic proposals, selected by sample ID; never reads uploaded pixels."""
from evidence.ai.extraction import normalize_proposal

SAMPLES = {'clear': ('LAMP-100', 'B101'), 'blurred': ('LAMP-100', None),
           'excluded': ('LAMP-100', 'B103')}


def propose(sample_id):
    if sample_id not in SAMPLES:
        raise ValueError('Unknown synthetic sample')
    model, batch = SAMPLES[sample_id]
    raw = {name: {'value': value, 'confidence': .99 if value else None, 'uncertain': value is None}
           for name, value in (('model', model), ('batch', batch))}
    return {**normalize_proposal(raw, 'mock'), 'sample_id': sample_id}
