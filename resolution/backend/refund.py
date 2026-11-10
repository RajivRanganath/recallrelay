"""Human-approved refund execution. The operation ID is persisted before the adapter is called."""
import hashlib

from resolution.backend.errors import InvalidInput
from resolution.backend.paypal import CaptureNotRefundable, RefundRejected, RefundUnknown
from resolution.backend.store import ApprovalConflict
from resolution.backend.validation import validate_contract

HOLD_TEXT = {
    'open_dispute': 'Manual handling required: PayPal reports an open dispute on this payment.',
    'balance': 'Manual handling required: this payment has less left to refund than the approved amount.',
    'balance_unclear': "Manual handling required: this payment's refunded balance could not be determined.",
    'payment_state': 'Manual handling required: PayPal reports this payment cannot be refunded as approved.',
}
APPROVAL_FIELDS ={'assessment_id', 'campaign_version', 'capture_id', 'amount_minor', 'approved_by'}


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
    check = getattr(adapter, 'check_capture', None)
    if check and store.operation(case_id) is None:  # Only before the first claim; repeats just report state.
        try:
            check(approval['capture_id'], approval['amount_minor'], reviewed['currency'])
        except CaptureNotRefundable as error:  # Fixed texts only; nothing from PayPal is copied into the case.
            text = HOLD_TEXT.get(error.reason, HOLD_TEXT['payment_state'])
            store.hold(case_id, _response(reviewed, adapter, 'manual_required', text, reviewed.get('operation_id')))
            raise ApprovalConflict(text) from None
        except RefundUnknown:
            raise ApprovalConflict('Could not check the payment with PayPal; nothing was sent. Try again.') from None
    operation = operation_id(case_id, approval)
    pending =_response(reviewed, adapter, 'pending', 'Approved by merchant; refund requested and awaiting confirmation.', operation)
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
    if not _confirmed(adapter, operation, refund_id):  # PayPal's own record must agree before we say "refunded".
        return store.finish(case_id, _response(current, adapter, 'pending', 'Refund outcome unknown; reconcile before retrying.', operation['operation_id']))
    return store.finish(case_id, _response(current, adapter, 'refunded', 'Refund completed.', operation['operation_id'], refund_id))


def capture_of(event):
    """The payment ID a refund event points at (the 'up' link), or None."""
    resource = event.get('resource') if isinstance(event, dict) else None
    for link in (resource.get('links') if isinstance(resource, dict) and isinstance(resource.get('links'), list) else []):
        if isinstance(link, dict) and link.get('rel') == 'up' and isinstance(link.get('href'), str):
            tail = link['href'].rstrip('/').rsplit('/', 1)[-1]
            if tail and '?' not in tail:
                return tail
    return None


def apply_webhook(store, adapter, event):
    """Settle a PENDING or FAILED case from an already-verified refund event.

    The event is only a hint: the refund is read back from PayPal and must match the stored operation
    (ID, COMPLETED, amount, currency, and this operation's ID as custom_id) before the case moves. It can
    only ever move pending -> refunded or failed -> refunded; a failed case can be wrong when concurrent
    requests got different answers and the refund really completed. Nothing else is ever changed.
    Returns the settled response, or None when the event changed nothing.
    """
    resource = event.get('resource') if isinstance(event, dict) else None
    if not isinstance(event, dict) or event.get('event_type') != 'PAYMENT.CAPTURE.REFUNDED' or not isinstance(resource, dict):
        return None
    refund_id, capture_id = resource.get('id'), capture_of(event)
    if not isinstance(refund_id, str) or not capture_id:
        return None
    case_id = store.unsettled_case_for_capture(capture_id)
    operation = store.operation(case_id) if case_id else None
    current = store.latest(case_id) if case_id else None
    if (not operation or not current or current['status'] not in ('pending', 'failed') or not hasattr(adapter, 'get_refund')
            or not _confirmed(adapter, operation, refund_id, bound=True)):
        return None
    done = store.finish(case_id, _response(current, adapter, 'refunded', 'Refund completed.', operation['operation_id'], refund_id))
    return done if done['status'] == 'refunded' else None


def _confirmed(adapter, operation, refund_id, bound=False):
    """PayPal's own record must agree. With bound=True (refund IDs that arrived from outside, such as a
    webhook) the refund must also carry this operation's ID as its custom_id, so an older refund of the
    same amount on the same payment can never settle a newer operation."""
    read = getattr(adapter, 'get_refund', None)
    if read is None:
        return True
    try:
        found = read(refund_id)
    except Exception:
        return False
    amount = found.get('amount') if isinstance(found, dict) and isinstance(found.get('amount'), dict) else {}
    minor = operation['amount_minor']
    return (found.get('id') == refund_id and found.get('status') == 'COMPLETED' and amount.get('currency_code') == operation['currency']
            and amount.get('value') == f'{minor // 100}.{minor % 100:02d}'
            and (not bound or found.get('custom_id') == operation['operation_id']))
