"""A repeated handoff cannot undo merchant confirmation or a payment hold."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from resolution.backend.review import review
from resolution.backend.store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())


class ReviewReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'cases.sqlite3')
        self.pending = copy.deepcopy(FIXTURE)
        self.confirmed = dict(copy.deepcopy(FIXTURE), remedy_conditions_met=True)
        self.store.save_review(self.pending, review(self.pending))
        self.accepted = self.store.save_review(self.confirmed, review(self.confirmed))

    def tearDown(self):
        self.tmp.cleanup()

    def test_unconfirmed_replay_preserves_confirmed_response_and_snapshot(self):
        self.assertEqual(self.store.save_review(self.pending, review(self.pending)), self.accepted)
        self.assertEqual(self.store.request('case-demo-1'), self.confirmed)
        self.assertIsNone(self.store.operation('case-demo-1'))

    def test_replay_preserves_a_provider_hold_instead_of_reopening_approval(self):
        held = dict(self.accepted, status='manual_required', proposed_amount_minor=0,
                    brief='Manual handling required: payment has an open dispute.')
        self.assertTrue(self.store.hold('case-demo-1', held))
        self.assertEqual(self.store.save_review(self.pending, review(self.pending)), held)
        self.assertEqual(self.store.latest('case-demo-1'), held)

    def test_new_assessment_requires_fresh_remedy_confirmation(self):
        updated = copy.deepcopy(self.pending)
        updated['assessment']['assessment_id'] = 'assessment-new-snapshot'
        result = self.store.save_review(updated, review(updated))
        self.assertEqual(result['status'], 'manual_required')
        self.assertFalse(self.store.request('case-demo-1')['remedy_conditions_met'])

    def test_changed_order_does_not_inherit_remedy_confirmation(self):
        updated = copy.deepcopy(self.pending)
        updated['order']['capture_id'] = 'capture-another-synthetic'
        result = self.store.save_review(updated, review(updated))
        self.assertEqual(result['status'], 'manual_required')
        self.assertFalse(self.store.request('case-demo-1')['remedy_conditions_met'])

    def test_changed_assessment_values_do_not_inherit_confirmation(self):
        updated = copy.deepcopy(self.pending)
        updated['assessment']['batch'] = 'B102'
        result = self.store.save_review(updated, review(updated))
        self.assertEqual(result['status'], 'manual_required')
        self.assertFalse(self.store.request('case-demo-1')['remedy_conditions_met'])

    def test_concurrent_confirmation_and_replays_finish_confirmed(self):
        barrier = threading.Barrier(8)
        errors = []
        def save(confirmed):
            try:
                barrier.wait(timeout=5)
                request = self.confirmed if confirmed else self.pending
                self.store.save_review(request, review(request))
            except Exception as error:
                errors.append(error)
        workers = [threading.Thread(target=save, args=(i == 0,)) for i in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertTrue(self.store.request('case-demo-1')['remedy_conditions_met'])
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'awaiting_approval')
