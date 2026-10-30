import base64
from http.server import HTTPServer
import threading
import unittest
import urllib.request
import urllib.error
from dashboard import Handler


class PublicDashboardTests(unittest.TestCase):
    def test_authentication_host_and_origin_required(self):
        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            server.public_origin = 'https://demo-test.trycloudflare.com'
            server.demo_authorization = 'Basic ' + base64.b64encode(b'demo:test-password-123456').decode()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = 'http://127.0.0.1:%s' % server.server_port
            def request(headers, path='/', data=None):
                return opener.open(urllib.request.Request(url+path, headers=headers, data=data))
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request({'Host': 'demo-test.trycloudflare.com'})
                self.assertEqual(error.exception.code, 401)
                headers = {'Host': 'demo-test.trycloudflare.com', 'Authorization': server.demo_authorization}
                with request(headers) as response:
                    self.assertEqual(response.status, 200)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request(dict(headers, Host='attacker.example'))
                self.assertEqual(error.exception.code, 403)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request(dict(headers, Origin='https://attacker.example'), '/api/fixtures', b'{}')
                self.assertEqual(error.exception.code, 403)
            finally:
                server.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
