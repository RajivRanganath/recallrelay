"""One-origin workflow, explicit approval and restricted local HTTP routing."""
import copy
import http.client
import json
import socket
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from evidence.backend.workspace import make_workspace
from evidence.demo import running
from evidence.integrated import integrated_session
from test_assessment import fixture
from test_resolution_integration import call


class WorkspaceTests(unittest.TestCase):
    def test_same_origin_assessment_review_approval_and_customer_outcome(self):
        with integrated_session() as session:
            app = session.application_url
            self.assertNotIn(app, (session.customer_url, session.resolution_url))
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1')[0], 404)
            saved = call(app, '/api/customer/demo/assessments', {'label': fixture()['label']})[1]
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1')[0], 404)
            result = call(app, '/api/customer/demo/handoff', {'assessment_id': saved['assessment_id']})
            self.assertEqual((result[0], result[1]['status']), (200, 'manual_required'))
            detail = call(app, '/api/merchant/v1/cases/case-demo-1')[1]
            self.assertEqual(detail['assessment']['assessment_id'], saved['assessment_id'])
            self.assertFalse(detail['remedy_conditions_met'])
            binding = {key: value for key, value in detail['binding'].items() if key != 'currency'}
            binding['approved_by'] = 'synthetic-reviewer'
            binding['amount_minor'] = 4000
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1/approve', binding)[0], 409)
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1/brief', {})[1]['source'], 'template')
            self.assertFalse(call(app, '/api/merchant/v1/cases/case-demo-1')[1]['remedy_conditions_met'])
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1/remedy-conditions', {})[1]['status'], 'awaiting_approval')
            binding['amount_minor'] = 3999
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1/approve', binding)[0], 409)
            binding['amount_minor'] = 4000
            done = call(app, '/api/merchant/v1/cases/case-demo-1/approve', binding)
            self.assertEqual((done[0], done[1]['status'], done[1]['mode']), (200, 'refunded', 'mock'))
            self.assertEqual(call(app, '/api/customer/demo/resolution-status'), done)
            self.assertEqual(call(app, '/api/merchant/v1/cases/case-demo-1/approve', binding), done)
            self.assertEqual(call(app, '/api/customer/v1/assessments/case-demo-1'), (200, saved))
        with self.assertRaises((URLError, OSError)):
            urlopen(app + '/', timeout=1)
        self.assertFalse(session.state_directory.exists())

    def test_missing_and_excluded_cannot_bypass_conditions_via_workspace(self):
        for batch, expected in [('', 'needs_information'), ('B103', 'excluded')]:
            with self.subTest(batch=batch), integrated_session() as session:
                label = copy.deepcopy(fixture()['label']); label['confirmed_batch'] = batch
                app = session.application_url
                saved = call(app, '/api/customer/demo/assessments', {'label': label})[1]
                result = call(app, '/api/customer/demo/handoff', {'assessment_id': saved['assessment_id']})[1]
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['proposed_amount_minor'], 0)
                detail = call(app, '/api/merchant/v1/cases/case-demo-1')[1]
                self.assertIsNone(detail['operation'])

    def test_only_owned_routes_no_seeder_webhook_arbitrary_target_or_query(self):
        with integrated_session() as session:
            app = session.application_url
            for path in ('/api/merchant/v1/cases', '/api/merchant/v1/paypal/webhook',
                         '/api/merchant/v1/demo/case', '/api/customer/../health',
                         '/api/merchant/health?target=http://example.com',
                         '/api/customer/v1/assessments/%2e%2e', '/api/elsewhere/health'):
                self.assertEqual(call(app, path)[0], 404, path)
            self.assertEqual(call(app, '/api/merchant/v1/demo/case', {})[0], 404)
            self.assertEqual(call(app, '/api/merchant/v1/paypal/webhook', {})[0], 404)

    def test_foreign_and_duplicate_host_origin_or_body_framing_rejected(self):
        with integrated_session() as session:
            port = int(session.application_url.rsplit(':', 1)[1])
            cases = [([('Host', 'external.invalid')], b'{}', 403),
                     ([('Host', f'127.0.0.1:{port}'), ('Origin', 'https://foreign.invalid')], b'{}', 403),
                     ([('Host', f'127.0.0.1:{port}'), ('Host', f'127.0.0.1:{port}')], b'{}', 403),
                     ([('Host', f'127.0.0.1:{port}'), ('Content-Length', '2')], b'{}', 400),
                     ([('Host', f'127.0.0.1:{port}'), ('Transfer-Encoding', 'chunked')], b'{}', 400)]
            for headers, body, expected in cases:
                with self.subTest(headers=headers):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                    try:
                        connection.putrequest('POST', '/api/customer/demo/handoff', skip_host=True)
                        for name, value in headers: connection.putheader(name, value)
                        connection.putheader('Content-Type', 'application/json')
                        connection.putheader('Content-Length', str(len(body)))
                        connection.endheaders(body)
                        response = connection.getresponse(); response.read()
                        self.assertEqual(response.status, expected)
                    finally:
                        connection.close()

    def test_partial_headers_do_not_dispatch_and_truncated_body_is_rejected(self):
        server = make_workspace(0, 'http://127.0.0.1:1', 'http://127.0.0.1:1')
        server.request_timeout = .15
        with running(server):
            port = server.server_port
            with socket.create_connection(('127.0.0.1', port), timeout=2) as peer:
                peer.sendall(f'POST /api/customer/demo/handoff HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: 2\r\n'.encode())
                self.assertIn(b' 408 ', peer.recv(4096))
            with socket.create_connection(('127.0.0.1', port), timeout=2) as peer:
                peer.sendall(f'POST /api/customer/demo/handoff HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n{{}}'.encode())
                peer.shutdown(socket.SHUT_WR)
                self.assertIn(b' 400 ', peer.recv(4096))

    def test_static_workspace_has_one_navigation_no_embedded_old_apps(self):
        with integrated_session() as session:
            for path, mime in [('/', 'text/html'), ('/workspace.js', 'text/javascript'), ('/workspace.css', 'text/css')]:
                with urlopen(session.application_url + path) as response:
                    raw = response.read().decode()
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.headers['Content-Type'].startswith(mime))
                    self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
                    if path == '/':
                        self.assertIn('id="view-review"', raw)
                        self.assertIn('id="view-status"', raw)
                        self.assertNotIn('<iframe', raw)
                        self.assertNotIn('target="_blank"', raw)

    def test_unavailable_upstream_is_visible_without_forwarding_credentials(self):
        with running(make_workspace(0, 'http://127.0.0.1:1', 'http://127.0.0.1:1')) as app:
            self.assertEqual(call(app, '/api/customer/health')[0], 503)
        with self.assertRaises(ValueError):
            make_workspace(0, 'https://outside.invalid', 'http://127.0.0.1:1')


if __name__ == '__main__':
    unittest.main()
