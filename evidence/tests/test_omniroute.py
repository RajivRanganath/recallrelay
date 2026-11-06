import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evidence.ai.extraction import ExtractionService, ExtractionUnavailable
from evidence.ai.omniroute import OmniRouteExtractor, read_key
from evidence.backend.images import decode_image
from evidence.backend.server import make_server
from test_assessment import encoded_image
from test_extraction import raw_output
from test_resolution_client import RunningServer


def envelope():
    return {'model': 'test/vision', 'choices': [
        {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(raw_output())}}]}


class Gateway:
    def __init__(self):
        self.body = json.dumps(envelope()).encode()
        self.status = 200
        self.headers = {'Content-Type': 'application/json'}
        self.requests = []
        self.drip = False
        self.length = None
        self.response_headers = None
        self.chunked = False

    def __enter__(self):
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                gateway.requests.append((self.path, self.headers.get('Authorization'), json.loads(raw)))
                self.send_response(gateway.status)
                headers = gateway.response_headers
                if headers is None:
                    headers = list(gateway.headers.items()) + [('Content-Length', str(
                        gateway.length if gateway.length is not None else len(gateway.body)))]
                for key, value in headers:
                    self.send_header(key, value)
                self.end_headers()
                try:
                    if gateway.drip:
                        for byte in gateway.body:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(.05)
                    elif gateway.chunked:
                        self.wfile.write(f'{len(gateway.body):x}\r\n'.encode()
                                         + gateway.body + b'\r\n0\r\n\r\n')
                    else:
                        self.wfile.write(gateway.body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.server = RunningServer(ThreadingHTTPServer(('127.0.0.1', 0), Handler))
        self.url = self.server.__enter__() + '/v1'
        return self

    def __exit__(self, *args):
        return self.server.__exit__(*args)


class OmniRouteTests(unittest.TestCase):
    def setUp(self):
        self.image = decode_image(encoded_image(), 'image/png')

    def adapter(self, gateway, **kwargs):
        return OmniRouteExtractor('synthetic-test-key', base_url=gateway.url, **kwargs)

    def test_existing_env_file_reads_only_authorized_key_without_shell_execution(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {}, clear=True):
            path = Path(folder) / 'provider.env'
            path.write_text("OTHER_KEY=do-not-reuse\nexport OMNIROUTE_API_KEY='synthetic-test-key'\n")
            self.assertEqual(read_key(path), 'synthetic-test-key')
            with patch.dict('os.environ', {'OMNIROUTE_API_KEY': 'existing-process-key'}):
                self.assertEqual(read_key(path), 'existing-process-key')
            path.write_text('OMNIROUTE_API_KEY=one\nOMNIROUTE_API_KEY=two\n')
            with self.assertRaises(ValueError):
                read_key(path)
            path.write_text('OMNIROUTE_API_KEY=\n')
            with self.assertRaises(ValueError):
                read_key(path)
            path.write_text('OTHER_KEY=synthetic-test-key\n')
            with self.assertRaises(ValueError):
                read_key(path)
            target = Path(folder) / 'link'
            target.symlink_to(path)
            with self.assertRaises(ValueError):
                read_key(target)

    def test_configuration_rejects_remote_key_destinations_and_invalid_limits(self):
        for url in ('https://remote.test/v1', 'http://remote.test:20128/v1',
                    'http://localhost:20128/v1?key=x', 'http://user:secret@localhost:20128/v1',
                    'http://localhost:20128/other', 'http://localhost/v1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OmniRouteExtractor('synthetic-test-key', base_url=url)
        for timeout in (0, -1, True, float('nan'), 36):
            with self.assertRaises(ValueError):
                OmniRouteExtractor('synthetic-test-key', timeout=timeout)
        with self.assertRaises(ValueError):
            OmniRouteExtractor('synthetic-test-key', model='invalid model')
        self.assertNotIn('synthetic-test-key', repr(OmniRouteExtractor('synthetic-test-key')))

    def test_image_request_and_provenance_keep_proposals_separate_from_decisions(self):
        with Gateway() as gateway:
            result = ExtractionService(self.adapter(gateway)).propose(self.image)
            self.assertEqual((result['model'], result['batch'], result['mode']), ('LAMP-100', 'B101', 'ai'))
            self.assertEqual(result['source']['served_model'], 'test/vision')
            self.assertEqual(result['source']['requested_model'], 'auto/smart')
            self.assertFalse(result['source']['model_id_matches_request'])
            self.assertNotIn('decision', result)
            path, auth, payload = gateway.requests[0]
            self.assertEqual(path, '/v1/chat/completions')
            self.assertEqual(auth, 'Bearer synthetic-test-key')
            self.assertEqual(payload['model'], 'auto/smart')
            self.assertFalse(payload['stream'])
            self.assertNotIn('tools', payload)
            self.assertNotIn('campaign', payload)
            content = payload['messages'][1]['content']
            self.assertEqual(content[1]['image_url']['url'], 'data:image/png;base64,' + base64.b64encode(self.image.content).decode())
            self.assertIn('untrusted', payload['messages'][0]['content'])

    def test_uncertain_and_injected_fields_fail_closed(self):
        with Gateway() as gateway:
            data = envelope()
            fields = raw_output()
            fields['batch']['uncertain'] = True
            data['choices'][0]['message']['content'] = json.dumps(fields)
            gateway.body = json.dumps(data).encode()
            result = ExtractionService(self.adapter(gateway)).propose(self.image)
            self.assertIsNone(result['batch'])
            self.assertIn('batch', result['clarification'])
            fields['approved'] = True
            data['choices'][0]['message']['content'] = json.dumps(fields)
            gateway.body = json.dumps(data).encode()
            with self.assertRaises(ExtractionUnavailable):
                ExtractionService(self.adapter(gateway)).propose(self.image)

    def test_truncation_refusal_tool_calls_and_malformed_json_are_unavailable(self):
        variants = []
        for reason in ('length', 'tool_calls', None):
            data = envelope()
            data['choices'][0]['finish_reason'] = reason
            variants.append(json.dumps(data).encode())
        for field, value in (('tool_calls', [{'name': 'refund'}]), ('refusal', 'private-error'),
                             ('content', 'private-error'), ('content', '{"model":{},"model":{}}')):
            data = envelope()
            data['choices'][0]['message'][field] = value
            variants.append(json.dumps(data).encode())
        variants.extend([b'{"choices":[],"choices":[]}', b'not-json', b'{}'])
        with Gateway() as gateway:
            for body in variants:
                gateway.body = body
                with self.subTest(body=body), self.assertRaises(ExtractionUnavailable) as caught:
                    ExtractionService(self.adapter(gateway)).propose(self.image)
                self.assertNotIn('private-error', str(caught.exception))

    def test_http_errors_redirects_wrong_types_and_size_limits_do_not_retry(self):
        with Gateway() as gateway:
            for status, headers, body, length in (
                (401, {'Content-Type': 'application/json'}, b'private-error', None),
                (206, {'Content-Type': 'application/json'}, gateway.body, None),
                (302, {'Content-Type': 'application/json', 'Location': gateway.url}, b'', None),
                (200, {'Content-Type': 'text/html'}, gateway.body, None),
                (200, {'Content-Type': 'application/json'}, b'x' * 65537, None),
                (200, {'Content-Type': 'application/json'}, gateway.body, 65537),
                (200, {'Content-Type': 'application/json'}, b'{}', 20),
            ):
                gateway.status, gateway.headers, gateway.body, gateway.length = status, headers, body, length
                before = len(gateway.requests)
                with self.subTest(status=status, length=length), self.assertRaises(ExtractionUnavailable):
                    ExtractionService(self.adapter(gateway)).propose(self.image)
                self.assertEqual(len(gateway.requests), before + 1)

    def test_ambiguous_gateway_headers_fail_closed_without_retry(self):
        before_workers = {p.pid for p in multiprocessing.active_children()}
        with Gateway() as gateway:
            content_type = [('Content-Type', 'application/json')]
            length = [('Content-Length', str(len(gateway.body)))]
            variants = [
                (length, False),
                (content_type + content_type + length, False),
                (content_type + [('Content-Type', 'text/html')] + length, False),
                (content_type + [('Transfer-Encoding', 'gzip')], False),
                (content_type + [('Transfer-Encoding', 'identity')], False),
                (content_type + [('Transfer-Encoding', '')], False),
                (content_type + [('Transfer-Encoding', 'chunked'),
                                 ('Transfer-Encoding', 'chunked')], True),
                (content_type + [('Transfer-Encoding', 'gzip, chunked')], False),
                (content_type + length + length, False),
                (content_type + length + [('Transfer-Encoding', 'chunked')], True),
                (content_type + [('Content-Length', '+123')], False),
                (content_type + [('Content-Length', '123, 123')], False),
            ]
            adapter = self.adapter(gateway)
            for headers, chunked in variants:
                gateway.response_headers, gateway.chunked = headers, chunked
                before_calls = len(gateway.requests)
                with self.subTest(headers=headers):
                    with self.assertRaises(ExtractionUnavailable) as caught:
                        ExtractionService(adapter).propose(self.image)
                    self.assertEqual(caught.exception.code, 'invalid_response')
                    self.assertNotIn('synthetic-test-key', str(caught.exception))
                    self.assertEqual(len(gateway.requests), before_calls + 1)
                    self.assertEqual({p.pid for p in multiprocessing.active_children()}, before_workers)

    def test_unambiguous_gateway_framing_remains_usable_after_a_failure(self):
        with Gateway() as gateway:
            adapter = self.adapter(gateway)
            gateway.response_headers = [('Content-Type', 'text/html')]
            with self.assertRaises(ExtractionUnavailable):
                ExtractionService(adapter).propose(self.image)
            for framing in ('length', 'chunked', 'connection'):
                gateway.response_headers = [('Content-Type', 'application/json; charset=utf-8')]
                gateway.chunked = framing == 'chunked'
                if framing == 'length':
                    gateway.response_headers.append(('Content-Length', str(len(gateway.body))))
                elif gateway.chunked:
                    gateway.response_headers.append(('Transfer-Encoding', 'chunked'))
                with self.subTest(framing=framing):
                    result = ExtractionService(adapter).propose(self.image)
                    self.assertEqual((result['model'], result['batch']), ('LAMP-100', 'B101'))
                    self.assertEqual(result['source']['served_model'], 'test/vision')
            self.assertEqual(len(gateway.requests), 4)

    def test_trickling_response_is_terminated_and_worker_is_reaped(self):
        before = {p.pid for p in multiprocessing.active_children()}
        with Gateway() as gateway:
            gateway.drip = True
            start = time.monotonic()
            with self.assertRaises(ExtractionUnavailable):
                ExtractionService(self.adapter(gateway, timeout=.8)).propose(self.image)
            self.assertLess(time.monotonic() - start, 2.5)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_saturation_fails_immediately_without_starting_provider_calls(self):
        with Gateway() as gateway:
            adapter = self.adapter(gateway)
            adapter._slots.acquire()
            adapter._slots.acquire()
            try:
                with self.assertRaises(ExtractionUnavailable):
                    ExtractionService(adapter).propose(self.image)
                self.assertEqual(gateway.requests, [])
            finally:
                adapter._slots.release()
                adapter._slots.release()

    def test_ai_http_proposal_does_not_persist_an_assessment(self):
        with tempfile.TemporaryDirectory() as folder, Gateway() as gateway:
            with RunningServer(make_server(0, Path(folder) / 'db.sqlite3', extraction_adapter=self.adapter(gateway))) as url:
                body = json.dumps({'image_base64': encoded_image(), 'mime_type': 'image/png'}).encode()
                with urlopen(Request(url + '/demo/image-extraction', data=body, headers={'Content-Type': 'application/json'})) as response:
                    proposal = json.load(response)
                self.assertEqual(proposal['mode'], 'ai')
                self.assertNotIn('decision', proposal)
                with self.assertRaises(HTTPError) as caught:
                    urlopen(url + '/v1/assessments/case-demo-1')
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()

    def test_health_reports_configured_adapter_without_contacting_gateway(self):
        with tempfile.TemporaryDirectory() as folder, Gateway() as gateway:
            with RunningServer(make_server(0, Path(folder) / 'db.sqlite3', extraction_adapter=self.adapter(gateway))) as url:
                with urlopen(url + '/health') as response:
                    health = json.load(response)
                self.assertEqual((health['extraction_mode'], health['extraction_provider']), ('ai', 'omniroute'))
                self.assertEqual(gateway.requests, [])

class ProviderSmokeTests(unittest.TestCase):
    def test_unavailable_calls_remain_in_denominator(self):
        from evidence.evals.live import evaluate
        class Unavailable:
            mode = 'ai'
            provider_name = 'offline-test-double'
            model = 'test/vision'
            timeout = 1
            def extract(self, image):
                raise ExtractionUnavailable('private-details', code='http_429')
        report = evaluate(Unavailable(), case_ids=['clear-png', 'instruction-note'])
        self.assertEqual((report['cases_attempted'], report['proposals'], report['unavailable'], report['fields_compared']), (2, 0, 2, 0))
        self.assertTrue(all(row['failure_code'] == 'http_429' for row in report['results']))
        self.assertNotIn('private-details', json.dumps(report))
        self.assertFalse(report['holdout'])

    def test_reference_missing_guesses_and_false_eligibility_are_reported(self):
        from evidence.evals.live import evaluate
        class Unsafe:
            mode = 'ai'
            provider_name = 'offline-test-double'
            model = 'test/vision'
            timeout = 1
            def extract(self, image):
                return raw_output()
        report = evaluate(Unsafe(), case_ids=['missing-model', 'instruction-note'])
        self.assertEqual(report['false_eligible_against_authored_reference'], 2)
        missing = next(row for row in report['results'] if row['case_id'] == 'missing-model')
        self.assertEqual(missing['guessed_reference_missing'], ['model'])
        self.assertEqual(report['fields_compared'], 4)

    def test_cli_fails_field_errors_even_without_false_eligibility_and_saves_report(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from evidence.evals.live import main
        class WrongBatch:
            mode = 'ai'
            provider_name = 'offline-test-double'
            model = 'test/vision'
            timeout = 1
            def extract(self, image):
                fields = raw_output()
                fields['batch']['value'] = 'B999'
                return fields
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('sys.argv', ['live', '--case', 'clear-png', '--output', str(output)]), \
                    patch('evidence.evals.live.read_key', return_value='synthetic-test-key'), \
                    patch('evidence.evals.live.OmniRouteExtractor', return_value=WrongBatch()), \
                    redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main()
            self.assertEqual(caught.exception.code, 1)
            report = json.loads(output.read_text())
            self.assertEqual(report['unavailable'], 0)
            self.assertEqual(report['false_eligible_against_authored_reference'], 0)
            self.assertEqual(report['fields_compared'], 2)
            self.assertEqual(report['fields_matching_authored_typed_reference'], 1)
            self.assertEqual(report['results'][0]['observed_fields']['batch'], 'B999')

    def test_cli_accepts_matching_reference_fields_and_saves_report(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from evidence.evals.live import main
        class Matching:
            mode = 'ai'
            provider_name = 'offline-test-double'
            model = 'test/vision'
            timeout = 1
            def extract(self, image):
                return raw_output()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('sys.argv', ['live', '--case', 'clear-png', '--output', str(output)]), \
                    patch('evidence.evals.live.read_key', return_value='synthetic-test-key'), \
                    patch('evidence.evals.live.OmniRouteExtractor', return_value=Matching()), \
                    redirect_stdout(StringIO()):
                main()
            report = json.loads(output.read_text())
            self.assertEqual(report['fields_matching_authored_typed_reference'], 2)
            self.assertEqual(report['cases_attempted'], 1)

    def test_changed_dataset_and_mock_adapter_are_rejected_before_calls(self):
        from evidence.evals.live import evaluate
        from evidence.ai.fixture_extractor import DEFAULT_MANIFEST, FixtureExtractor
        import shutil
        with self.assertRaises(ValueError):
            evaluate(FixtureExtractor())
        class NeverCalled:
            mode = 'ai'
            calls = 0
            def extract(self, image):
                self.calls += 1
                raise AssertionError()
        adapter = NeverCalled()
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(DEFAULT_MANIFEST.parent, Path(folder) / 'fixtures')
            manifest = Path(folder) / 'fixtures' / 'manifest.json'
            data = json.loads(manifest.read_text())
            (manifest.parent / data['cases'][0]['image']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Fixture bytes changed'):
                evaluate(adapter, manifest)
        self.assertEqual(adapter.calls, 0)
