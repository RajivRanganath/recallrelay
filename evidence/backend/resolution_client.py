"""Read-only HTTP boundary. No resolution imports, storage access or payment calls."""
from http.client import HTTPException
from urllib.error import HTTPError, URLError
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


class ResolutionClient:
    def __init__(self, base_url, timeout=2):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('RESOLUTION_BASE_URL must be an HTTP(S) origin without credentials')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def get_status(self, case_id):
        request = Request(f'{self.base_url}/v1/resolutions/{quote(case_id, safe="")}',
                          headers={'Accept': 'application/json'}, method='GET')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise ResolutionUnavailable('Resolution did not return a complete status')
                if response.headers.get_content_type() != 'application/json':
                    raise ResolutionUnavailable('Resolution returned a non-JSON response')
                length = response.headers.get('Content-Length')
                if length is not None and not 0 < int(length) <= MAX_RESPONSE_BYTES:
                    raise ResolutionUnavailable('Invalid resolution response length')
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if length is not None and len(raw) != int(length):
                    raise ResolutionUnavailable('Resolution response was truncated')
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ResolutionUnavailable('Resolution response exceeded the limit')
            data = strict_json(raw)
            validate_contract('resolution-response', data)
            if data['case_id'] != case_id:
                raise ResolutionUnavailable('Resolution returned a different case')
            return data
        except HTTPError as error:
            code = error.code
            error.close()
            if code == 404:
                raise ResolutionNotFound('No resolution record exists for this case') from None
            raise ResolutionUnavailable('Resolution service returned an error') from None
        except (URLError, TimeoutError, OSError, ValueError, HTTPException):
            raise ResolutionUnavailable('Resolution status could not be read or validated') from None
