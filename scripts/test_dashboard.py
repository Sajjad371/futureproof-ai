import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer
import dashboard
from unittest.mock import patch


class DashboardTests(unittest.TestCase):
    def test_browser_disconnect_is_handled(self):
        handler = object.__new__(dashboard.Handler)
        for error in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            handler.close_connection = False
            with patch.object(handler, 'respond_get', side_effect=error):
                handler.do_GET()
            self.assertTrue(handler.close_connection)

    def test_detail_projection_does_not_leak_unknown_fields(self):
        result = dashboard.summary_details({'target_applied': False,
            'checks': {'health': True, 'secret': 'hidden', 'authentication': 'hidden'},
            'api_key': 'hidden'})
        self.assertEqual(result, {'target_applied': False, 'checks': {'health': True}})

    def test_configuration_plan_is_classified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / 'artifacts/config-fixtures/config-demo'
            fixture.mkdir(parents=True)
            (fixture / 'config-plan.json').write_text(json.dumps({'plan': {'steps': []}}))
            data = dashboard.inventory(root)
            self.assertEqual(data['skipped'], 0)
            self.assertEqual(data['records'][0]['status'], 'plan_recorded')

    def test_only_summary_fields_are_returned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / 'artifacts/restart-fixtures/restart-demo'
            fixture.mkdir(parents=True)
            (fixture / 'record.json').write_text(json.dumps({'status': 'passed', 'secret': 'do-not-return'}))
            (fixture / 'broken.json').write_text('{')
            data = dashboard.inventory(root)
            self.assertEqual(data['skipped'], 1)
            self.assertEqual(len(data['records']), 1)
            self.assertNotIn('do-not-return', json.dumps(data))

    def test_http_routes_and_host_restriction(self):
        with HTTPServer(('127.0.0.1', 0), dashboard.Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                url = 'http://127.0.0.1:%s' % server.server_port
                with opener.open(url + '/api/runs') as response:
                    self.assertIn('records', json.load(response))
                with opener.open(url + '/favicon.ico') as response:
                    self.assertEqual(response.status, 204)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    opener.open(urllib.request.Request(url + '/api/fixtures', data=b'{}',
                        headers={'Content-Type': 'application/json'}))
                self.assertEqual(error.exception.code, 403)
                for path in ['/.env', '/../../.env']:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        opener.open(url + path)
                    self.assertEqual(error.exception.code, 404)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    opener.open(urllib.request.Request(url, headers={'Host': 'untrusted.example'}))
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
