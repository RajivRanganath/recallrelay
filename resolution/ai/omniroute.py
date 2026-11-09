"""Opt-in text provider through the user's existing local OmniRoute gateway. Never imports the evidence lane."""
import json
import math
import re
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from resolution.ai.errors import BriefUnavailable
from resolution.backend.envfile import read_secrets
from resolution.backend.json_input import strict_json

DEFAULT_BASE_URL = 'http://127.0.0.1:20128/v1'
MAX_RESPONSE_BYTES = 65536
MODEL_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}'


def read_key(env_file=None):
    return read_secrets(('OMNIROUTE_API_KEY',), env_file)['OMNIROUTE_API_KEY']


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class OmniRouteBrief:
    name = 'omniroute'

    def __init__(self, api_key, model='auto/smart', base_url=DEFAULT_BASE_URL, timeout=20):
        parsed = urlsplit(base_url)
        # Local gateway only. Never forward an existing key to an arbitrary URL.
        if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip('/') != '/v1' or not parsed.port):
            raise ValueError('OmniRoute must use a local HTTP gateway ending in /v1')
        if not isinstance(api_key, str) or not re.fullmatch(r'[!-~]{1,512}', api_key):
            raise ValueError('A valid OmniRoute key is required')
        if not isinstance(model, str) or not re.fullmatch(MODEL_PATTERN, model):
            raise ValueError('Invalid OmniRoute model identifier')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 35:
            raise ValueError('Timeout must be greater than zero and at most 35 seconds')
        self._key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip('/'), timeout
        self._slots = threading.BoundedSemaphore(2)

    def __repr__(self):
        return '<OmniRouteBrief>'

    def _post(self, payload, result):
        """Runs in a worker thread so the caller's deadline holds even if the upstream trickles bytes."""
        try:
            request = Request(self.base_url + '/chat/completions', data=payload, method='POST', headers={
                'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json',
                'Accept': 'application/json', 'Cache-Control': 'no-store'})
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
                'model': self.model, 'stream': False, 'temperature': 0, 'max_tokens': 1200,
                'reasoning_effort': 'none', 'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}).encode()
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
                choice = data['choices'][0]
                message = choice['message']
                served = data.get('model')
                if (len(data['choices']) != 1 or choice.get('finish_reason') != 'stop' or message.get('role') != 'assistant'
                        or message.get('tool_calls') or message.get('function_call') or message.get('refusal')
                        or not isinstance(message.get('content'), str)
                        or not isinstance(served, str) or not re.fullmatch(MODEL_PATTERN, served)):
                    raise ValueError()
            except Exception:
                raise BriefUnavailable('invalid_response') from None
            return message['content'], served
        finally:
            self._slots.release()
