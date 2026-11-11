"""Both actual services, separate stores, explicit HTTP handoff, fake payments only."""
import copy
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json

from evidence.integrated import integrated_session
from evidence.backend.server import make_server
from evidence.backend.resolution_client import ResolutionClient, ResolutionUnavailable
from test_assessment import fixture
from test_resolution_client import RunningServer
from test_resolution_integration import call


class IntegratedTests(unittest.TestCase):
    def submit(self, session, label=None):
        code, saved = call(session.customer_url, '/demo/assessments', {'label': label or fixture()['label']})
        self.assertEqual(code, 200)
        return saved

    def handoff(self, session, saved):
        return call(session.customer_url, '/demo/handoff', {'assessment_id': saved['assessment_id']})

    def test_same_case_from_customer_through_merchant_approval_back_to_customer(self):
        with integrated_session() as session:
            customer, merchant = session.customer_url, session.resolution_url
            self.assertTrue(call(customer, '/health')[1]['handoff_enabled'])
            self.assertEqual(call(customer, '/health')[1]['merchant_url'], merchant)
            self.assertEqual(call(merchant, '/v1/cases')[1], {'cases': []})
            saved = self.submit(session)
            self.assertEqual(call(merchant, '/v1/cases')[1], {'cases': []})
            code, reviewed = self.handoff(session, saved)
            self.assertEqual((code, reviewed['status'], reviewed['proposed_amount_minor']), (200, 'manual_required', 0))
            detail = call(merchant, '/v1/cases/case-demo-1')[1]
            self.assertEqual(detail['assessment']['assessment_id'], saved['assessment_id'])
            self.assertEqual(detail['assessment']['batch'], saved['batch'])
            self.assertIsNone(detail['operation'])
            self.assertFalse(detail['remedy_conditions_met'])
            self.assertEqual(call(customer, '/demo/resolution-status'), (200, reviewed))
            # Missing remedy confirmation and an arbitrary amount cannot authorize payment.
            binding = {k: v for k, v in detail['binding'].items() if k != 'currency'}
            binding['approved_by'] = 'synthetic-merchant'
            binding['amount_minor'] = 4000
            self.assertEqual(call(merchant, '/v1/cases/case-demo-1/approve', binding)[0], 409)
            self.assertEqual(call(merchant, '/v1/cases/case-demo-1/remedy-conditions', {})[1]['status'], 'awaiting_approval')
            self.assertEqual(self.handoff(session, saved)[1]['status'], 'awaiting_approval')
            self.assertTrue(call(merchant, '/v1/cases/case-demo-1')[1]['remedy_conditions_met'])
            binding['amount_minor'] = 1
            self.assertEqual(call(merchant, '/v1/cases/case-demo-1/approve', binding)[0], 409)
            binding['amount_minor'] = 4000
            code, done = call(merchant, '/v1/cases/case-demo-1/approve', binding)
            self.assertEqual((code, done['status'], done['mode']), (200, 'refunded', 'mock'))
            self.assertEqual(call(merchant, '/v1/cases/case-demo-1/approve', binding), (200, done))
            self.assertEqual(call(customer, '/demo/resolution-status'), (200, done))
            self.assertEqual(call(customer, '/v1/assessments/case-demo-1'), (200, saved))
            self.assertEqual(self.handoff(session, saved), (200, done))
            changed = copy.deepcopy(fixture()['label'])
            changed['confirmed_batch'] = ''
            newer = self.submit(session, changed)
            self.assertEqual(self.handoff(session, newer)[0], 409)
            self.assertEqual(call(customer, '/demo/resolution-status'), (200, done))
            self.assertTrue((session.state_directory / 'evidence.sqlite3').is_file())
            self.assertTrue((session.state_directory / 'resolution.sqlite3').is_file())

    def test_missing_and_excluded_remain_unresolved_without_payment(self):
        for batch, expected in [('', 'needs_information'), ('B103', 'excluded')]:
            with self.subTest(batch=batch), integrated_session() as session:
                label = copy.deepcopy(fixture()['label'])
                label['confirmed_batch'] = batch
                saved = self.submit(session, label)
                code, reviewed = self.handoff(session, saved)
                self.assertEqual((code, reviewed['status'], reviewed['proposed_amount_minor']), (200, expected, 0))
                detail = call(session.resolution_url, '/v1/cases/case-demo-1')[1]
                self.assertIsNone(detail['operation'])
                self.assertEqual(call(session.customer_url, '/demo/resolution-status'), (200, reviewed))

    def test_stale_snapshot_untrusted_context_and_cross_origin_are_rejected(self):
        with integrated_session() as session:
            self.assertEqual(self.handoff(session, {'assessment_id': 'missing'})[0], 409)
            first = self.submit(session)
            changed = copy.deepcopy(fixture()['label'])
            changed['confirmed_batch'] = ''
            latest = self.submit(session, changed)
            self.assertNotEqual(first['assessment_id'], latest['assessment_id'])
            self.assertEqual(self.handoff(session, first)[0], 409)
            body = {'assessment_id': latest['assessment_id'], 'remedy_conditions_met': True}
            self.assertEqual(call(session.customer_url, '/demo/handoff', body)[0], 400)
            req = Request(session.customer_url + '/demo/handoff', data=json.dumps({'assessment_id': latest['assessment_id']}).encode(),
                          headers={'Content-Type': 'application/json', 'Origin': 'https://untrusted.invalid'})
            with self.assertRaises(HTTPError) as error:
                urlopen(req, timeout=5)
            error.exception.close()
            self.assertEqual(error.exception.code, 403)
            self.assertEqual(call(session.resolution_url, '/v1/cases')[1], {'cases': []})
            self.assertEqual(self.handoff(session, latest)[1]['status'], 'needs_information')

    def test_handoff_is_opt_in_dependency_failure_keeps_saved_assessment(self):
        with tempfile.TemporaryDirectory() as folder:
            for enabled, expected in [(False, 404), (True, 503)]:
                with RunningServer(make_server(0, Path(folder) / f'{enabled}.sqlite3', 'http://127.0.0.1:1', enable_handoff=enabled)) as customer:
                    saved = call(customer, '/demo/assessments', {'label': fixture()['label']})[1]
                    code, error = call(customer, '/demo/handoff', {'assessment_id': saved['assessment_id']})
                    self.assertEqual(code, expected)
                    self.assertIn('error', error)
                    self.assertEqual(call(customer, '/v1/assessments/case-demo-1'), (200, saved))
            with self.assertRaises(ValueError):
                make_server(0, Path(folder) / 'invalid.sqlite3', 'https://example.com', enable_handoff=True)

    def test_launcher_cleans_both_services_and_temporary_state(self):
        with patch.dict('os.environ', {'RESOLUTION_BASE_URL': 'https://unused.invalid', 'PAYPAL_CLIENT_ID': 'unused'}):
            with integrated_session() as session:
                folder = session.state_directory
                self.assertEqual(call(session.resolution_url, '/health')[1]['mode'], 'mock')
                self.assertEqual(call(session.customer_url, '/health')[1]['extraction_mode'], 'mock')
        self.assertFalse(folder.exists())
        for url in (session.customer_url, session.resolution_url):
            with self.assertRaises((URLError, OSError)):
                with urlopen(url + '/health', timeout=1):
                    self.fail('Service remained available after shutdown')
        for value in (-1, 65536, True, '8101'):
            with self.assertRaises(ValueError):
                with integrated_session(port=value):
                    self.fail('Invalid port accepted')

    def test_launcher_does_not_select_on_process_pipes(self):
        # Windows selectors accept sockets but reject subprocess output pipes.
        with patch('selectors.DefaultSelector', side_effect=OSError(10038, 'Socket operation on nonsocket')):
            with integrated_session() as session:
                self.assertEqual(call(session.resolution_url, '/health')[1]['mode'], 'mock')

    def test_retry_after_lost_response_preserves_merchant_remedy_confirmation(self):
        original = ResolutionClient.handoff
        def accepted_but_response_lost(client, order, assessment):
            original(client, order, assessment)
            raise ResolutionUnavailable('Synthetic lost response after merchant acceptance')
        with integrated_session() as session:
            saved = self.submit(session)
            with patch.object(ResolutionClient, 'handoff', accepted_but_response_lost):
                self.assertEqual(self.handoff(session, saved)[0], 503)
            merchant = session.resolution_url
            self.assertEqual(call(merchant, '/v1/cases/case-demo-1/remedy-conditions', {})[1]['status'], 'awaiting_approval')
            with patch.object(ResolutionClient, 'handoff', side_effect=AssertionError('Must read the accepted snapshot, not repost it')):
                code, reviewed = self.handoff(session, saved)
            self.assertEqual((code, reviewed['status']), (200, 'awaiting_approval'))
            self.assertTrue(call(merchant, '/v1/cases/case-demo-1')[1]['remedy_conditions_met'])

    def test_a_new_assessment_still_replaces_an_unapproved_snapshot(self):
        with integrated_session() as session:
            first = self.submit(session)
            self.assertEqual(self.handoff(session, first)[0], 200)
            changed = copy.deepcopy(fixture()['label'])
            changed['confirmed_batch'] = ''
            latest = self.submit(session, changed)
            code, reviewed = self.handoff(session, latest)
            self.assertEqual((code, reviewed['status']), (200, 'needs_information'))
            detail = call(session.resolution_url, '/v1/cases/case-demo-1')[1]
            self.assertEqual(detail['assessment']['assessment_id'], latest['assessment_id'])


if __name__ == '__main__':
    unittest.main()
