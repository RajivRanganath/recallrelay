"""Refund adapter boundary. Only FakePayPal exists; it never makes network calls."""


class RefundRejected(RuntimeError):
    """PayPal definitively refused the refund; no money moved."""


class RefundUnknown(RuntimeError):
    """The outcome is not known (timeout, lost response); the refund may or may not exist."""


class FakePayPal:
    """In-memory stand-in. Like PayPal's request-ID idempotency, one operation ID creates one refund.

    `behaviors` scripts the next calls: 'ok', 'reject', 'unknown' (nothing created),
    or 'lost' (refund created but the response is lost).
    """
    mode = 'mock'

    def __init__(self, behaviors=()):
        self.behaviors = list(behaviors)
        self.refunds = {}  # operation_id -> refund_id
        self.calls = 0

    def refund(self, operation_id, capture_id, amount_minor, currency):
        self.calls += 1
        behavior = self.behaviors.pop(0) if self.behaviors else 'ok'
        if behavior == 'reject':
            raise RefundRejected('Refund refused')
        if behavior == 'unknown':
            raise RefundUnknown('No response')
        refund_id = self.refunds.setdefault(operation_id, f'fake-refund-{operation_id}')
        if behavior == 'lost':
            raise RefundUnknown('Response lost')
        return refund_id
