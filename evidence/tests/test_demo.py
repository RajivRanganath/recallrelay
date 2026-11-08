"""Temporary-state and cleanup checks for the local synthetic rehearsal launcher."""
from unittest.mock import patch
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from evidence import demo
from scripts.mock_server import make_server as make_mock
from test_assessment import fixture
from test_resolution_client import RunningServer
from test_resolution_integration import call


class DemoTests(unittest.TestCase):
    def test_rehearsal_starts_clean_uses_mock_and_removes_storage_and_servers(self):
        # Existing provider configuration must not select an AI or remote adapter.
        with patch.dict('os.environ', {'RESOLUTION_BASE_URL': 'https://unused.invalid',
                                      'OMNIROUTE_API_KEY': 'synthetic-unused-key'}), \
                patch('evidence.backend.server.read_key') as key:
            with demo.rehearsal() as session:
                folder = session.state_directory
                self.assertTrue(folder.is_dir())
                code, health = call(session.customer_url, '/health')
                self.assertEqual((code, health['extraction_mode']), (200, 'mock'))
                self.assertEqual(session.resolution_source, 'committed resolution mock')
                self.assertEqual(call(session.customer_url, '/v1/assessments/case-demo-1')[0], 404)
                code, proposal = call(session.customer_url, '/demo/extraction', {'sample_id': 'clear'})
                self.assertEqual((code, proposal['mode'], proposal['batch']), (200, 'mock', 'B101'))
                self.assertEqual(call(session.customer_url, '/v1/assessments/case-demo-1')[0], 404)
                code, saved = call(session.customer_url, '/demo/assessments', {'label': fixture()['label']})
                self.assertEqual((code, saved['decision'], saved['mode']), (200, 'eligible', 'manual'))
                code, status = call(session.customer_url, '/demo/resolution-status')
                self.assertEqual((code, status['mode'], status['status']), (200, 'mock', 'awaiting_approval'))
                self.assertEqual(call(session.customer_url, '/v1/assessments/case-demo-1'), (200, saved))
            key.assert_not_called()
        self.assertFalse(folder.exists())
        for url in (session.customer_url, session.resolution_url):
            with self.subTest(url=url), self.assertRaises((URLError, OSError)):
                with urlopen(url + '/health', timeout=1):
                    self.fail('Server remained available after rehearsal cleanup')
        with demo.rehearsal() as fresh:
            self.assertEqual(call(fresh.customer_url, '/v1/assessments/case-demo-1')[0], 404)

    def test_explicit_resolution_origin_is_read_only_and_not_stopped_on_exit(self):
        with RunningServer(make_mock('resolution', 0)) as external:
            with patch('evidence.demo.make_mock') as factory:
                with demo.rehearsal(resolution_url=external) as session:
                    self.assertEqual(session.resolution_source, 'external service')
                    self.assertEqual(session.resolution_url, external)
                    self.assertEqual(call(session.customer_url, '/demo/resolution-status')[0], 200)
                factory.assert_not_called()
            self.assertEqual(call(external, '/health')[0], 200)

    def test_partial_startup_failure_closes_owned_mock(self):
        owned = make_mock('resolution', 0)
        with patch('evidence.demo.make_mock', return_value=owned), \
                patch('evidence.demo.make_evidence', side_effect=OSError('authored startup failure')):
            with self.assertRaises(OSError):
                with demo.rehearsal():
                    self.fail('Startup should fail')
        self.assertEqual(owned.socket.fileno(), -1)

    def test_invalid_external_origins_and_ports_fail_before_startup(self):
        for origin in ('https://example.com', 'http://127.0.0.1:8102/path',
                       'http://user:pass@127.0.0.1:8102', 'http://127.0.0.1:8102?key=synthetic',
                       'http://127.0.0.1:8102#fragment', 'http://localhost', 'http://localhost:bad'):
            with self.subTest(origin=origin), patch('evidence.demo.make_mock') as factory:
                with self.assertRaises(ValueError):
                    with demo.rehearsal(resolution_url=origin):
                        self.fail('Invalid origin was accepted')
                factory.assert_not_called()
        for port in (-1, 65536, True, '8101'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                with demo.rehearsal(port=port):
                    self.fail('Invalid port was accepted')
