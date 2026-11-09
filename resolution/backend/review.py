"""Deterministic review. Code, not AI, decides the status; this step never moves money."""
from resolution.backend.errors import InvalidInput

REFUND_WINDOW_DAYS = 180  # Older original captures stay manual.
CAMPAIGN_CURRENCY = 'USD'


def review(request):
    order, assessment = request['order'], request['assessment']
    if order['case_id'] != assessment['case_id']:
        raise InvalidInput('Order and assessment refer to different cases')
    citations = sorted({item['source_id'] for item in assessment['evidence']})
    remaining = max(order['paid_minor'] - order['previously_refunded_minor'], 0)

    if assessment['decision'] == 'needs_information':
        status, amount = 'needs_information', 0
        brief = f"More information is needed before review: {assessment['reason']}"
    elif assessment['decision'] == 'excluded':
        status, amount = 'excluded', 0
        brief = f"Excluded from this campaign, which is not a safety finding: {assessment['reason']}"
    else:
        problems = []
        if order['currency'] != CAMPAIGN_CURRENCY:
            problems.append(f'currency is not {CAMPAIGN_CURRENCY}')
        if order['quantity'] != 1:
            problems.append('case does not cover exactly one unit')
        if order['age_days'] > REFUND_WINDOW_DAYS:
            problems.append(f'purchase is older than {REFUND_WINDOW_DAYS} days')
        if remaining == 0:
            problems.append('nothing is left to refund')
        if not request['remedy_conditions_met']:
            problems.append('remedy conditions are not confirmed by the merchant')
        if problems:
            status, amount = 'manual_required', 0
            brief = 'Manual handling required: ' + '; '.join(problems) + '.'
        else:
            status, amount = 'awaiting_approval', remaining
            brief = (f"Assessment {assessment['assessment_id']} matches this campaign. "
                     f'Merchant approval needed for a refund of {remaining} minor units {order["currency"]}.')
    return {
        'schema_version': '1.0', 'case_id': order['case_id'], 'status': status, 'brief': brief,
        'citations': citations, 'proposed_amount_minor': amount, 'currency': order['currency'],
        'refund_id': None, 'operation_id': None,
        # No PayPal call exists yet, so nothing here may claim 'sandbox'.
        'mode': 'mock',
    }
