"""Read-only HTTP boundary. No resolution imports, storage access or payment calls."""
import math
import multiprocessing
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from evidence.backend.validation import validate_contract
from evidence.backend.json_input import strict_json

MAX_RESPONSE_BYTES = 65536


class ResolutionUnavailable(RuntimeError):
    pass


class ResolutionNotFound(ResolutionUnavailable):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _status_worker(pipe, url, timeout):
    """Return bounded bytes or a sanitized failure; never log upstream bodies."""
    try:
        request = Request(url, headers={'Accept': 'application/json'}, method='GET')
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError()
            if (len(response.headers.get_all('Content-Type', [])) != 1
                    or response.headers.get_content_type() != 'application/json'):
                raise ValueError()
            lengths = response.headers.get_all('Content-Length', [])
            transfers = response.headers.get_all('Transfer-Encoding', [])
            if (len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers)
                    or (transfers and transfers[0].strip().lower() != 'chunked')):
                raise ValueError()
            if lengths and (not lengths[0].isascii() or not lengths[0].isdigit()
                            or not 0 < int(lengths[0]) <= MAX_RESPONSE_BYTES):
                raise ValueError()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES or (lengths and len(raw) != int(lengths[0])):
                raise ValueError()
        pipe.send((raw, None))
    except Exception as error:
        failure = 'not_found' if isinstance(error, HTTPError) and error.code == 404 else 'unavailable'
        if isinstance(error, HTTPError):
            error.close()
        try:
            pipe.send((None, failure))
        except (BrokenPipeError, OSError):
            pass
    finally:
        pipe.close()


class ResolutionClient:
    def __init__(self, base_url, timeout=2):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('RESOLUTION_BASE_URL must be an HTTP(S) origin without credentials')
        parsed.port  # Reject malformed ports before starting a worker.
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 0 < timeout <= 35):
            raise ValueError('Timeout must be greater than zero and at most 35 seconds')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self._slots = threading.BoundedSemaphore(2)

    def get_status(self, case_id):
        if not self._slots.acquire(blocking=False):
            raise ResolutionUnavailable('Resolution status is busy; try again later')
        process = receive = send = None
        try:
            # Socket inactivity timeouts alone cannot stop trickling headers/bodies
            # or stalled name resolution. Supervise the entire HTTP read instead.
            deadline = time.monotonic() + self.timeout
            context = multiprocessing.get_context('spawn')
            receive, send = context.Pipe(duplex=False)
            process = context.Process(target=_status_worker,
                                      args=(send, f'{self.base_url}/v1/resolutions/{quote(case_id, safe="")}', self.timeout),
                                      daemon=True)
            process.start()
            send.close()
            if not receive.poll(max(0, deadline - time.monotonic())):
                raise ResolutionUnavailable('Resolution status exceeded the local wait limit')
            raw, failure = receive.recv()
            if failure == 'not_found':
                raise ResolutionNotFound('No resolution record exists for this case')
            if failure:
                raise ResolutionUnavailable('Resolution status could not be read or validated')
            data = strict_json(raw)
            validate_contract('resolution-response', data)
            if data['case_id'] != case_id:
                raise ResolutionUnavailable('Resolution returned a different case')
            return data
        except ResolutionUnavailable:
            raise
        except Exception:
            raise ResolutionUnavailable('Resolution status could not be read or validated') from None
        finally:
            if process is not None and process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()
            for connection in (receive, send):
                if connection is not None:
                    connection.close()
            self._slots.release()
