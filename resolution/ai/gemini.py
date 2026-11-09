"""Opt-in text provider that calls Google's Gemini API directly. Never imports the evidence lane.

The key travels only in a request header (never in a URL), the host is fixed to Google (a loopback stub is
allowed for tests), redirects are refused, and upstream bodies or errors never reach callers: they become
short codes so the brief service can fall back to the template.
"""
import json
import math
import re
import threading
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from resolution.ai.errors import BriefUnavailable
from resolution.backend.envfile import read_secrets
from resolution.backend.json_input import strict_json

GOOGLE_URL = 'https://generativelanguage.googleapis.com'
MAX_RESPONSE_BYTES = 131072
MODEL_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'


def read_key(env_file=None):
    return read_secrets(('GEMINI_API_KEY',), env_file)['GEMINI_API_KEY']


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GeminiBrief:
    name = 'gemini'

    def __init__(self, api_key, model, base_url=GOOGLE_URL, timeout=30):
        parsed = urlsplit(base_url)
        google = parsed.scheme == 'https' and parsed.hostname == 'generativelanguage.googleapis.com' and not parsed.port
        loopback_test = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')  # Local stub servers only.
        if not (google or loopback_test) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError('Only Google\'s Gemini API (or a loopback test stub) is allowed')
        if not isinstance(api_key, str) or not re.fullmatch(r'[!-~]{1,512}', api_key):
            raise ValueError('A valid Gemini API key is required')
        if not isinstance(model, str) or not re.fullmatch(MODEL_PATTERN, model):
            raise ValueError('Invalid Gemini model identifier')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('Timeout must be greater than zero and at most 60 seconds')
        self._key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip('/'), timeout
        self._slots = threading.BoundedSemaphore(2)

    def __repr__(self):
        return '<GeminiBrief>'

    def _post(self, payload, result):
        """Runs in a worker thread so the caller's deadline holds even if the upstream trickles bytes."""
        try:
            request = Request(f'{self.base_url}/v1beta/models/{quote(self.model, safe="")}:generateContent', data=payload, method='POST', headers={
                'x-goog-api-key': self._key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=self.timeout) as response:
                if response.status != 200 or response.headers.get_content_type() != 'application/json':
                    raise ValueError()
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not 0 < len(raw) <= MAX_RESPONSE_BYTES:
                raise ValueError()
            result.append(raw)
        except HTTPError as error:
            error.close()
            result.append('http_' + str(error.code))
        except Exception:
            result.append('network')

    def complete(self, system, user):
        """Return (assistant text, served model). Upstream bodies and errors never reach callers."""
        if not self._slots.acquire(blocking=False):
            raise BriefUnavailable('busy')
        try:
            payload = json.dumps({
                'systemInstruction': {'parts': [{'text': system}]},
                'contents': [{'role': 'user', 'parts': [{'text': user}]}],
                'generationConfig': {'temperature': 0, 'maxOutputTokens': 2048, 'responseMimeType': 'application/json'}}).encode()
            result = []
            worker = threading.Thread(target=self._post, args=(payload, result), daemon=True)
            worker.start()
            worker.join(self.timeout + 1)
            if not result:
                raise BriefUnavailable('deadline')
            if isinstance(result[0], str):
                raise BriefUnavailable(result[0])
            try:
                data = strict_json(result[0])
                candidates = data['candidates']
                candidate = candidates[0]
                parts = candidate['content']['parts']
                served = data.get('modelVersion') or self.model
                texts = []
                for part in parts:
                    if not isinstance(part, dict) or set(part) - {'text', 'thought', 'thoughtSignature'}:
                        raise ValueError()  # Function calls, inline data and anything else are not a plain text reply.
                    if part.get('thought') is True:
                        continue  # A model's thinking summary is not part of the reply.
                    texts.append(part['text'])
                if (len(candidates) != 1 or candidate.get('finishReason') != 'STOP' or data.get('promptFeedback', {}).get('blockReason')
                        or not texts or not all(isinstance(t, str) for t in texts)
                        or not isinstance(served, str) or not re.fullmatch(MODEL_PATTERN, served)):
                    raise ValueError()
            except Exception:
                raise BriefUnavailable('invalid_response') from None
            return ''.join(texts), served
        finally:
            self._slots.release()
