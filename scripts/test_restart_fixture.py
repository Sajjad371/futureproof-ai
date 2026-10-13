"""Restart fixture policy checks; no API calls or process control."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import restart_fixture as restart


def plan():
    return {'steps': [{'tool': 'RESTART_SERVICE', 'service': restart.SERVICE}]}


class RestartFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.object(restart, 'ROOT', Path(temporary.name)):
            self.root = restart.create_fixture()

    def test_valid_plan_leaves_all_files_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(restart.validate_plan(plan(), self.root), restart.SERVICE)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_system_services_and_shell_commands_denied(self):
        for service in ['sshd', 'docker', '../futureproof-demo', 'futureproof-demo; reboot']:
            proposal = plan()
            proposal['steps'][0]['service'] = service
            with self.subTest(service=service), self.assertRaises(ValueError):
                restart.validate_plan(proposal, self.root)

    def test_unknown_tools_and_fields_denied(self):
        for field, value in [('tool', 'BASH'), ('command', 'reboot'), ('timeout', 999)]:
            proposal = plan()
            proposal['steps'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                restart.validate_plan(proposal, self.root)

    def test_missing_duplicate_and_invalid_steps_denied(self):
        for proposal in [None, {}, {'steps': []}, {'steps': plan()['steps'] * 2},
                         {'steps': [None]}, dict(plan(), approved=True)]:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                restart.validate_plan(proposal, self.root)

    def test_content_drift_with_restored_timestamp_denied(self):
        path = self.root / 'customer-demo.txt'
        metadata = path.stat()
        data = path.read_bytes()
        path.write_bytes(b'X' + data[1:])
        os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        with self.assertRaises(ValueError):
            restart.validate_plan(plan(), self.root)

    def test_changed_configuration_or_startup_denied(self):
        for name in ['app.json', 'startup.json']:
            original = (self.root / name).read_bytes()
            (self.root / name).write_bytes(b'{}')
            with self.subTest(name=name), self.assertRaises(ValueError):
                restart.inspect(self.root)
            (self.root / name).write_bytes(original)

    def test_missing_file_denied(self):
        (self.root / 'customer-demo.txt').unlink()
        with self.assertRaises(OSError):
            restart.inspect(self.root)

    def test_manifest_tampering_and_duplicate_keys_denied(self):
        for data in ['{}', '{"fixture_version":1,"fixture_version":1}']:
            (self.root / 'manifest.json').write_text(data)
            with self.assertRaises(ValueError):
                restart.inspect(self.root)

    def test_hardlink_denied(self):
        os.link(self.root / 'customer-demo.txt', self.root / 'alias.txt')
        with self.assertRaises(ValueError):
            restart.inspect(self.root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
