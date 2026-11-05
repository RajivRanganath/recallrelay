"""Deterministic v1 identifier checks; never approves or executes a refund."""
from uuid import uuid4

from evidence.backend.validation import validate_contract, validate_label

UNCERTAIN = {'unknown', 'unclear', 'unreadable', 'unsure', 'n/a'}


def confirmed(value):
    text = value.strip()
    return None if not text or '?' in text or text.lower() in UNCERTAIN else text


def assess(request):
    validate_contract('assessment-request', request)
    validate_label(request['label'])
    campaign, order, label = request['campaign'], request['order'], request['label']
    model, batch = (confirmed(label[f'confirmed_{field}']) for field in ('model', 'batch'))
    missing = [field for field, value in (('model', model), ('batch', batch)) if value is None]
    evidence = [
        {'source_id': 'confirmed-label', 'field': field, 'value': value}
        for field, value in (('model', model), ('batch', batch)) if value is not None
    ]
    decision, clarification = 'needs_information', None
    if missing:
        reason = 'Confirmed identifiers are missing or uncertain.'
        clarification = f"Please confirm the {missing[0]} printed on the product label."
    elif not campaign['approved']:
        missing = ['campaign.approved']
        reason = 'The campaign needs merchant approval before identifiers can be assessed.'
        clarification = 'Ask the merchant to supply an approved campaign snapshot.'
    elif (campaign['currency'] != 'USD' or order['currency'] != 'USD'
          or campaign['remedy'] != 'refund' or order['quantity'] != 1):
        missing = ['supported_context']
        reason = 'This prototype supports one unit, a refund campaign and USD only.'
        clarification = 'Ask the merchant to review this unsupported case manually.'
    elif not campaign['affected_models'] or not campaign['affected_batches']:
        missing = ['campaign.rules']
        reason = 'The campaign identifier rules are incomplete.'
        clarification = 'Ask the merchant to supply complete approved identifier rules.'
    elif (model not in campaign['affected_models'] or batch in campaign['excluded_batches']
          or batch not in campaign['affected_batches']):
        decision = 'excluded'
        reason = 'Confirmed identifiers do not match this campaign. This is not a product safety finding.'
    else:
        decision = 'eligible'
        reason = 'Confirmed model and batch match this campaign. Merchant remedy and payment checks are still required; no refund is authorized.'
    response = {
        'schema_version': '1.0', 'assessment_id': f'assessment-{uuid4().hex}',
        'case_id': order['case_id'], 'campaign_id': campaign['campaign_id'],
        'campaign_version': campaign['version'], 'decision': decision,
        'model': model, 'batch': batch, 'missing_fields': missing,
        'clarification': clarification, 'evidence': evidence, 'reason': reason,
        'mode': 'manual',
    }
    validate_contract('assessment-response', response)
    return response
