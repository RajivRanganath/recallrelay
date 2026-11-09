import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from resolution.backend.errors import InvalidInput
from resolution.backend.paypal import CaptureNotRefundable, FakePayPal, OpenDispute, RefundUnknown
from resolution.backend.refund import approve, reconcile
from resolution.backend.review import review
from resolution.backend.store import ApprovalConflict, AlreadyInProgress, CaseStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())
APPROVAL = {'assessment_id': 'assessment-demo-1', 'campaign_version': 1,
            'capture_id': 'capture-demo-NOT-PAYPAL', 'amount_minor': 4000, 'approved_by': 'merchant-demo'}


class RefundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'cases.sqlite3')
        request = copy.deepcopy(FIXTURE)
        request['remedy_conditions_met'] = True
        self.store.save_review(request, review(request))

    def tearDown(self):
        self.tmp.cleanup()

    def test_approval_creates_one_refund_with_a_persisted_operation_id(self):
        adapter = FakePayPal()
        result = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual((result['status'], result['proposed_amount_minor']), ('refunded', 4000))
        self.assertEqual(result['refund_id'], f"fake-refund-{result['operation_id']}")
        self.assertEqual(self.store.operation('case-demo-1')['operation_id'], result['operation_id'])
        self.assertEqual(self.store.latest('case-demo-1'), result)

    def test_repeated_approval_never_creates_a_second_refund(self):
        adapter = FakePayPal()
        first = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual(approve(self.store, adapter, 'case-demo-1', APPROVAL), first)
        self.assertEqual((adapter.calls, len(adapter.refunds)), (1, 1))

    def test_concurrent_approvals_call_paypal_once(self):
        adapter = FakePayPal()
        results = []
        threads = [threading.Thread(target=lambda: results.append(approve(self.store, adapter, 'case-demo-1', APPROVAL))) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual((len(results), adapter.calls, len(adapter.refunds)), (8, 1, 1))
        self.assertEqual({r['operation_id'] for r in results}, {results[0]['operation_id']})

    def test_approval_must_match_reviewed_assessment_campaign_capture_and_amount(self):
        for field, value in (('amount_minor', 3999), ('amount_minor', 9999), ('assessment_id', 'other'),
                             ('campaign_version', 2), ('capture_id', 'capture-other')):
            with self.subTest(field=field, value=value), self.assertRaises(ApprovalConflict):
                approve(self.store, FakePayPal(), 'case-demo-1', dict(APPROVAL, **{field: value}))
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'awaiting_approval')
        self.assertIsNone(self.store.operation('case-demo-1'))

    def test_malformed_approvals_are_rejected(self):
        for bad in (None, {}, dict(APPROVAL, amount_minor=0), dict(APPROVAL, amount_minor='4000'),
                    dict(APPROVAL, amount_minor=True), dict(APPROVAL, approved_by=''), dict(APPROVAL, extra=1)):
            with self.subTest(bad=bad), self.assertRaises(InvalidInput):
                approve(self.store, FakePayPal(), 'case-demo-1', bad)

    def test_only_cases_awaiting_approval_can_be_approved(self):
        excluded = copy.deepcopy(FIXTURE)
        excluded['assessment']['decision'] = 'excluded'
        self.store.save_review(excluded, review(excluded))
        adapter = FakePayPal()
        with self.assertRaises(ApprovalConflict):
            approve(self.store, adapter, 'case-demo-1', APPROVAL)
        with self.assertRaises(ApprovalConflict):
            approve(self.store, adapter, 'unknown', APPROVAL)
        self.assertEqual(adapter.calls, 0)

    def test_lost_response_stays_pending_then_reconciles_without_a_duplicate(self):
        adapter = FakePayPal(['lost'])
        pending = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual((pending['status'], pending['refund_id']), ('pending', None))
        done = reconcile(self.store, adapter, 'case-demo-1')
        self.assertEqual((done['status'], done['operation_id']), ('refunded', pending['operation_id']))
        self.assertEqual(len(adapter.refunds), 1)

    def test_unknown_outcome_stays_pending_and_can_retry_with_the_same_operation(self):
        adapter = FakePayPal(['unknown', 'unknown'])
        first = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual(reconcile(self.store, adapter, 'case-demo-1')['status'], 'pending')
        self.assertEqual(reconcile(self.store, adapter, 'case-demo-1')['status'], 'refunded')
        self.assertEqual(first['operation_id'], self.store.operation('case-demo-1')['operation_id'])

    def test_rejected_refund_is_visible_and_locks_the_case(self):
        result = approve(self.store, FakePayPal(['reject']), 'case-demo-1', APPROVAL)
        self.assertEqual((result['status'], result['refund_id']), ('failed', None))
        with self.assertRaises(ApprovalConflict):
            reconcile(self.store, FakePayPal(), 'case-demo-1')
        request = copy.deepcopy(FIXTURE)
        request['remedy_conditions_met'] = True
        with self.assertRaises(AlreadyInProgress):
            self.store.save_review(request, review(request))

    def test_reconcile_requires_a_pending_refund(self):
        with self.assertRaises(ApprovalConflict):
            reconcile(self.store, FakePayPal(), 'case-demo-1')

    def test_overlapping_reconciles_never_turn_a_refunded_case_back_to_pending(self):
        first_started, release_first = threading.Event(), threading.Event()

        class Slow(FakePayPal):
            def refund(self, *args):
                self.calls += 1
                if self.calls == 1:  # Initial approval: outcome unknown, case stays pending.
                    raise RefundUnknown('No response')
                if self.calls == 2:  # Slow check: started first, times out only after the other check has finished.
                    first_started.set()
                    release_first.wait(5)
                    raise RefundUnknown('Timed out')
                return super().refund(*args)  # Fast check: completes the refund.

        adapter = Slow()
        approve(self.store, adapter, 'case-demo-1', APPROVAL)
        results = {}
        slow = threading.Thread(target=lambda: results.update(slow=reconcile(self.store, adapter, 'case-demo-1')))
        slow.start()
        first_started.wait(5)
        results['fast'] = reconcile(self.store, adapter, 'case-demo-1')
        release_first.set()
        slow.join()
        self.assertEqual(results['fast']['status'], 'refunded')
        self.assertEqual(results['slow']['status'], 'refunded')  # The late "unknown" gets the stored result back.
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'refunded')

    def test_a_confirmed_refund_is_not_hidden_behind_an_earlier_failure(self):
        # Same-ID requests can get different answers from PayPal: one check is told "refused", another succeeds.
        adapter = FakePayPal(['reject'])
        failed = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual(failed['status'], 'failed')
        done = dict(failed, status='refunded', brief='Refund completed.', refund_id='fake-refund-confirmed')
        self.assertEqual(self.store.finish('case-demo-1', done)['status'], 'refunded')
        self.assertEqual(self.store.latest('case-demo-1')['refund_id'], 'fake-refund-confirmed')

    def test_only_failed_can_be_upgraded_and_only_to_refunded(self):
        failed = approve(self.store, FakePayPal(['reject']), 'case-demo-1', APPROVAL)
        for status in ('pending', 'failed'):  # A failure stays a failure unless a refund is confirmed.
            self.assertEqual(self.store.finish('case-demo-1', dict(failed, status=status))['status'], 'failed')
        self.tearDown()
        self.setUp()
        refunded = approve(self.store, FakePayPal(), 'case-demo-1', APPROVAL)
        for status in ('pending', 'failed', 'refunded'):  # A completed refund is never replaced.
            self.assertEqual(self.store.finish('case-demo-1', dict(refunded, status=status, refund_id=None))['refund_id'], refunded['refund_id'])
        self.assertEqual(self.store.latest('case-demo-1'), refunded)

    def test_a_failed_check_after_a_successful_one_does_not_lose_the_refund(self):
        started, release = threading.Event(), threading.Event()

        class Split(FakePayPal):
            def refund(self, *args):
                self.calls += 1
                if self.calls == 1:
                    raise RefundUnknown('No response')  # Approval leaves the case pending.
                if self.calls == 2:  # Slow check: PayPal refuses it, but only after the other check already finished.
                    started.set()
                    release.wait(5)
                    from resolution.backend.paypal import RefundRejected
                    raise RefundRejected('Refused')
                return super().refund(*args)  # Fast check succeeds.

        adapter = Split()
        approve(self.store, adapter, 'case-demo-1', APPROVAL)
        slow = threading.Thread(target=lambda: reconcile(self.store, adapter, 'case-demo-1'))
        slow.start()
        started.wait(5)
        self.assertEqual(reconcile(self.store, adapter, 'case-demo-1')['status'], 'refunded')
        release.set()
        slow.join()
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'refunded')

    def test_a_failure_that_lands_first_cannot_hide_a_later_confirmed_refund(self):
        started, release = threading.Event(), threading.Event()

        class Split(FakePayPal):
            def refund(self, *args):
                self.calls += 1
                if self.calls == 1:
                    raise RefundUnknown('No response')
                if self.calls == 2:  # Slow check: succeeds, but only after the other check stored "failed".
                    started.set()
                    release.wait(5)
                    return super().refund(*args)
                from resolution.backend.paypal import RefundRejected
                raise RefundRejected('Refused')  # Fast check: refused.

        adapter = Split()
        approve(self.store, adapter, 'case-demo-1', APPROVAL)
        results = {}
        slow = threading.Thread(target=lambda: results.update(slow=reconcile(self.store, adapter, 'case-demo-1')))
        slow.start()
        started.wait(5)
        self.assertEqual(reconcile(self.store, adapter, 'case-demo-1')['status'], 'failed')
        release.set()
        slow.join()
        self.assertEqual((results['slow']['status'], self.store.latest('case-demo-1')['status']), ('refunded', 'refunded'))

    def test_late_unknown_result_cannot_overwrite_a_completed_refund(self):
        done = approve(self.store, FakePayPal(), 'case-demo-1', APPROVAL)
        late = dict(done, status='pending', refund_id=None)
        self.assertEqual(self.store.finish('case-demo-1', late)['status'], 'refunded')
        self.assertEqual(self.store.latest('case-demo-1'), done)

    def test_refund_is_not_called_done_unless_the_provider_read_back_agrees(self):
        for name, read in (('unreadable', lambda self, rid: (_ for _ in ()).throw(RefundUnknown('x'))),
                           ('not_completed', lambda self, rid: dict(FakePayPal.get_refund(self, rid), status='PENDING')),
                           ('wrong_amount', lambda self, rid: dict(FakePayPal.get_refund(self, rid), amount={'value': '1.00', 'currency_code': 'USD'}))):
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                adapter = type('Adapter', (FakePayPal,), {'get_refund': read})()
                result = approve(self.store, adapter, 'case-demo-1', APPROVAL)
                self.assertEqual((result['status'], result['refund_id']), ('pending', None))

    def test_approval_checks_the_payment_before_claiming_and_blocks_unrefundable_payments(self):
        class Checked(FakePayPal):
            def __init__(self, outcome):
                super().__init__()
                self.outcome, self.checks = outcome, 0

            def check_capture(self, capture_id, amount_minor, currency):
                self.checks += 1
                if self.outcome:
                    raise self.outcome('blocked')
        # PayPal says no -> manual handling. PayPal unreachable -> blocked, but the case stays approvable.
        for outcome, expected in ((CaptureNotRefundable, 'manual_required'), (OpenDispute, 'manual_required'), (RefundUnknown, 'awaiting_approval')):
            with self.subTest(outcome=outcome.__name__):
                self.tearDown()
                self.setUp()
                adapter = Checked(outcome)
                with self.assertRaises(ApprovalConflict):
                    approve(self.store, adapter, 'case-demo-1', APPROVAL)
                self.assertEqual((adapter.calls, self.store.operation('case-demo-1')), (0, None))
                self.assertEqual(self.store.latest('case-demo-1')['status'], expected)
        self.tearDown()
        self.setUp()
        ok = Checked(None)
        first = approve(self.store, ok, 'case-demo-1', APPROVAL)
        self.assertEqual((first['status'], ok.checks), ('refunded', 1))
        approve(self.store, ok, 'case-demo-1', APPROVAL)  # A repeat reports state without re-checking or refunding.
        self.assertEqual((ok.checks, ok.calls), (1, 1))

    def test_fixture_capture_ids_never_reach_a_real_sandbox_adapter(self):
        class Sandbox(FakePayPal):
            mode = 'sandbox'
        adapter = Sandbox()
        with self.assertRaises(ApprovalConflict):
            approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.assertEqual(adapter.calls, 0)
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'awaiting_approval')
        self.assertIsNone(self.store.operation('case-demo-1'))


if __name__ == '__main__':
    unittest.main()
