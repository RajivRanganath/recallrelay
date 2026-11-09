import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from resolution.ai.brief import BriefService
from resolution.ai.errors import BriefUnavailable
from resolution.ai.gemini import GeminiBrief, read_key
from resolution.evals import run
from test_brief import detail

KEY = 'stub-GEMINI-KEY-12345'


def reply(text='{"summary":"x"}', model='gemini-test-1', **candidate):
    return {'modelVersion': model, 'candidates': [dict({'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': text}]}}, **candidate)]}


class StubGoogle:
    def __init__(self, replies=()):
        self.replies, self.requests = list(replies), []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                stub.requests.append(({k.lower(): v for k, v in self.headers.items()}, self.path, body))
                code, payload, kind = stub.replies.pop(0) if stub.replies else (200, reply(), 'application/json')
                if code == 'slow':
                    time.sleep(1.5)
                    return
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(code)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f'http://127.0.0.1:{self.server.server_port}'

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ProviderTests(unittest.TestCase):
    def test_request_shape_keeps_the_key_in_a_header_never_the_url(self):
        stub = StubGoogle()
        with stub as url:
            text, served = GeminiBrief(KEY, 'gemini-test-1', base_url=url).complete('SYSTEM TEXT', 'USER JSON')
        self.assertEqual((text, served), ('{"summary":"x"}', 'gemini-test-1'))
        headers, path, body = stub.requests[0]
        self.assertEqual(path, '/v1beta/models/gemini-test-1:generateContent')
        self.assertEqual(headers['x-goog-api-key'], KEY)
        self.assertNotIn(KEY, path)
        self.assertNotIn('authorization', headers)
        self.assertEqual(body['systemInstruction'], {'parts': [{'text': 'SYSTEM TEXT'}]})
        self.assertEqual(body['contents'], [{'role': 'user', 'parts': [{'text': 'USER JSON'}]}])
        self.assertEqual((body['generationConfig']['temperature'], body['generationConfig']['responseMimeType']), (0, 'application/json'))

    def test_text_parts_are_joined_and_thought_parts_are_skipped(self):
        payload = {'modelVersion': 'gemini-test-1', 'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [
            {'text': 'private reasoning', 'thought': True}, {'text': '{"summary":'}, {'text': '"x"}'}]}}]}
        with StubGoogle([(200, payload, 'application/json')]) as url:
            text, _ = GeminiBrief(KEY, 'gemini-test-1', base_url=url).complete('s', 'u')
        self.assertEqual(text, '{"summary":"x"}')

    def test_bad_replies_become_short_codes_never_upstream_text(self):
        def parts(*items):
            return (200, {'modelVersion': 'm', 'candidates': [{'finishReason': 'STOP', 'content': {'parts': list(items)}}]}, 'application/json')
        cases = [
            ('http_400', (400, {'error': {'message': 'API key not valid SECRET-DETAIL ' + KEY}}, 'application/json')),
            ('http_429', (429, {'error': 'quota'}, 'application/json')), ('http_500', (500, {}, 'application/json')),
            ('network', (200, b'not json', 'text/plain')),
            ('invalid_response', (200, b'not json', 'application/json')),
            ('invalid_response', (200, reply(finishReason='MAX_TOKENS'), 'application/json')),
            ('invalid_response', (200, reply(finishReason='SAFETY'), 'application/json')),
            ('invalid_response', (200, {'modelVersion': 'm', 'candidates': []}, 'application/json')),
            ('invalid_response', (200, {'modelVersion': 'm', 'candidates': [reply()['candidates'][0]] * 2}, 'application/json')),
            ('invalid_response', (200, dict(reply(), promptFeedback={'blockReason': 'SAFETY'}), 'application/json')),
            ('invalid_response', parts({'functionCall': {'name': 'x', 'args': {}}})),
            ('invalid_response', parts({'inlineData': {'mimeType': 'image/png', 'data': 'AAAA'}})),
            ('invalid_response', parts({'text': 5})),
            ('invalid_response', parts()),
            ('invalid_response', parts({'text': 'only thinking', 'thought': True})),
            ('invalid_response', (200, reply(model='bad model!'), 'application/json')),
            ('invalid_response', (200, {'candidates': [{'finishReason': 'STOP'}]}, 'application/json')),
        ]
        for code, item in cases:
            with self.subTest(expected=code, status=item[0]), StubGoogle([item]) as url:
                with self.assertRaises(BriefUnavailable) as caught:
                    GeminiBrief(KEY, 'gemini-test-1', base_url=url).complete('s', 'u')
                self.assertEqual(caught.exception.code, code)
                for text in (str(caught.exception), repr(caught.exception)):
                    self.assertNotIn('SECRET-DETAIL', text)
                    self.assertNotIn(KEY, text)

    def test_deadline_and_unreachable_service(self):
        with StubGoogle([('slow', None, None)]) as url:
            with self.assertRaises(BriefUnavailable) as caught:
                GeminiBrief(KEY, 'gemini-test-1', base_url=url, timeout=0.3).complete('s', 'u')
            self.assertIn(caught.exception.code, {'network', 'deadline'})
        with self.assertRaises(BriefUnavailable) as caught:  # The stub is gone now.
            GeminiBrief(KEY, 'gemini-test-1', base_url=url, timeout=1).complete('s', 'u')
        self.assertEqual(caught.exception.code, 'network')

    def test_only_google_or_a_loopback_stub_and_valid_inputs(self):
        for url in ('https://evil.example', 'http://generativelanguage.googleapis.com', 'https://generativelanguage.googleapis.com.evil.example',
                    'https://user:pw@generativelanguage.googleapis.com', 'https://generativelanguage.googleapis.com?key=x',
                    'https://generativelanguage.googleapis.com:8443', 'https://generativelanguage.googleapis.com/v1beta', 'http://example.com'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                GeminiBrief(KEY, 'gemini-test-1', base_url=url)
        for kwargs in ({'api_key': ''}, {'api_key': 'has space'}, {'api_key': KEY, 'model': 'bad model'}, {'api_key': KEY, 'model': 'a/b'},
                       {'api_key': KEY, 'model': '../x'}, {'api_key': KEY, 'model': ''}, {'api_key': KEY, 'timeout': 0},
                       {'api_key': KEY, 'timeout': 999}, {'api_key': KEY, 'timeout': True}):
            kwargs.setdefault('model', 'gemini-test-1')
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                GeminiBrief(**kwargs)
        self.assertNotIn(KEY, repr(GeminiBrief(KEY, 'gemini-test-1')))  # The real Google host is the default.

    def test_key_is_read_from_an_env_file_without_executing_it(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ):
            os.environ.pop('GEMINI_API_KEY', None)
            path = Path(tmp) / 'gemini.env'
            path.write_text('OTHER=1\nexport GEMINI_API_KEY="from-file-key"\n$(touch pwned)\n')
            self.assertEqual(read_key(path), 'from-file-key')
            path.write_text('GEMINI_API_KEY=a\nGEMINI_API_KEY=b\n')
            with self.assertRaises(ValueError):
                read_key(path)
            self.assertFalse((Path(tmp) / 'pwned').exists())


class ServiceIntegrationTests(unittest.TestCase):
    GOOD = {'summary': 'Batch B101 matches and the refund of 40.00 USD awaits your approval.', 'missing_steps': [], 'citations': ['review']}

    def brief(self, content):
        with StubGoogle([(200, reply(json.dumps(content)), 'application/json')]) as url:
            return BriefService(GeminiBrief(KEY, 'gemini-test-1', base_url=url)).brief(detail())

    def test_a_valid_reply_becomes_an_ai_brief_labeled_with_provider_and_model(self):
        result = self.brief(self.GOOD)
        self.assertEqual((result['source'], result['provider'], result['served_model'], result['fallback_reason']),
                         ('ai', 'gemini', 'gemini-test-1', None))

    def test_a_reply_that_fails_the_checks_is_replaced_by_the_template(self):
        result = self.brief(dict(self.GOOD, summary='The refund has been approved and paid.'))
        self.assertEqual((result['source'], result['fallback_reason']), ('template', 'invalid_output'))

    def test_a_provider_outage_falls_back_with_a_short_code(self):
        with StubGoogle([(429, {}, 'application/json')]) as url:
            result = BriefService(GeminiBrief(KEY, 'gemini-test-1', base_url=url)).brief(detail())
        self.assertEqual((result['source'], result['fallback_reason']), ('template', 'http_429'))


class CommandTests(unittest.TestCase):
    def invoke(self, *args):
        with mock.patch('sys.argv', ['run', *args]), mock.patch('builtins.print'):
            run.main()

    def test_report_marks_gemini_as_real_ai_and_the_options_are_validated(self):
        self.assertTrue(run.build_report('gemini', run.FakeGrounded())['real_ai'])
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.json'
            for args in (('--provider', 'gemini'), ('--provider', 'template', '--gemini-model', 'm'),
                         ('--provider', 'omniroute', '--gemini-env', str(Path(tmp) / 'x.env'))):
                with self.subTest(args=args), self.assertRaises(SystemExit):
                    self.invoke(*args, '--output', str(report))
                self.assertFalse(report.exists())  # Bad arguments never reserve or leave a report file.
            with mock.patch.dict(os.environ):
                os.environ.pop('GEMINI_API_KEY', None)
                with self.assertRaises(SystemExit):
                    self.invoke('--provider', 'gemini', '--gemini-model', 'm', '--output', str(report))


if __name__ == '__main__':
    unittest.main()
