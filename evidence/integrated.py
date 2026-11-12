"""Run one local workspace for label assessment, merchant review and fake refunds."""
import argparse
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import queue
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
    lines = queue.Queue(maxsize=1)
    reader = threading.Thread(target=readiness_line, args=(process.stdout, lines), daemon=True)
    try:
        reader.start()
        try:
            line = lines.get(timeout=READY_TIMEOUT)
        except queue.Empty:
            raise RuntimeError('Merchant service did not start within the readiness deadline') from None
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
        if reader.ident is not None:
            reader.join(timeout=2)
        process.stdout.close()


@contextmanager
def integrated_session(port=0, merchant_port=0, *, workspace_port=0):
    for value in (port, merchant_port, workspace_port):
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('Ports must be integers from 0 to 65535')
    with ExitStack() as cleanup:
        folder = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix='recallrelay-integrated-')))
        merchant = cleanup.enter_context(merchant_process(folder, merchant_port))
        customer = cleanup.enter_context(running(make_server(
            port, folder / 'evidence.sqlite3', merchant, enable_handoff=True)))
        from evidence.backend.workspace import make_workspace
        workspace = cleanup.enter_context(running(make_workspace(workspace_port, customer, merchant)))
        yield DemoSession(customer, merchant, 'actual local service / fake payments', folder, workspace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8101, help='Unified application port; 0 chooses an unused port')
    parser.add_argument('--merchant-port', type=int, default=0, help='Internal merchant port; normally selected automatically')
    args = parser.parse_args()
    try:
        with integrated_session(0, args.merchant_port, workspace_port=args.port) as session:
            print('RecallRelay: ' + (session.application_url or session.customer_url), flush=True)
            print('Synthetic only. Mock extraction, deterministic assessment, template briefs, fake payments.', flush=True)
            print('One workspace: confirm label -> send for review -> confirm remedy -> approve fake refund -> refund status.', flush=True)
            print('Fresh temporary session. Ctrl+C stops the workspace and both services and removes rehearsal state.', flush=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError, RuntimeError):
        parser.error('Could not start the workspace; check dependencies and choose available ports')


if __name__ == '__main__':
    main()
