import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest

from resolution.ai.errors import BriefUnavailable
from resolution.ai.omniroute import OmniRouteBrief, read_key

KEY = 'stub-KEY-12345'


def completion(content='{"summary":"x"}', model='served/model-1', **choice):
    message = dict({'role': 'assistant', 'content': content}, **choice.pop('message', {}))
    return {'model': model, 'choices': [dict({'finish_reason': 'stop', 'message': message}, **choice)]}


class StubGateway:
    def __init__(self, replies=()):
        self.replies, self.requests = list(replies), []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                stub.requests.append(({k.lower(): v for k, v in self.headers.items()}, self.path, body))
                code, reply, kind = stub.replies.pop(0) if stub.replies else (200, completion(), 'application/json')
                if code == 'slow':
                    time.sleep(1.5)
                    return
                raw = reply if isinstance(reply, bytes) else json.dumps(reply).encode()
                self.send_response(code)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f'http://127.0.0.1:{self.server.server_port}/v1'

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ProviderTests(unittest.TestCase):
    def test_request_shape_and_successful_reply(self):
        stub = StubGateway()
        with stub as url:
            content, served = OmniRouteBrief(KEY, model='auto/smart', base_url=url).complete('SYSTEM TEXT', 'USER JSON')
        self.assertEqual((content, served), ('{"summary":"x"}', 'served/model-1'))
        headers, path, body = stub.requests[0]
        self.assertEqual((path, headers['authorization']), ('/v1/chat/completions', 'Bearer ' + KEY))
        self.assertEqual((body['model'], body['temperature'], body['stream'], body['response_format']), ('auto/smart', 0, False, {'type': 'json_object'}))
        self.assertEqual([m['role'] for m in body['messages']], ['system', 'user'])
        self.assertEqual((body['messages'][0]['content'], body['messages'][1]['content']), ('SYSTEM TEXT', 'USER JSON'))

    def test_bad_replies_become_short_codes_never_upstream_text(self):
        replies = {
            'http_500': (500, {'error': 'SECRET upstream detail'}, 'application/json'),
            'http_401': (401, {'error': KEY}, 'application/json'),
            'network': (200, b'not json', 'text/plain'),  # Wrong content type is treated as a failed call.
            'invalid_response': [(200, b'not json', 'application/json'), (200, completion(finish_reason='length'), 'application/json'),
                                 (200, completion(message={'tool_calls': [{'id': 'x'}]}), 'application/json'),
                                 (200, completion(message={'refusal': 'no'}), 'application/json'),
                                 (200, completion(message={'role': 'user'}), 'application/json'),
                                 (200, completion(message={'content': None}), 'application/json'),
                                 (200, completion(model='bad model!'), 'application/json'),
                                 (200, {'model': 'm', 'choices': []}, 'application/json'),
                                 (200, {'model': 'm', 'choices': [completion()['choices'][0]] * 2}, 'application/json')],
        }
        for code, reply in replies.items():
            for item in (reply if isinstance(reply, list) else [reply]):
                with self.subTest(code=code, status=item[0]), StubGateway([item]) as url:
                    with self.assertRaises(BriefUnavailable) as caught:
                        OmniRouteBrief(KEY, base_url=url).complete('s', 'u')
                    self.assertIn(caught.exception.code, {code, 'network'} if code == 'network' else {code})
                    for text in (str(caught.exception), repr(caught.exception)):
                        self.assertNotIn('SECRET', text)
                        self.assertNotIn(KEY, text)

    def test_deadline_and_unreachable_gateway(self):
        with StubGateway([('slow', None, None)]) as url:
            with self.assertRaises(BriefUnavailable) as caught:
                OmniRouteBrief(KEY, base_url=url, timeout=0.3).complete('s', 'u')
            # A silent server trips the socket timeout ('network'); 'deadline' is the backstop for a trickling one.
            self.assertIn(caught.exception.code, {'network', 'deadline'})
        with self.assertRaises(BriefUnavailable) as caught:  # The gateway is gone now.
            OmniRouteBrief(KEY, base_url=url, timeout=1).complete('s', 'u')
        self.assertEqual(caught.exception.code, 'network')

    def test_only_a_local_gateway_is_allowed_and_inputs_are_validated(self):
        for url in ('http://example.com:20128/v1', 'https://127.0.0.1:20128/v1', 'http://127.0.0.1/v1', 'http://127.0.0.1:20128/v2',
                    'http://user:pw@127.0.0.1:20128/v1', 'http://127.0.0.1:20128/v1?x=1', 'http://127.0.0.1.evil.example:20128/v1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OmniRouteBrief(KEY, base_url=url)
        for kwargs in ({'api_key': ''}, {'api_key': 'has space'}, {'api_key': KEY, 'model': 'bad model!'},
                       {'api_key': KEY, 'timeout': 0}, {'api_key': KEY, 'timeout': 99}, {'api_key': KEY, 'timeout': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OmniRouteBrief(**kwargs)
        OmniRouteBrief(KEY)  # Default local gateway.
        self.assertNotIn(KEY, repr(OmniRouteBrief(KEY)))

    def test_key_is_read_from_an_env_file_without_executing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'omniroute.env'
            path.write_text('OTHER=1\nexport OMNIROUTE_API_KEY="from-file-key"\n$(touch pwned)\n')
            import os
            saved = os.environ.pop('OMNIROUTE_API_KEY', None)
            try:
                self.assertEqual(read_key(path), 'from-file-key')
                path.write_text('OMNIROUTE_API_KEY=a\nOMNIROUTE_API_KEY=b\n')
                with self.assertRaises(ValueError):
                    read_key(path)
            finally:
                if saved is not None:
                    os.environ['OMNIROUTE_API_KEY'] = saved
            self.assertFalse((Path(tmp) / 'pwned').exists())


if __name__ == '__main__':
    unittest.main()
