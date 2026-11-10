import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from resolution.backend.paypal import FakePayPal, RefundUnknown
from resolution.sandbox import retry_experiment
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
        self.assertTrue(seen['custom_id_matches'])  # The refund is bound to the request ID.
        self.assertEqual(len(adapter.refunds), 1)

    def test_a_provider_that_duplicates_the_refund_fails_the_experiment(self):
        adapter = NotIdempotent()
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertFalse(seen['passed'])
        self.assertFalse(seen['same_refund_id'])

    def test_a_refund_that_is_not_bound_to_the_request_id_fails_the_experiment(self):
        adapter = type('Untagged', (FakePayPal,), {'get_refund': lambda self, rid: dict(FakePayPal.get_refund(self, rid), custom_id=None)})()
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertFalse(seen['custom_id_matches'])
        self.assertFalse(seen['passed'])

    def test_provider_errors_are_recorded_not_raised(self):
        adapter = FakePayPal(['unknown'])
        adapter.check_capture = lambda *args: None
        seen = run(adapter, 'REALCAPTURE1', 1000, 'req-1')
        self.assertFalse(seen['passed'])
        self.assertIn('RefundUnknown', seen['error'])


class OutputReservationTests(unittest.TestCase):
    """The report file is reserved before PayPal is contacted, so a rerun cannot create another real refund."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.case = Path(self.tmp.name) / 'case.json'
        self.case.write_text(json.dumps({'order': {'capture_id': 'REALCAPTURE1'}}))
        self.output = Path(self.tmp.name) / 'report.json'
        self.calls = []

    def main(self, *extra):
        def fake_run(adapter, capture_id, amount_minor, request_id, currency='USD'):
            self.calls.append(request_id)
            return {'request_id': request_id, 'passed': True}
        argv = ['retry_experiment', str(self.case), '--output', str(self.output), *extra]
        with mock.patch.object(sys, 'argv', argv), mock.patch.object(retry_experiment, 'run', fake_run), \
                mock.patch.object(retry_experiment, 'load_credentials', lambda env=None: ('id', 'secret')), \
                mock.patch.object(retry_experiment, 'SandboxPayPal', lambda *args: object()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                retry_experiment.main()
        return caught.exception.code

    def test_the_first_run_writes_the_report_and_a_rerun_stops_before_contacting_paypal(self):
        self.assertEqual(self.main(), 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(json.loads(self.output.read_text())['passed'], True)
        self.assertNotEqual(self.main(), 0)  # The report already exists: refuse...
        self.assertEqual(len(self.calls), 1)  # ...and PayPal was not contacted a second time.

    def test_an_existing_report_stops_the_run_even_with_a_fixed_request_id(self):
        self.output.write_text('earlier result')
        self.assertNotEqual(self.main('--request-id', 'req-fixed'), 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.read_text(), 'earlier result')  # Never overwritten.


if __name__ == '__main__':
    unittest.main()
