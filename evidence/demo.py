"""Start a fresh local customer rehearsal with mock extraction and no providers."""
import argparse
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass, field
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit

from evidence.ai.fixture_extractor import FixtureExtractor
from evidence.backend.server import make_server as make_evidence
from scripts.mock_server import make_server as make_mock


@dataclass(frozen=True)
class DemoSession:
    customer_url: str
    resolution_url: str
    resolution_source: str
    state_directory: Path = field(repr=False)


@contextmanager
def running(server):
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
    try:
        worker.start()
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        if worker.ident is not None:
            server.shutdown()
            worker.join()
        server.server_close()


def local_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or not parsed.port or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Resolution must be an explicit loopback HTTP origin')
    return value.rstrip('/')


@contextmanager
def rehearsal(port=0, resolution_url=None):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('Port must be between 0 and 65535')
    upstream = local_origin(resolution_url) if resolution_url is not None else None
    with ExitStack() as cleanup:
        folder = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix='recallrelay-demo-')))
        source = 'external service' if upstream else 'committed resolution mock'
        if upstream is None:
            upstream = cleanup.enter_context(running(make_mock('resolution', 0)))
        customer = cleanup.enter_context(running(make_evidence(
            port, folder / 'assessments.sqlite3', upstream, extraction_adapter=FixtureExtractor())))
        yield DemoSession(customer, upstream, source, folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='Customer port; 0 selects an unused port')
    parser.add_argument('--resolution-url', help='Optional already-running loopback resolution origin')
    args = parser.parse_args()
    try:
        with rehearsal(args.port, args.resolution_url) as session:
            print('RecallRelay synthetic customer rehearsal: ' + session.customer_url, flush=True)
            print('Extraction: mock fixture lookup. Assessment: confirmed text + rules.', flush=True)
            print('Resolution: ' + session.resolution_source + ' at ' + session.resolution_url, flush=True)
            if session.resolution_source == 'committed resolution mock':
                print('Merchant status is a separate canned fixture; no handoff or payment occurs.', flush=True)
            else:
                print('Only status GETs use the selected service; this launcher creates no merchant case.', flush=True)
            print('Fresh temporary evidence storage. Ctrl+C stops the rehearsal and removes it.', flush=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
    except (OSError, ValueError):
        parser.error('Could not start rehearsal; use an available port and a loopback resolution origin')


if __name__ == '__main__':
    main()
