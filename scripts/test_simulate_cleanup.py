"""Failure-path tests using temporary fixtures and simulated Podman responses.

No API requests, real containers, or existing project fixtures are used.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import create_demo_fixture
import simulate_cleanup


class SimulationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/cleanup_policy.py').write_bytes(
            (Path(__file__).parent / 'cleanup_policy.py').read_bytes())
        with patch.object(create_demo_fixture, 'ROOT', self.root), contextlib.redirect_stdout(io.StringIO()):
            self.fixture = create_demo_fixture.main()
        self.manifest = json.loads((self.fixture / 'manifest.json').read_text())
        self.plan = {'steps': [{'tool': 'DELETE_FILE', 'path': 'uploads/old.tmp'}]}
        self.report = {'status': 'passed', 'deleted': ['uploads/old.tmp'],
                       'preserved': ['uploads/current.json', 'uploads/customer-demo.txt', 'uploads/recent.tmp'],
                       'http_health': True, 'document_download': True,
                       'removed_file_bytes': next(e['size_bytes'] for e in self.manifest['files']
                                                  if e['path'] == 'uploads/old.tmp')}
        self.failure = None
        self.commands = []

    def podman(self, command, **kwargs):
        self.commands.append(command)
        if command[1] == 'info':
            return subprocess.CompletedProcess(command, 0, stdout='true')
        if command[1] == 'run':
            if self.failure:
                raise self.failure
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(self.report))
        return subprocess.CompletedProcess(command, 0)

    def run_simulation(self):
        (self.fixture / 'planning-result.json').write_text(json.dumps(
            {'status': 'policy_passed', 'plan': self.plan}))
        with patch.object(simulate_cleanup, 'ROOT', self.root), \
                patch.object(simulate_cleanup.subprocess, 'run', side_effect=self.podman), \
                patch('sys.argv', ['simulate_cleanup.py', self.fixture.name]), \
                contextlib.redirect_stdout(io.StringIO()):
            code = simulate_cleanup.main()
        evidence = json.loads(next(self.fixture.glob('futureproof-simulation-*.json')).read_text())
        self.assertFalse(evidence['target_applied'])
        return code, evidence

    def test_valid_report_and_original_preserved(self):
        code, evidence = self.run_simulation()
        self.assertEqual(code, 0)
        self.assertTrue(evidence['original_unchanged'])
        self.assertTrue((self.fixture / 'uploads/old.tmp').exists())

    def test_protected_deletion_rejected_before_podman(self):
        self.plan['steps'][0]['path'] = 'uploads/customer-demo.txt'
        self.assertEqual(self.run_simulation()[0], 1)
        self.assertEqual(self.commands, [])

    def test_incomplete_goal_rejected_before_podman(self):
        # Make the second temporary file eligible in this disposable test fixture.
        import os
        entry = next(e for e in self.manifest['files'] if e['path'] == 'uploads/recent.tmp')
        entry['modified_at'] = self.manifest['created_at'] - 45 * 86400
        os.utime(self.fixture / entry['path'], (entry['modified_at'], entry['modified_at']))
        (self.fixture / 'manifest.json').write_text(json.dumps(self.manifest))
        self.assertEqual(self.run_simulation()[0], 1)
        self.assertEqual(self.commands, [])

    def test_protected_content_drift_rejected_before_podman(self):
        (self.fixture / 'uploads/customer-demo.txt').write_text('changed')
        self.assertEqual(self.run_simulation()[0], 1)
        self.assertEqual(self.commands, [])

    def test_container_failure_records_failure_and_cleans_resources(self):
        self.failure = subprocess.CalledProcessError(1, 'podman', stderr='worker failed')
        code, evidence = self.run_simulation()
        self.assertEqual(code, 1)
        self.assertEqual(evidence['status'], 'failed')
        self.assertEqual([c[1] for c in self.commands][-2:], ['rm', 'rmi'])

    def test_timeout_records_failure_and_cleans_resources(self):
        self.failure = subprocess.TimeoutExpired('podman', 60)
        self.assertEqual(self.run_simulation()[0], 1)
        self.assertEqual([c[1] for c in self.commands][-2:], ['rm', 'rmi'])

    def test_empty_report_cannot_pass(self):
        self.report = {}
        self.assertEqual(self.run_simulation()[0], 1)

    def test_failed_http_check_cannot_pass(self):
        self.report['http_health'] = False
        self.assertEqual(self.run_simulation()[0], 1)

    def test_incorrect_deleted_files_cannot_pass(self):
        self.report['deleted'] = ['uploads/customer-demo.txt']
        self.assertEqual(self.run_simulation()[0], 1)

    def test_worker_cannot_override_host_evidence(self):
        self.report['target_applied'] = True
        self.assertEqual(self.run_simulation()[0], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
