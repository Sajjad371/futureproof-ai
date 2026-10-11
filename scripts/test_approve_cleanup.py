"""Approval tests use isolated fixtures; no API or containers required."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import create_demo_fixture
from approval_state import binding
from approve_cleanup import approve


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.object(create_demo_fixture, 'ROOT', Path(self.temp.name)), contextlib.redirect_stdout(io.StringIO()):
            self.fixture = create_demo_fixture.main()
        self.plan_path = self.fixture / 'planning-result.json'
        self.plan = {'status': 'policy_passed', 'plan': {'steps': [
            {'tool': 'DELETE_FILE', 'path': 'uploads/old.tmp'}]}}
        self.plan_path.write_text(json.dumps(self.plan))
        self.evidence_path = self.fixture / 'futureproof-simulation-123456abcdef.json'
        self.evidence = {'evidence_version': 2, 'binding': binding(self.fixture),
                         'status': 'passed', 'original_unchanged': True, 'target_applied': False,
                         'http_health': True, 'document_download': True,
                         'container': self.evidence_path.stem, 'deleted': ['uploads/old.tmp']}
        self.save_evidence()

    def save_evidence(self):
        self.evidence_path.write_text(json.dumps(self.evidence))

    def confirm(self, prompt):
        return 'APPROVE ' + self.evidence_path.stem

    def run_approval(self, confirm=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return approve(self.fixture, self.evidence_path, confirm or self.confirm)

    def assert_denied(self, confirm=None):
        with self.assertRaises(ValueError):
            self.run_approval(confirm)
        self.assertEqual(list(self.fixture.glob('approval-*.json')), [])

    def test_explicit_confirmation_records_approval_without_deletion(self):
        output = self.run_approval()
        record = json.loads(output.read_text())
        self.assertEqual(record['binding'], self.evidence['binding'])
        self.assertFalse(record['target_applied'])
        self.assertTrue((self.fixture / 'uploads/old.tmp').exists())

    def test_wrong_confirmation_denied(self):
        self.assert_denied(lambda _: 'yes')

    def test_old_evidence_denied(self):
        del self.evidence['binding']
        self.save_evidence()
        self.assert_denied()

    def test_failed_simulation_denied(self):
        self.evidence['status'] = 'failed'
        self.save_evidence()
        self.assert_denied()

    def test_changed_plan_denied(self):
        self.plan['plan']['steps'][0]['path'] = 'uploads/recent.tmp'
        self.plan_path.write_text(json.dumps(self.plan))
        self.assert_denied()

    def test_protected_content_drift_with_restored_timestamp_denied(self):
        path = self.fixture / 'uploads/customer-demo.txt'
        before = path.stat()
        path.write_bytes(b'x' * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assert_denied()

    def test_added_file_denied(self):
        (self.fixture / 'uploads/new.tmp').write_text('new')
        self.assert_denied()

    def test_manifest_change_denied(self):
        path = self.fixture / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['goal'] = 'changed goal'
        path.write_text(json.dumps(manifest))
        self.assert_denied()

    def test_state_change_during_confirmation_denied(self):
        def change(prompt):
            (self.fixture / 'uploads/customer-demo.txt').write_text('changed')
            return self.confirm(prompt)
        self.assert_denied(change)

    def test_evidence_change_during_confirmation_denied(self):
        def change(prompt):
            self.evidence['extra'] = 'changed'
            self.save_evidence()
            return self.confirm(prompt)
        self.assert_denied(change)


if __name__ == '__main__':
    unittest.main(verbosity=2)
