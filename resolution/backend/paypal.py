"""Refund adapter boundary. Only FakePayPal exists; it never makes network calls."""


class RefundRejected(RuntimeError):
    """PayPal definitively refused the refund; no money moved."""


class RefundUnknown(RuntimeError):
    """The outcome is not known (timeout, lost response); the refund may or may not exist."""


class CaptureNotRefundable(RuntimeError):
    """PayPal says the payment cannot be refunded as approved; nothing was sent. `reason` is a fixed code."""
    reason = 'payment_state'


class OpenDispute(CaptureNotRefundable):
    reason = 'open_dispute'


class BalanceTooLow(CaptureNotRefundable):
    reason = 'balance'


class BalanceUnclear(CaptureNotRefundable):
    reason = 'balance_unclear'


class FakePayPal:
    """In-memory stand-in. Like PayPal's request-ID idempotency, one operation ID creates one refund.

    `behaviors` scripts the next calls: 'ok', 'reject', 'unknown' (nothing created),
    or 'lost' (refund created but the response is lost).
    """
    mode = 'mock'

    def __init__(self, behaviors=()):
        self.behaviors = list(behaviors)
        self.refunds = {}  # operation_id -> refund_id
        self.amounts = {}  # refund_id -> (amount_minor, currency), for read-back
        self.calls = 0

    def refund(self, operation_id, capture_id, amount_minor, currency):
        self.calls += 1
        behavior = self.behaviors.pop(0) if self.behaviors else 'ok'
        if behavior == 'reject':
            raise RefundRejected('Refund refused')
        if behavior == 'unknown':
            raise RefundUnknown('No response')
        refund_id = self.refunds.setdefault(operation_id, f'fake-refund-{operation_id}')
        self.amounts[refund_id] = (amount_minor, currency)
        if behavior == 'lost':
            raise RefundUnknown('Response lost')
        return refund_id

    def verify_webhook(self, headers, raw, webhook_id):
        return getattr(self, 'webhooks_valid', False)  # Tests flip this; a fake never accepts events by default.

    def get_refund(self, refund_id):
        if refund_id not in self.amounts:
            raise RefundUnknown('Refund could not be read back')
        minor, currency = self.amounts[refund_id]
        return {'id': refund_id, 'status': 'COMPLETED', 'amount': {'value': f'{minor // 100}.{minor % 100:02d}', 'currency_code': currency}}
