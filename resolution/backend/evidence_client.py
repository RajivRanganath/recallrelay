"""HTTP boundary to the evidence service. No evidence imports or storage access."""
from http.client import HTTPException
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from resolution.backend.errors import InvalidInput
from resolution.backend.json_input import strict_json
from resolution.backend.validation import validate_contract

MAX_RESPONSE_BYTES = 65536


class EvidenceUnavailable(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class EvidenceClient:
    def __init__(self, base_url, timeout=5):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('EVIDENCE_BASE_URL must be an HTTP(S) origin without credentials')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def assess(self, assessment_request):
        """POST the approved campaign and order snapshot; return the validated assessment."""
        validate_contract('assessment-request', assessment_request)
        request = Request(f'{self.base_url}/v1/assessments', data=json.dumps(assessment_request).encode(),
                          headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise EvidenceUnavailable('Evidence did not return a complete assessment')
                if response.headers.get_content_type() != 'application/json':
                    raise EvidenceUnavailable('Evidence returned a non-JSON response')
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not 0 < len(raw) <= MAX_RESPONSE_BYTES:
                raise EvidenceUnavailable('Invalid evidence response length')
            data = strict_json(raw)
            validate_contract('assessment-response', data)
            if data['case_id'] != assessment_request['order']['case_id']:
                raise EvidenceUnavailable('Evidence returned a different case')
            campaign = assessment_request['campaign']
            if (data['campaign_id'] != campaign['campaign_id']
                    or data['campaign_version'] != campaign['version']):
                raise EvidenceUnavailable('Evidence returned a different campaign snapshot')
            return data
        except HTTPError as error:
            error.close()
            raise EvidenceUnavailable('Evidence service returned an error') from None
        except (URLError, TimeoutError, OSError, ValueError, HTTPException, InvalidInput):
            raise EvidenceUnavailable('Evidence assessment could not be read or validated') from None
