"""Run one local workspace for label assessment, merchant review and refunds.

Default: mock extraction, template briefs, fake payments; no credentials or network calls.
Opt-in live modes use the same workspace: AI label reading and AI briefs through existing
provider adapters, and refunds against the PayPal SANDBOX only (never live money)."""
import argparse
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading

from evidence.backend.server import make_server
from evidence.backend.validation import ROOT
from evidence.demo import DemoSession, running

READY_TIMEOUT = 10


def readiness_line(stream, result):
    """A blocking pipe read works on Windows; only the owning thread waits on it."""
    try:
        result.put(stream.readline(256))
    except (OSError, ValueError):
        result.put(b'')


# The merchant service owns its store and dependencies. It runs in a separate
# process; the customer application never imports it or opens its database.
MERCHANT = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from resolution.ai.brief import BriefService
from resolution.backend.paypal import FakePayPal, RefundUnknown
from resolution.backend.server import make_server
options = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}


class LoseFirstResponse:
    # Demo fault injection: the first refund really reaches the adapter, then its acknowledgement
    # is discarded. The case must stay pending and recover with the same operation ID.
    def __init__(self, inner):
        self.inner, self.lost = inner, False

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def refund(self, *args):
        refund_id = self.inner.refund(*args)
        if not self.lost:
            self.lost = True
            raise RefundUnknown('Acknowledgement deliberately discarded')
        return refund_id


try:
    adapter = FakePayPal()
    if options.get('paypal') == 'sandbox':
        from resolution.backend.paypal_sandbox import SandboxPayPal, load_credentials
        adapter = SandboxPayPal(*load_credentials(options.get('paypal_env')), **options.get('paypal_options', {}))
    if options.get('lose_first_refund_response'):
        adapter = LoseFirstResponse(adapter)
    provider = None
    if options.get('brief') == 'omniroute':
        from resolution.ai.omniroute import OmniRouteBrief, read_key
        provider = OmniRouteBrief(read_key(options.get('omniroute_env')), model=options['model'])
    elif options.get('brief') == 'gemini':
        from resolution.ai.gemini import GeminiBrief, read_key
        provider = GeminiBrief(read_key(options.get('gemini_env')), model=options['gemini_model'])
    server = make_server(int(sys.argv[3]), sys.argv[2], adapter, BriefService(provider))
except (OSError, ValueError, KeyError, TypeError):
    print(json.dumps({'error': 'configuration'}), flush=True)  # Never the secret or the provider message.
    sys.exit(2)
print(json.dumps({'port': server.server_port}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
"""


@contextmanager
def merchant_process(folder, port=0, options=None):
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP') if key in os.environ}
    process = subprocess.Popen(
        [sys.executable, '-I', '-B', '-u', '-c', MERCHANT, str(ROOT),
         str(folder / 'resolution.sqlite3'), str(port), json.dumps(options or {})], cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    lines = queue.Queue(maxsize=1)
    reader = threading.Thread(target=readiness_line, args=(process.stdout, lines), daemon=True)
    try:
        reader.start()
        try:
            line = lines.get(timeout=READY_TIMEOUT)
        except queue.Empty:
            raise RuntimeError('Merchant service did not start within the readiness deadline') from None
        try:
            started = json.loads(line)
            if isinstance(started, dict) and started.get('error') == 'configuration':
                raise RuntimeError('Merchant service rejected its PayPal or brief configuration; check the env files and model') from None
            selected = started['port']
            if type(selected) is not int or not 0 < selected <= 65535:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise RuntimeError('Merchant service could not start; check the port and lane dependencies') from None
        yield f'http://127.0.0.1:{selected}'
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if reader.ident is not None:
            reader.join(timeout=2)
        process.stdout.close()


def sandbox_order(path):
    """Payment fields of a case file written by resolution.sandbox.make_capture; the case ID stays this workspace's."""
    order = json.loads(Path(path).read_text())['order']
    return {key: order[key] for key in ('order_id', 'capture_id', 'paid_minor', 'previously_refunded_minor')}


@contextmanager
def integrated_session(port=0, merchant_port=0, *, workspace_port=0, extraction_adapter=None,
                       merchant_options=None, order=None, public_host=None, on_reset=None):
    for value in (port, merchant_port, workspace_port):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('Ports must be integers from 0 to 65535')
    options = dict(merchant_options or {})
    sandbox = options.get('paypal') == 'sandbox'
    if sandbox != (order is not None) or (order and order['capture_id'].startswith('capture-demo')):
        raise ValueError('PayPal sandbox refunds need a real sandbox capture, and only sandbox mode may use one')
    if public_host is not None and (sandbox or extraction_adapter is not None or options.get('brief', 'template') != 'template'
                                    or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', public_host)):
        # No login exists, so a public copy must never hold PayPal or model credentials.
        raise ValueError('A public host serves the mock demo only and must be a plain lowercase host name')
    with ExitStack() as cleanup:
        folder = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix='recallrelay-integrated-')))
        merchant = cleanup.enter_context(merchant_process(folder, merchant_port, options))
        customer = cleanup.enter_context(running(make_server(
            port, folder / 'evidence.sqlite3', merchant, extraction_adapter, enable_handoff=True, order=order,
            # Each merchant read starts a supervised helper process; a small shared host needs longer than a laptop.
            resolution_timeout=30 if public_host else 2)))
        from evidence.backend.workspace import make_workspace
        workspace = cleanup.enter_context(running(make_workspace(workspace_port, customer, merchant, {
            'lose_first_refund_response': bool(options.get('lose_first_refund_response'))}
            | ({'hosted': True} if public_host else {}), public_host, on_reset)))
        source = 'actual local service / ' + ('PayPal sandbox refunds' if sandbox else 'fake payments')
        yield DemoSession(customer, merchant, source, folder, workspace)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8101, help='Unified application port; 0 chooses an unused port')
    parser.add_argument('--merchant-port', type=int, default=0, help='Internal merchant port; normally selected automatically')
    parser.add_argument('--extractor', choices=('mock', 'omniroute'), default='mock',
                        help='omniroute sends an uploaded label photo to a model through your local OmniRoute gateway')
    parser.add_argument('--brief', choices=('template', 'omniroute', 'gemini'), default='template',
                        help='AI drafts the merchant brief; code validates it against case records or shows the template')
    parser.add_argument('--omniroute-env', type=Path, help='Existing env file holding OMNIROUTE_API_KEY (read, never executed)')
    parser.add_argument('--model', default='auto/smart', help='OmniRoute model for label reading and omniroute briefs')
    parser.add_argument('--gemini-env', type=Path, help='Existing env file holding GEMINI_API_KEY (read, never executed)')
    parser.add_argument('--gemini-model', help='Gemini model id; required with --brief gemini')
    parser.add_argument('--paypal', choices=('fake', 'sandbox'), default='fake',
                        help='sandbox sends real refunds to the PayPal SANDBOX only; no live-money mode exists')
    parser.add_argument('--paypal-env', type=Path, help='Existing env file holding PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET')
    parser.add_argument('--sandbox-case', type=Path,
                        help='Case file from "python -m resolution.sandbox.make_capture"; supplies the sandbox order and capture')
    parser.add_argument('--lose-first-refund-response', action='store_true',
                        help='Recovery demo: discard the first accepted refund acknowledgement so the case stays pending')
    parser.add_argument('--public-host', help='Hosted mock demo: also accept this host name behind a TLS proxy, on all interfaces. '
                                              'Mock label reading, template briefs and fake payments only')
    args = parser.parse_args()
    if (args.paypal == 'sandbox') != bool(args.sandbox_case) or (args.paypal_env and args.paypal != 'sandbox'):
        parser.error('--paypal sandbox needs --sandbox-case (and usually --paypal-env); neither is used with fake payments')
    if args.public_host and (args.extractor != 'mock' or args.brief != 'template' or args.paypal != 'fake'):
        parser.error('--public-host serves the mock demo only: no model or PayPal credentials on a public copy')
    if args.brief == 'gemini' and not args.gemini_model:
        parser.error('--brief gemini needs --gemini-model')
    adapter = order = None
    try:
        if args.extractor == 'omniroute':
            from evidence.ai.omniroute import OmniRouteExtractor, read_key
            adapter = OmniRouteExtractor(read_key(args.omniroute_env), model=args.model)
        if args.sandbox_case:
            order = sandbox_order(args.sandbox_case)
    except (OSError, ValueError, KeyError, TypeError):
        parser.error('Could not load the OmniRoute key/model or the sandbox case file')
    path = lambda value: str(value.resolve()) if value else None
    options = {'paypal': args.paypal, 'paypal_env': path(args.paypal_env), 'brief': args.brief,
               'omniroute_env': path(args.omniroute_env), 'model': args.model, 'gemini_env': path(args.gemini_env),
               'gemini_model': args.gemini_model, 'lose_first_refund_response': args.lose_first_refund_response}
    reset = threading.Event()  # Set only by the hosted demo's reset route; otherwise this waits for Ctrl+C.
    try:
        while True:
            reset.clear()
            with integrated_session(0, args.merchant_port, workspace_port=args.port, extraction_adapter=adapter,
                                    merchant_options=options, order=order, public_host=args.public_host,
                                    on_reset=reset.set if args.public_host else None) as session:
                print('RecallRelay: ' + (session.application_url or session.customer_url), flush=True)
                print('Label reading: ' + ('AI via OmniRoute, model ' + args.model if adapter else 'mock fixture lookup')
                      + '. Assessment: deterministic rules on confirmed text.', flush=True)
                print('Merchant brief: ' + ('AI via ' + args.brief + ', validated against case records' if args.brief != 'template' else 'template')
                      + '. Payments: ' + ('PayPal SANDBOX refunds, no live money' if order else 'fake, no money moves') + '.', flush=True)
                if args.lose_first_refund_response:
                    print('Fault injection ON: the first accepted refund acknowledgement is discarded to show recovery.', flush=True)
                print(f"One workspace: confirm label -> send for review -> confirm remedy -> approve {'sandbox' if order else 'fake'} refund -> refund status.", flush=True)
                print('Fresh temporary session. Ctrl+C stops the workspace and both services and removes rehearsal state.', flush=True)
                try:
                    reset.wait()
                except KeyboardInterrupt:
                    return
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error) if isinstance(error, RuntimeError) else 'Could not start the workspace; check dependencies and choose available ports')


if __name__ == '__main__':
    main()
