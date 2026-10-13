import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer
import dashboard


class DashboardTests(unittest.TestCase):
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
