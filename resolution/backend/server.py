"""Loopback-only merchant UI plus the internal frozen v1 resolution API. Fake PayPal only."""
import argparse
import copy
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

WEB = ROOT / 'resolution' / 'web'
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


def case_detail(store, case_id):
    """Merchant view of one case: the review plus the values an approval must bind to."""
    resolution, request = store.latest(case_id), store.request(case_id)
    if not resolution or not request:
        return None
    assessment, order = request['assessment'], request['order']
    return {'resolution': resolution, 'operation': store.operation(case_id),
            'remedy_conditions_met': request['remedy_conditions_met'],
            'assessment': {key: assessment[key] for key in ('assessment_id', 'decision', 'model', 'batch', 'reason', 'evidence', 'mode')},
            'binding': {'assessment_id': assessment['assessment_id'], 'campaign_version': assessment['campaign_version'],
                        'capture_id': order['capture_id'], 'amount_minor': resolution['proposed_amount_minor'],
                        'currency': order['currency']},
            'order': {key: order[key] for key in ('order_id', 'paid_minor', 'previously_refunded_minor', 'age_days', 'quantity')}}


def make_server(port=8102, db_path=None, adapter=None):
    store = CaseStore(db_path or ROOT / 'resolution' / '.local' / 'cases.sqlite3')
    adapter = adapter if adapter is not None else FakePayPal()
    demo_request = json.loads((ROOT / 'contracts' / 'fixtures' / 'resolution-request.json').read_text())

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass  # No bodies, identifiers, or secrets in access logs.

        def reply(self, code, body, content_type='application/json'):
            raw = json.dumps(body).encode() if content_type == 'application/json' else body
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def allowed_host(self):
            return len(self.headers.get_all('Host', [])) == 1 and self.headers.get('Host') in {
                f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def same_origin(self):
            # Browsers always send Origin on cross-origin POSTs, so a hostile page cannot omit it.
            # Non-browser callers (evidence service, tests) send none and stay allowed.
            origin = self.headers.get('Origin')
            port = self.server.server_port
            return origin is None or origin in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            if self.path in ASSETS:
                name, content_type = ASSETS[self.path]
                return self.reply(200, (WEB / name).read_bytes(), content_type)
            if self.path == '/health':
                return self.reply(200, {'service': 'resolution', 'mode': adapter.mode})
            if self.path == '/v1/cases':
                return self.reply(200, {'cases': store.list_cases()})
            for prefix, load in (('/v1/resolutions/', store.latest), ('/v1/cases/', lambda c: case_detail(store, c))):
                if self.path.startswith(prefix) and len(self.path) > len(prefix):
                    found = load(unquote(self.path[len(prefix):]))  # Read-only: a GET never refunds.
                    return self.reply(200, found) if found else self.reply(404, {'error': 'Not found'})
            self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            if not self.same_origin():
                return self.reply(403, {'error': 'Cross-origin requests are not allowed'})
            parts = self.path.strip('/').split('/')
            action = parts[3] if len(parts) == 4 and parts[:2] == ['v1', 'cases'] and parts[3] in ('approve', 'reconcile', 'remedy-conditions') else None
            if self.path not in ('/v1/resolutions', '/v1/demo/case') and not action:
                return self.reply(404, {'error': 'Not found'})
            try:
                takes_body = self.path == '/v1/resolutions' or action == 'approve'
                if takes_body and self.headers.get_content_type() != 'application/json':
                    return self.reply(415, {'error': 'Content-Type must be application/json'})
                size = int(self.headers.get('Content-Length', '0')) if takes_body else 0
                if takes_body and not 0 < size <= MAX_BODY_BYTES:
                    raise InvalidInput('Body size is outside the allowed range')
                body = strict_json(self.rfile.read(size)) if takes_body else None
                if action == 'approve':
                    response = approve(store, adapter, unquote(parts[2]), body)
                elif action == 'reconcile':
                    response = reconcile(store, adapter, unquote(parts[2]))
                elif action == 'remedy-conditions':
                    # Merchant-only action: the browser never supplies the flag itself.
                    request = store.request(unquote(parts[2]))
                    if not request:
                        return self.reply(404, {'error': 'Not found'})
                    request['remedy_conditions_met'] = True
                    response = store.save_review(request, review(request))
                elif self.path == '/v1/demo/case':
                    response = store.latest(demo_request['order']['case_id'])
                    if not response:
                        seed = copy.deepcopy(demo_request)
                        response = store.save_review(seed, review(seed))
                else:
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
    print(f'resolution on http://127.0.0.1:{args.port}; fake PayPal only, no money movement', flush=True)
    make_server(args.port, args.db).serve_forever()
