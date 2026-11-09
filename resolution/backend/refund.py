"""Human-approved refund execution. The operation ID is persisted before the adapter is called."""
import hashlib

from resolution.backend.errors import InvalidInput
from resolution.backend.paypal import RefundRejected
from resolution.backend.store import ApprovalConflict
from resolution.backend.validation import validate_contract

APPROVAL_FIELDS = {'assessment_id', 'campaign_version', 'capture_id', 'amount_minor', 'approved_by'}


def validate_approval(data):
    if not isinstance(data, dict) or set(data) != APPROVAL_FIELDS:
        raise InvalidInput('Expected assessment, campaign version, capture, amount and approver')
    for field in ('assessment_id', 'capture_id', 'approved_by'):
        if not isinstance(data[field], str) or not 0 < len(data[field]) <= 128 or any(ord(c) < 32 for c in data[field]):
            raise InvalidInput('Approval text fields must be 1-128 printable characters')
    for field in ('campaign_version', 'amount_minor'):
        if type(data[field]) is not int or data[field] < 0:
            raise InvalidInput('Approval numbers must be non-negative integers')
    if data['amount_minor'] == 0:
        raise InvalidInput('Approval amount must be greater than zero')
    return data


def operation_id(case_id, approval):
    key = '|'.join(str(approval[k]) for k in ('assessment_id', 'campaign_version', 'capture_id', 'amount_minor'))
    return 'op-' + hashlib.sha256(f'{case_id}|{key}'.encode()).hexdigest()[:24]


def _response(base, adapter, status, brief, operation, refund_id=None):
    response = dict(base, status=status, brief=brief, operation_id=operation, refund_id=refund_id, mode=adapter.mode)
    validate_contract('resolution-response', response)
    return response


def approve(store, adapter, case_id, approval):
    approval = validate_approval(approval)
    reviewed = store.latest(case_id)
    if not reviewed:
        raise ApprovalConflict('No reviewed case exists')
    if adapter.mode == 'sandbox' and approval['capture_id'].startswith('capture-demo'):
        raise ApprovalConflict('Fixture capture IDs must never reach PayPal')
    operation = operation_id(case_id, approval)
    pending = _response(reviewed, adapter, 'pending', 'Approved by merchant; refund requested and awaiting confirmation.', operation)
    response, claimed = store.claim_refund(case_id, operation, approval, pending)
    return _execute(store, adapter, case_id, response) if claimed else response


def reconcile(store, adapter, case_id):
    """Resubmit a pending refund with its original operation ID, which is safe to repeat."""
    current, operation = store.latest(case_id), store.operation(case_id)
    if not current or not operation or current['status'] != 'pending':
        raise ApprovalConflict('Case has no pending refund to reconcile')
    return _execute(store, adapter, case_id, current)


def _execute(store, adapter, case_id, current):
    operation = store.operation(case_id)
    try:
        refund_id = adapter.refund(operation['operation_id'], operation['capture_id'], operation['amount_minor'], operation['currency'])
    except RefundRejected:
        return store.finish(case_id, _response(current, adapter, 'failed', 'PayPal refused the refund; no money moved.', operation['operation_id']))
    except Exception:  # Unknown outcome, including unexpected errors: stay pending until reconciled.
        return store.finish(case_id, _response(current, adapter, 'pending', 'Refund outcome unknown; reconcile before retrying.', operation['operation_id']))
    return store.finish(case_id, _response(current, adapter, 'refunded', 'Refund completed.', operation['operation_id'], refund_id))
