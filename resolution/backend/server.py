"""Loopback-only merchant UI plus the internal frozen v1 resolution API. Fake PayPal only."""
import argparse
import copy
import io
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote

from resolution.ai.brief import BriefService
from resolution.ai.gemini import GeminiBrief, read_key as read_gemini_key
from resolution.ai.omniroute import OmniRouteBrief, read_key
from resolution.backend.errors import InvalidInput
from resolution.backend.intake import BoundedThreadingHTTPServer, DeadlineReader, ReceiveDeadline
from resolution.backend.json_input import strict_json
from resolution.backend.paypal import FakePayPal, RefundUnknown
from resolution.backend.paypal_sandbox import SandboxPayPal, load_credentials
from resolution.backend.refund import apply_webhook, approve, reconcile
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
            'assessment': {key: assessment[key] for key in ('assessment_id', 'decision', 'model', 'batch', 'reason', 'evidence', 'mode', 'missing_fields', 'clarification')},
            'binding': {'assessment_id': assessment['assessment_id'], 'campaign_version': assessment['campaign_version'],
                        'capture_id': order['capture_id'], 'amount_minor': resolution['proposed_amount_minor'],
                        'currency': order['currency']},
            'order': {key: order[key] for key in ('order_id', 'paid_minor', 'previously_refunded_minor', 'age_days', 'quantity')}}


PUBLIC_HOST = re.compile(r'(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')
PUBLIC_WEBHOOK_PATH = '/v1/paypal/webhook'
MAX_PUBLIC_WINDOW_SECONDS = 7200
PUBLIC_DENIED = {'error': 'Not available on the public host'}
RECEIVE_SECONDS = 10      # Total time allowed to receive one whole request (line, headers and body).
MAX_CONNECTIONS = 32      # Simultaneous handler threads; further connections are closed at once.
MAX_PUBLIC_HANDLERS = 4   # Simultaneous public webhook calls (each waits on PayPal); more get 503.
INCOMPLETE = object()     # read_body result: the body did not arrive inside the receive budget.


def public_host_name(value):
    """A plain DNS name (no scheme, port, path, IP address or localhost) for the one temporary public host."""
    host = value.strip().lower() if isinstance(value, str) else ''
    if not PUBLIC_HOST.fullmatch(host) or host.endswith('.localhost'):
        raise ValueError('The public host must be a plain DNS name such as abc-def.example.com')
    return host


def make_server(port=8102, db_path=None, adapter=None, brief=None, webhook_id=None,
                public_host=None, public_window_seconds=1800, receive_seconds=RECEIVE_SECONDS, max_connections=MAX_CONNECTIONS):
    """`public_host` is for a temporary, explicitly approved sandbox webhook test (docs/vismaya/WEBHOOK-EXCEPTION.md).

    Requests whose Host header equals it may reach ONLY `POST /v1/paypal/webhook`, and only until the window
    closes; everything else on that host is refused before any handler runs. Without it, any non-loopback
    Host is refused exactly as before.
    """
    if public_host is not None:
        public_host = public_host_name(public_host)
        if not webhook_id or not hasattr(adapter, 'verify_webhook'):
            raise ValueError('A public host needs a webhook ID and an adapter that can verify webhooks')
        if not 0 < public_window_seconds <= MAX_PUBLIC_WINDOW_SECONDS:
            raise ValueError('The public window must be between 1 second and 2 hours')
    if not 0 < receive_seconds <= 60 or not 1 <= max_connections <= 256:
        raise ValueError('The receive budget must be 0-60 seconds and the connection cap 1-256')
    public_deadline = time.monotonic() + public_window_seconds
    public_slots = threading.BoundedSemaphore(MAX_PUBLIC_HANDLERS)
    store = CaseStore(db_path or ROOT / 'resolution' / '.local' / 'cases.sqlite3')
    adapter = adapter if adapter is not None else FakePayPal()
    brief = brief if brief is not None else BriefService()
    demo_request = json.loads((ROOT / 'contracts' / 'fixtures' / 'resolution-request.json').read_text())

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def setup(self):
            super().setup()
            # One total budget for receiving the request, not just a per-wait timeout (see intake.py).
            self.receive = ReceiveDeadline(self.connection, receive_seconds, self.timeout)
            self.rfile.close()
            self.rfile = io.BufferedReader(DeadlineReader(self.connection, self.receive))

        def parse_request(self):
            parsed = super().parse_request()
            if parsed and self.receive.timed_out:
                # The budget ran out while the request was still arriving. The reader reports that as end of input and
                # the header parser accepts it, so a half-received request would look complete. Refuse it here,
                # before anything is dispatched to a route.
                return self.refuse_unfinished()
            return parsed

        def refuse_unfinished(self):
            self.receive.complete()
            self.close_connection = True
            self.reply(408, {'error': 'The request was not received in time'})
            return False

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

        def reject_public(self):
            """Refuse a public-host request from its headers alone, without waiting for any body.

            The reply goes out first. Then whatever the sender already sent is discarded for at most half a second,
            bounded in bytes too, so closing does not reset the connection and lose the reply."""
            self.receive.complete()
            self.close_connection = True
            self.reply(403, PUBLIC_DENIED)
            try:
                self.connection.shutdown(socket.SHUT_WR)
                end, left = time.monotonic() + 0.5, MAX_BODY_BYTES
                while left > 0 and time.monotonic() < end:
                    self.connection.settimeout(max(end - time.monotonic(), 0.01))
                    chunk = self.connection.recv(min(left, 65536))
                    if not chunk:
                        break
                    left -= len(chunk)
            except OSError:
                pass

        def public_request(self):
            """True only for the one configured public host, matched exactly (no port, one Host header)."""
            hosts = self.headers.get_all('Host', [])
            return public_host is not None and len(hosts) == 1 and hosts[0].lower() == public_host

        def same_origin(self):
            # Browsers always send Origin on cross-origin POSTs, so a hostile page cannot omit it.
            # Non-browser callers (evidence service, tests) send none and stay allowed.
            origin = self.headers.get('Origin')
            port = self.server.server_port
            return origin is None or origin in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}

        def do_GET(self):
            if self.receive.timed_out:  # Also checked in parse_request; never serve a request cut off by the budget.
                return self.refuse_unfinished()
            self.receive.complete()  # A GET has no body to wait for.
            if self.public_request():  # The public host serves the webhook POST only; no page, case or health data.
                return self.reject_public()
            if not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            if self.path in ASSETS:
                name, content_type = ASSETS[self.path]
                return self.reply(200, (WEB / name).read_bytes(), content_type)
            if self.path == '/health':
                return self.reply(200, {'service': 'resolution', 'mode': adapter.mode, 'brief': 'ai' if brief.provider else 'template'})
            if self.path == '/v1/cases':
                return self.reply(200, {'cases': store.list_cases()})
            for prefix, load in (('/v1/resolutions/', store.latest), ('/v1/cases/', lambda c: case_detail(store, c))):
                if self.path.startswith(prefix) and len(self.path) > len(prefix):
                    found = load(unquote(self.path[len(prefix):]))  # Read-only: a GET never refunds.
                    return self.reply(200, found) if found else self.reply(404, {'error': 'Not found'})
            self.reply(404, {'error': 'Not found'})

        def read_body(self):
            """Always consume the declared body (bounded) before any reply, so early rejections
            (403/404/415) never close the socket with unread data, which resets the client."""
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = -1
            if not 0 <= size <= MAX_BODY_BYTES:
                self.close_connection = True  # Cannot safely drain an unbounded or malformed body.
                self.receive.complete()
                return None
            data = self.rfile.read(size)
            self.receive.complete()
            if len(data) != size:  # The total receive budget ran out, or the sender hung up, before the body arrived.
                self.close_connection = True
                return INCOMPLETE
            return data

        def webhook(self, raw):
            public = self.public_request()
            if public and not public_slots.acquire(blocking=False):
                return self.reply(503, {'error': 'Busy; try again later'})
            try:
                return self._webhook(raw)
            finally:
                if public:
                    public_slots.release()

        def _webhook(self, raw):
            """PayPal event receiver. Off unless a webhook ID is configured. Unverified events change nothing,
            and a verified one only settles a pending refund after PayPal confirms it by a direct read."""
            if not webhook_id or not hasattr(adapter, 'verify_webhook'):
                return self.reply(404, {'error': 'Not found'})
            if self.headers.get_content_type() != 'application/json' or not raw:
                return self.reply(400, {'error': 'A JSON event body is required'})
            try:
                verified = adapter.verify_webhook({k.lower(): v for k, v in self.headers.items()}, raw, webhook_id)
            except RefundUnknown:
                return self.reply(503, {'error': 'Could not verify the event with PayPal; try again'})
            if not verified:
                return self.reply(401, {'error': 'Event could not be verified'})
            try:
                event = strict_json(raw)
            except InvalidInput:
                return self.reply(400, {'error': 'Invalid event'})
            return self.reply(200, {'accepted': True, 'settled': apply_webhook(store, adapter, event) is not None})

        def do_POST(self):
            if self.receive.timed_out:  # Also checked in parse_request; never act on a request cut off by the budget.
                return self.refuse_unfinished()
            if self.public_request() and (self.path != PUBLIC_WEBHOOK_PATH or time.monotonic() >= public_deadline):
                return self.reject_public()  # Decided from the headers alone: the body is never waited for.
            raw = self.read_body()
            if raw is INCOMPLETE:
                return self.reply(408, {'error': 'The request was not received in time'})
            if raw is None:
                return self.reply(400, {'error': 'Body size is outside the allowed range'})
            if self.public_request():
                # Exact path only (no query string), and only while the approved window is open.
                if self.path != PUBLIC_WEBHOOK_PATH or time.monotonic() >= public_deadline:
                    return self.reply(403, PUBLIC_DENIED)
            elif not self.allowed_host():
                return self.reply(403, {'error': 'Loopback Host required'})
            if not self.same_origin():
                return self.reply(403, {'error': 'Cross-origin requests are not allowed'})
            parts = self.path.strip('/').split('/')
            action = parts[3] if len(parts) == 4 and parts[:2] == ['v1', 'cases'] and parts[3] in ('approve', 'reconcile', 'remedy-conditions', 'brief') else None
            if self.path == PUBLIC_WEBHOOK_PATH:
                return self.webhook(raw)
            if self.path not in ('/v1/resolutions', '/v1/demo/case') and not action:
                return self.reply(404, {'error': 'Not found'})
            try:
                takes_body = self.path == '/v1/resolutions' or action == 'approve'
                if takes_body and self.headers.get_content_type() != 'application/json':
                    return self.reply(415, {'error': 'Content-Type must be application/json'})
                if takes_body and not raw:
                    raise InvalidInput('Body size is outside the allowed range')
                body = strict_json(raw) if takes_body else None
                if action == 'brief':  # Advisory text only: changes nothing and never touches the adapter.
                    detail = case_detail(store, unquote(parts[2]))
                    return self.reply(200, brief.brief(detail)) if detail else self.reply(404, {'error': 'Not found'})
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

    return BoundedThreadingHTTPServer(('127.0.0.1', port), Handler, max_connections)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8102)
    parser.add_argument('--db', default=os.environ.get('RESOLUTION_DB'))
    parser.add_argument('--paypal', choices=('fake', 'sandbox'), default='fake',
                        help='sandbox sends real refunds to the PayPal SANDBOX only; fake never leaves this process')
    parser.add_argument('--paypal-env', help='Existing env file holding PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (read, never executed)')
    parser.add_argument('--paypal-webhook-id', help='Turns on POST /v1/paypal/webhook for events of this PayPal sandbox webhook (needs --paypal sandbox)')
    parser.add_argument('--paypal-webhook-public-host', help='TEMPORARY, approved sandbox test only (docs/vismaya/WEBHOOK-EXCEPTION.md): the one public DNS name '
                        'of a tunnel. That host can reach only POST /v1/paypal/webhook, for a limited window. Needs --paypal sandbox and --paypal-webhook-id')
    parser.add_argument('--paypal-webhook-window-minutes', type=int, default=30,
                        help='How long the public host is served after startup (1-120, default 30)')
    parser.add_argument('--brief', choices=('template', 'omniroute', 'gemini'), default='template',
                        help='omniroute (local gateway) or gemini (Google API) drafts the merchant brief; output is validated or replaced by the template')
    parser.add_argument('--omniroute-env', help='Existing env file holding OMNIROUTE_API_KEY (read, never executed)')
    parser.add_argument('--omniroute-model', default='auto/smart')
    parser.add_argument('--gemini-env', help='Existing env file holding GEMINI_API_KEY (read, never executed)')
    parser.add_argument('--gemini-model', help='Gemini model id; required with --brief gemini')
    args = parser.parse_args()
    adapter = None
    if args.paypal == 'sandbox':
        try:
            adapter = SandboxPayPal(*load_credentials(args.paypal_env))
        except (OSError, ValueError):
            parser.error('Could not load PayPal sandbox credentials; check PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET or --paypal-env')
    elif args.paypal_env or args.paypal_webhook_id or args.paypal_webhook_public_host:
        parser.error('--paypal-env, --paypal-webhook-id and --paypal-webhook-public-host need --paypal sandbox')
    public_host = None
    if args.paypal_webhook_public_host is not None:
        if not args.paypal_webhook_id:
            parser.error('--paypal-webhook-public-host needs --paypal-webhook-id')
        if not 1 <= args.paypal_webhook_window_minutes <= MAX_PUBLIC_WINDOW_SECONDS // 60:
            parser.error('--paypal-webhook-window-minutes must be between 1 and 120')
        try:
            public_host = public_host_name(args.paypal_webhook_public_host)
        except ValueError as error:
            parser.error(str(error))
    provider = None
    if args.brief == 'omniroute':
        try:
            provider = OmniRouteBrief(read_key(args.omniroute_env), model=args.omniroute_model)
        except (OSError, ValueError):
            parser.error('Could not load the OmniRoute configuration; check OMNIROUTE_API_KEY or --omniroute-env and the model')
    elif args.brief == 'gemini':
        if not args.gemini_model:
            parser.error('--brief gemini needs --gemini-model')
        try:
            provider = GeminiBrief(read_gemini_key(args.gemini_env), model=args.gemini_model)
        except (OSError, ValueError):
            parser.error('Could not load the Gemini configuration; check GEMINI_API_KEY or --gemini-env and the model id')
    if args.omniroute_env and args.brief != 'omniroute':
        parser.error('--omniroute-env needs --brief omniroute')
    if (args.gemini_env or args.gemini_model) and args.brief != 'gemini':
        parser.error('--gemini-env and --gemini-model need --brief gemini')
    note = 'PayPal SANDBOX refunds (no live money)' if adapter else 'fake PayPal only, no money movement'
    print(f'resolution on http://127.0.0.1:{args.port}; {note}; brief: {"AI via " + provider.name + " (validated)" if provider else "template"}', flush=True)
    if public_host:
        print(f'TEMPORARY PUBLIC HOST: {public_host} may reach ONLY POST {PUBLIC_WEBHOOK_PATH} for {args.paypal_webhook_window_minutes} minutes. '
              'Stop the tunnel and delete the webhook when the test is over.', flush=True)
    make_server(args.port, args.db, adapter, BriefService(provider), args.paypal_webhook_id,
                public_host, args.paypal_webhook_window_minutes * 60).serve_forever()
