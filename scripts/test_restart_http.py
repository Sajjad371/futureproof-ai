"""Real child-process HTTP restart tests; no Podman or API needed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import restart_fixture as fixture
import restart_http_worker as worker


class RestartHTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.object(fixture, 'ROOT', Path(temporary.name)):
            self.root = fixture.create_fixture()

    def test_real_restart_loads_current_revision_and_preserves_files(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        worker.check_report(worker.run_checks(self.root))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_service_keeps_loaded_revision_until_restarted(self):
        process, port, instance = worker.start(self.root, 'startup.json')
        try:
            import json
            self.assertEqual(json.loads(worker.request(port, '/state')[1])['revision'], 1)
            self.assertEqual(fixture.read_json(self.root / 'app.json')['revision'], 2)
        finally:
            worker.stop(process)
        self.assertIsNotNone(process.poll())

    def test_drift_rejected_before_process_start(self):
        (self.root / 'customer-demo.txt').write_bytes(b'changed')
        with patch.object(worker, 'start') as start, self.assertRaises(ValueError):
            worker.run_checks(self.root)
        start.assert_not_called()

    def test_failure_stops_started_process(self):
        processes = []
        real_start = worker.start
        def capture(*args):
            result = real_start(*args)
            processes.append(result[0])
            return result
        real_request = worker.request
        def fail_state(port, path, authorized=True):
            return (200, b'{}') if path == '/state' else real_request(port, path, authorized)
        with patch.object(worker, 'start', side_effect=capture), patch.object(worker, 'request', side_effect=fail_state):
            with self.assertRaises(ValueError):
                worker.run_checks(self.root)
        self.assertTrue(processes)
        self.assertTrue(all(p.poll() is not None for p in processes))

    def test_incomplete_or_false_evidence_rejected(self):
        valid = dict(status='passed', before_revision=1, after_revision=2,
                     **{key: True for key in worker.CHECKS})
        for key in worker.CHECKS:
            for value in [False, None, 1]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    worker.check_report(dict(valid, **{key: value}))
        for value in [True, 1, '2', None]:
            with self.assertRaises(ValueError):
                worker.check_report(dict(valid, after_revision=value))


if __name__ == '__main__':
    unittest.main(verbosity=2)
