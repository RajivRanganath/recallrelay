import unittest

from resolution.backend.paypal import FakePayPal, RefundUnknown
from resolution.sandbox.retry_experiment import run


class NotIdempotent(FakePayPal):
    """A provider that makes a new refund on every call: the experiment must notice."""

    def refund(self, operation_id, capture_id, amount_minor, currency):
        return super().refund(f'{operation_id}-{self.calls}', capture_id, amount_minor, currency)


class RetryExperimentTests(unittest.TestCase):
    def test_same_request_id_returns_the_same_refund_and_the_read_back_matches(self):
        adapter = FakePayPal()
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertTrue(seen['passed'])
        self.assertEqual((seen['first_refund_id'] == seen['retry_refund_id'], seen['read_back']['amount']['value']), (True, '10.00'))
        self.assertEqual(len(adapter.refunds), 1)

    def test_a_provider_that_duplicates_the_refund_fails_the_experiment(self):
        adapter = NotIdempotent()
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertFalse(seen['passed'])
        self.assertFalse(seen['same_refund_id'])

    def test_provider_errors_are_recorded_not_raised(self):
        adapter = FakePayPal(['unknown'])
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertFalse(seen['passed'])
        self.assertIn('RefundUnknown', seen['error'])


if __name__ == '__main__':
    unittest.main()
