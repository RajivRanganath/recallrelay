import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from resolution.backend.paypal import FakePayPal, RefundUnknown
from resolution.backend.refund import apply_webhook, approve, capture_of
from resolution.backend.review import review
from resolution.backend.server import make_server
from resolution.backend.store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'contracts/fixtures/resolution-request.json').read_text())
APPROVAL = {'assessment_id': 'assessment-demo-1', 'campaign_version': 1,
            'capture_id': 'capture-demo-NOT-PAYPAL', 'amount_minor': 4000, 'approved_by': 'merchant-demo'}
CAPTURE = APPROVAL['capture_id']


def event(refund_id, capture=CAPTURE, kind='PAYMENT.CAPTURE.REFUNDED', **extra):
    resource = {'id': refund_id, 'status': 'COMPLETED', 'links': [
        {'rel': 'self', 'href': f'https://api.sandbox.paypal.com/v2/payments/refunds/{refund_id}'},
        {'rel': 'up', 'href': f'https://api.sandbox.paypal.com/v2/payments/captures/{capture}'}]}
    return dict({'id': 'WH-EVT-1', 'event_type': kind, 'resource': resource}, **extra)


class WebhookTests(unittest.TestCase):
    """A verified event may only settle a pending refund, and only after PayPal confirms it by a direct read."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'cases.sqlite3'
        self.store = CaseStore(self.db)
        request = copy.deepcopy(FIXTURE)
        request['remedy_conditions_met'] = True
        self.store.save_review(request, review(request))
        self.adapter = FakePayPal(['lost'])  # The refund exists at the provider, but our answer was lost: case is pending.
        self.pending = approve(self.store, self.adapter, 'case-demo-1', APPROVAL)
        self.refund_id = self.adapter.refunds[self.pending['operation_id']]

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_confirmed_refund_event_settles_the_pending_case(self):
        self.assertEqual(self.pending['status'], 'pending')
        done = apply_webhook(self.store, self.adapter, event(self.refund_id))
        self.assertEqual((done['status'], done['refund_id'], done['operation_id']), ('refunded', self.refund_id, self.pending['operation_id']))
        self.assertEqual(self.store.latest('case-demo-1'), done)
        self.assertEqual(self.adapter.calls, 1)  # Settling by event never sends a refund.

    def test_events_that_do_not_match_change_nothing(self):
        for name, bad in (('other event type', event(self.refund_id, kind='PAYMENT.CAPTURE.COMPLETED')),
                          ('other payment', event(self.refund_id, capture='capture-someone-else')),
                          ('unknown refund', event('R-NOT-AT-PAYPAL')),
                          ('no up link', {'event_type': 'PAYMENT.CAPTURE.REFUNDED', 'resource': {'id': self.refund_id, 'links': []}}),
                          ('no resource', {'event_type': 'PAYMENT.CAPTURE.REFUNDED'}), ('not an object', ['x']),
                          ('id not text', event(5))):
            with self.subTest(name):
                self.assertIsNone(apply_webhook(self.store, self.adapter, bad))
                self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')

    def test_the_event_is_a_hint_only_paypal_must_agree_on_amount_and_status(self):
        lying = type('Lying', (FakePayPal,), {'get_refund': lambda self, rid: dict(FakePayPal.get_refund(self, rid), status='PENDING')})
        wrong = type('Wrong', (FakePayPal,), {'get_refund': lambda self, rid: dict(FakePayPal.get_refund(self, rid), amount={'value': '1.00', 'currency_code': 'USD'})})
        gone = type('Gone', (FakePayPal,), {'get_refund': lambda self, rid: (_ for _ in ()).throw(RefundUnknown('x'))})
        for cls in (lying, wrong, gone):
            with self.subTest(cls.__name__):
                adapter = cls()
                adapter.amounts = dict(self.adapter.amounts)
                self.assertIsNone(apply_webhook(self.store, adapter, event(self.refund_id, status='COMPLETED')))
                self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')

    def test_a_finished_case_is_never_changed_by_a_late_event(self):
        done = apply_webhook(self.store, self.adapter, event(self.refund_id))
        self.assertIsNone(apply_webhook(self.store, self.adapter, event(self.refund_id)))
        self.assertEqual(self.store.latest('case-demo-1'), done)

    def test_an_adapter_that_cannot_read_refunds_never_trusts_an_event(self):
        class NoRead:
            mode = 'mock'
        self.assertIsNone(apply_webhook(self.store, NoRead(), event(self.refund_id)))
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')

    def test_capture_is_taken_from_the_up_link_only(self):
        self.assertEqual(capture_of(event('R1', capture='CAP1')), 'CAP1')
        for odd in ({'resource': {'links': [{'rel': 'up', 'href': 5}]}}, {'resource': {'links': 'x'}}, {'resource': {'links': [{'rel': 'up', 'href': 'x/y?z'}]}},
                    {'resource': 'x'}, None):
            self.assertIsNone(capture_of(odd))


class WebhookRouteTests(unittest.TestCase):
    def start(self, adapter, webhook_id='WH-1'):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CaseStore(Path(self.tmp.name) / 'cases.sqlite3')
        request = copy.deepcopy(FIXTURE)
        request['remedy_conditions_met'] = True
        self.store.save_review(request, review(request))
        pending = approve(self.store, adapter, 'case-demo-1', APPROVAL)
        self.refund_id = adapter.refunds[pending['operation_id']]
        self.server = make_server(0, Path(self.tmp.name) / 'cases.sqlite3', adapter, None, webhook_id)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=2)))
        self.url = f'http://127.0.0.1:{self.server.server_port}/v1/paypal/webhook'

    def post(self, body, content_type='application/json', headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        request = Request(self.url, data=raw, method='POST', headers={'Content-Type': content_type, **(headers or {})})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_unverified_events_are_rejected_and_change_nothing(self):
        adapter = FakePayPal(['lost'])
        self.start(adapter)
        self.assertEqual(self.post(event(self.refund_id))[0], 401)
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')

    def test_a_verified_event_settles_the_case(self):
        adapter = FakePayPal(['lost'])
        adapter.webhooks_valid = True
        self.start(adapter)
        code, body = self.post(event(self.refund_id))
        self.assertEqual((code, body), (200, {'accepted': True, 'settled': True}))
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'refunded')
        self.assertEqual(self.post(event(self.refund_id)), (200, {'accepted': True, 'settled': False}))  # Replays are harmless.

    def test_the_route_is_off_without_a_webhook_id_and_rejects_bad_requests(self):
        adapter = FakePayPal(['lost'])
        adapter.webhooks_valid = True
        self.start(adapter, webhook_id=None)
        self.assertEqual(self.post(event(self.refund_id))[0], 404)
        self.server.shutdown()
        self.server.server_close()
        self.start(adapter)
        self.assertEqual(self.post(b'', headers={})[0], 400)
        self.assertEqual(self.post(event(self.refund_id), content_type='text/plain')[0], 400)
        self.assertEqual(self.post(b'{"a": 1, "a": 2}')[1].get('error'), 'Invalid event')
        self.assertEqual(self.post(event(self.refund_id), headers={'Origin': 'http://evil.example'})[0], 403)

    def test_paypal_being_unreachable_is_a_retryable_error_not_a_pass(self):
        class Down(FakePayPal):
            def verify_webhook(self, headers, raw, webhook_id):
                raise RefundUnknown('down')
        adapter = Down(['lost'])
        self.start(adapter)
        self.assertEqual(self.post(event(self.refund_id))[0], 503)
        self.assertEqual(self.store.latest('case-demo-1')['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
