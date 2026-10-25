import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('betterenglish_server', Path(__file__).parents[1] / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

RESULT = {'summary': '你清楚地描述了散步的习惯，没有发现明显错误。',
          'referenceAnswer': 'I enjoy walking in the park.', 'issues': [],
          'recommendations': [{'phrase': 'go for a walk', 'meaning': '去散步',
                               'example': 'I like to go for a walk after dinner.', 'usage': '描述日常散步活动。'}],
          'retryTask': '再说一次你喜欢在哪里散步，尝试使用 go for a walk。'}

class AnalysisTests(unittest.TestCase):
    def test_valid_answer_and_no_forced_errors(self):
        result = server.validate_analysis(copy.deepcopy(RESULT), 'I enjoy walking in the park.')
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['engine'], '本机 Ollama AI')

    def test_fabricated_quote_rejected(self):
        bad = copy.deepcopy(RESULT)
        bad['issues'] = [dict(zip(server.ISSUE_FIELDS, ['语法错误', 'I am agree', 'I agree', 'agree是动词', 'I agree.']))]
        with self.assertRaisesRegex(server.SetupError, '原文不存在'):
            server.validate_analysis(bad, 'I enjoy walking.')

    def test_incomplete_and_wrong_shapes_rejected(self):
        for value in [None, {}, {'summary': 'hello'}, dict(RESULT, issues='not a list'),
                      dict(RESULT, recommendations=[{'phrase': 'walk'}])]:
            with self.subTest(value=value), self.assertRaises(server.SetupError):
                server.validate_analysis(value, 'I enjoy walking.')

    def test_malformed_model_json_rejected(self):
        with patch.object(server, 'ollama', return_value={'message': {'content': 'not json'}}):
            with self.assertRaisesRegex(server.SetupError, 'JSON'):
                server.analyze('I enjoy walking.', 'Weekend')

    def test_topic_and_original_passed_without_rewrite(self):
        with patch.object(server, 'ollama', return_value={'message': {'content': json.dumps(RESULT)}}) as call:
            server.analyze('I enjoy walking.', 'Weekend')
            sent = call.call_args.args[1]
            self.assertEqual(json.loads(sent['messages'][1]['content']),
                             {'topic': 'Weekend', 'originalTranscript': 'I enjoy walking.'})
            self.assertFalse(sent['think'])
            self.assertEqual(sent['format'], server.SCHEMA)

if __name__ == '__main__':
    unittest.main()

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, value=None, origin='http://localhost:8080'):
        import urllib.request
        import urllib.error
        req = urllib.request.Request(self.base + path,
              data=None if value is None else json.dumps(value).encode(),
              headers={'Host': 'localhost:8080', 'Origin': origin, 'Content-Type': 'application/json'})
        try:
            r = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as err:
            r = err
        return r.status, r.read().decode()

    def test_full_http_flow_through_handler(self):
        def fake(path, payload=None, **kw):
            return {} if path == '/api/show' else {'message': {'content': json.dumps(RESULT)}}
        with patch.object(server, 'ollama', side_effect=fake):
            status, text = self.request('/api/analyze', {'text': 'I enjoy walking.', 'topic': 'Weekend'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)['referenceAnswer'], RESULT['referenceAnswer'])

    def test_external_origin_rejected(self):
        self.assertEqual(self.request('/api/analyze', {'text': 'Hello.'}, origin='https://example.com')[0], 403)

    def test_invalid_input_and_private_files_rejected(self):
        self.assertEqual(self.request('/api/analyze', {'text': ''})[0], 400)
        self.assertEqual(self.request('/server.py')[0], 404)
        self.assertEqual(self.request('/.git/config')[0], 404)

    def test_busy_returns_actionable_error(self):
        server.LOCK.acquire()
        try:
            status, text = self.request('/api/analyze', {'text': 'Hello.'})
            self.assertEqual(status, 429)
            self.assertIn('重新分析', text)
        finally:
            server.LOCK.release()

    def test_cloud_model_rejected(self):
        with patch.object(server, 'MODEL', 'something:cloud'):
            self.assertEqual(self.request('/api/analyze', {'text': 'Hello.'})[0], 400)
        with patch.object(server, 'ollama', return_value={'remote_host': 'https://example.com'}):
            self.assertEqual(self.request('/api/analyze', {'text': 'Hello.'})[0], 400)
