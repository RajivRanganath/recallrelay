import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from resolution.backend.errors import InvalidInput
from resolution.backend.paypal import FakePayPal
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
