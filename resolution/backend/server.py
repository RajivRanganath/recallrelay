"""Loopback-only internal frozen v1 resolution API. Review only: no PayPal calls yet."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from resolution.backend.errors import InvalidInput
from resolution.backend.json_input import strict_json
from resolution.backend.paypal import FakePayPal
from resolution.backend.refund import approve, reconcile
from resolution.backend.review import review
from resolution.backend.store import AlreadyInProgress, ApprovalConflict, CaseStore
from resolution.backend.validation import MAX_BODY_BYTES, ROOT, validate_contract


def make_server(port=8102, db_path=None, adapter=None):
    store = CaseStore(db_path or ROOT / 'resolution' / '.local' / 'cases.sqlite3')
    adapter = adapter if adapter is not None else FakePayPal()

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass  # No bodies, identifiers, or secrets in access logs.

        def reply(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def allowed_host(self):
            return len(self.headers.get_all('Host', [])) == 1 and self.headers.get('Host') in {
                f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            if self.path == '/health':
                return self.reply(200, {'service': 'resolution', 'mode': 'mock'})
            prefix = '/v1/resolutions/'
            if self.path.startswith(prefix) and len(self.path) > len(prefix):
                found = store.latest(unquote(self.path[len(prefix):]))  # Read-only: a GET never refunds.
                return self.reply(200, found) if found else self.reply(404, {'error': 'Not found'})
            self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            parts = self.path.strip('/').split('/')
            action = parts[3] if len(parts) == 4 and parts[:2] == ['v1', 'cases'] and parts[3] in ('approve', 'reconcile') else None
            if self.path != '/v1/resolutions' and not action:
                return self.reply(404, {'error': 'Not found'})
            try:
                size = int(self.headers.get('Content-Length', '0')) if self.path == '/v1/resolutions' or action == 'approve' else 0
                if size and not 0 < size <= MAX_BODY_BYTES:
                    raise InvalidInput('Body size is outside the allowed range')
                body = strict_json(self.rfile.read(size)) if size else None
                if action == 'approve':
                    response = approve(store, adapter, unquote(parts[2]), body)
                elif action == 'reconcile':
                    response = reconcile(store, adapter, unquote(parts[2]))
                else:
                    if body is None:
                        raise InvalidInput('Body size is outside the allowed range')
                    validate_contract('resolution-request', body)
                    response = store.save_review(body, review(body))
                validate_contract('resolution-response', response)
                self.reply(200, response)
            except (AlreadyInProgress, ApprovalConflict) as error:
                self.reply(409, {'error': str(error)})
            except InvalidInput as error:
                self.reply(400, {'error': str(error)})
            except ValueError:
                self.reply(400, {'error': 'Invalid request'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8102)
    parser.add_argument('--db', default=os.environ.get('RESOLUTION_DB'))
    args = parser.parse_args()
    print(f'resolution on http://127.0.0.1:{args.port}; review only, no money movement', flush=True)
    make_server(args.port, args.db).serve_forever()
