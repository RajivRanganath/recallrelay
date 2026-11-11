"""Run both synthetic apps with explicit HTTP handoff and fake payments only."""
import argparse
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import threading

from evidence.backend.server import make_server
from evidence.backend.validation import ROOT
from evidence.demo import DemoSession, running


# The merchant service owns its store and dependencies. It runs in a separate
# process; the customer application never imports it or opens its database.
MERCHANT = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from resolution.backend.server import make_server
server = make_server(int(sys.argv[3]), sys.argv[2])
print(json.dumps({'port': server.server_port}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
"""


@contextmanager
def merchant_process(folder, port=0):
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'TEMP', 'TMP') if key in os.environ}
    process = subprocess.Popen(
        [sys.executable, '-I', '-B', '-u', '-c', MERCHANT, str(ROOT),
         str(folder / 'resolution.sqlite3'), str(port)], cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=10):
                raise RuntimeError('Merchant service did not start within ten seconds')
            line = process.stdout.readline(256)
        try:
            selected = json.loads(line)['port']
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
        process.stdout.close()


@contextmanager
def integrated_session(port=0, merchant_port=0):
    for value in (port, merchant_port):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('Ports must be integers from 0 to 65535')
    with ExitStack() as cleanup:
        folder = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix='recallrelay-integrated-')))
        merchant = cleanup.enter_context(merchant_process(folder, merchant_port))
        customer = cleanup.enter_context(running(make_server(
            port, folder / 'evidence.sqlite3', merchant, enable_handoff=True)))
        yield DemoSession(customer, merchant, 'actual local service / fake payments', folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8101)
    parser.add_argument('--merchant-port', type=int, default=8102)
    args = parser.parse_args()
    try:
        with integrated_session(args.port, args.merchant_port) as session:
            print('Customer: ' + session.customer_url, flush=True)
            print('Merchant: ' + session.resolution_url, flush=True)
            print('Synthetic only. Mock extraction, deterministic assessment, template briefs, fake payments.', flush=True)
            print('Confirm label → check match → send for merchant review → open merchant → confirm remedy → approve fake refund → refresh customer status.', flush=True)
            print('Fresh separate temporary stores. Ctrl+C stops both apps and removes rehearsal state.', flush=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError, RuntimeError):
        parser.error('Could not start both apps; check dependencies and choose two available ports')


if __name__ == '__main__':
    main()
