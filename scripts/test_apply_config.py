"""Real configuration apply/restore and HTTP checks in temporary fixtures."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import test_approve_config
import apply_config as executor
from check_config_container import snapshot


class ConfigApplyTests(unittest.TestCase):
    def setUp(self):
        helper = test_approve_config.ConfigApprovalTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.fixture = helper.fixture
        self.approval = helper.run_approval()
        self.before = snapshot(self.fixture)

    def test_apply_and_restore_with_real_http(self):
        tx = executor.apply(self.fixture, self.approval)
        self.assertEqual(json.loads((self.fixture / 'app.json').read_text())['max_upload_bytes'], 2097152)
        self.assertEqual(json.loads((tx / 'result.json').read_text())['status'], 'applied')
        executor.recover(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_expired_approval_rejected(self):
        approval = json.loads(self.approval.read_text())
        approval['approved_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        approval['expires_at'] = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        self.approval.write_text(json.dumps(approval))
        with self.assertRaisesRegex(ValueError, 'expired'):
            executor.apply(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_changed_scope_rejected(self):
        approval = json.loads(self.approval.read_text())
        approval['scope']['value'] = 4194304
        self.approval.write_text(json.dumps(approval))
        with self.assertRaises(ValueError):
            executor.apply(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_backup_failure_prevents_change(self):
        with patch.object(executor.shutil, 'copy2', side_effect=OSError('backup failure')):
            with self.assertRaises(OSError):
                executor.apply(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_postflight_failure_restores(self):
        original = executor.verify
        def fail(fixture, record, restored=False):
            if not restored:
                raise ValueError('injected failure')
            return original(fixture, record, restored)
        with patch.object(executor, 'verify', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'original configuration restored'):
                executor.apply(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_approval_cannot_be_replayed_after_recovery(self):
        executor.apply(self.fixture, self.approval)
        executor.recover(self.fixture, self.approval)
        with self.assertRaisesRegex(ValueError, 'already used'):
            executor.apply(self.fixture, self.approval)

    def test_interruption_can_be_recovered(self):
        with patch.object(executor, 'verify', side_effect=SystemExit('interruption')):
            with self.assertRaises(SystemExit):
                executor.apply(self.fixture, self.approval)
        executor.recover(self.fixture, self.approval)
        self.assertEqual(snapshot(self.fixture), self.before)

    def test_recovery_preserves_unexpected_edit(self):
        executor.apply(self.fixture, self.approval)
        (self.fixture / 'app.json').write_text('{"unexpected": true}')
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            executor.recover(self.fixture, self.approval)
        self.assertEqual((self.fixture / 'app.json').read_text(), '{"unexpected": true}')

    def test_corrupt_backup_rejected(self):
        tx = executor.apply(self.fixture, self.approval)
        (tx / 'app.backup.json').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'Backup verification'):
            executor.recover(self.fixture, self.approval)


if __name__ == '__main__':
    unittest.main(verbosity=2)
