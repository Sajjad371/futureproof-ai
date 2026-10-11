"""Exercise real file changes and loopback HTTP checks on temporary fixtures only."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
import apply_cleanup as executor
from approval_state import binding
import test_approve_cleanup


class ApplyTests(unittest.TestCase):
    def setUp(self):
        helper = test_approve_cleanup.ApprovalTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.fixture = helper.fixture
        with contextlib.redirect_stdout(io.StringIO()):
            self.approval = helper.run_approval()
        self.before = binding(self.fixture)

    def test_apply_then_recover_restores_exact_state(self):
        transaction = executor.apply(self.fixture, self.approval)
        self.assertFalse((self.fixture / executor.TARGET).exists())
        self.assertTrue((transaction / 'old.tmp').exists())
        self.assertEqual(json.loads((transaction / 'result.json').read_text())['status'], 'applied')
        executor.recover(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)

    def test_stale_approval_denied_without_deletion(self):
        (self.fixture / 'uploads/recent.tmp').write_text('changed')
        with self.assertRaises(ValueError):
            executor.apply(self.fixture, self.approval)
        self.assertTrue((self.fixture / executor.TARGET).exists())
        self.assertEqual(list(self.fixture.glob('apply-*')), [])

    def test_repeat_after_success_reports_used_approval(self):
        transaction = executor.apply(self.fixture, self.approval)
        with self.assertRaisesRegex(FileExistsError, 'already has an application attempt'):
            executor.apply(self.fixture, self.approval)
        self.assertEqual(json.loads((transaction / 'result.json').read_text())['status'], 'applied')
        self.assertTrue((transaction / 'old.tmp').exists())

    def test_consumed_approval_denied_even_after_restore(self):
        executor.apply(self.fixture, self.approval)
        executor.recover(self.fixture, self.approval)
        with self.assertRaises(FileExistsError):
            executor.apply(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)

    def test_verification_failure_automatically_restores(self):
        real = executor.verify_target
        def fail_after_delete(fixture, manifest, deleted):
            if deleted:
                raise ValueError('injected verification failure')
            return real(fixture, manifest, deleted)
        with patch.object(executor, 'verify_target', side_effect=fail_after_delete):
            with self.assertRaisesRegex(RuntimeError, 'original demo state restored'):
                executor.apply(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)

    def test_backup_failure_prevents_deletion(self):
        with patch.object(executor.shutil, 'copy2', side_effect=OSError('injected backup failure')):
            with self.assertRaises(OSError):
                executor.apply(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)

    def test_recovery_refuses_to_overwrite_new_content(self):
        executor.apply(self.fixture, self.approval)
        (self.fixture / executor.TARGET).write_text('new user content')
        with self.assertRaises(ValueError):
            executor.recover(self.fixture, self.approval)
        self.assertEqual((self.fixture / executor.TARGET).read_text(), 'new user content')

    def test_corrupt_backup_recovery_denied(self):
        transaction = executor.apply(self.fixture, self.approval)
        (transaction / 'old.tmp').write_text('corrupt')
        with self.assertRaises(ValueError):
            executor.recover(self.fixture, self.approval)
        self.assertFalse((self.fixture / executor.TARGET).exists())

    def test_concurrent_apply_denied(self):
        with executor.locked(self.fixture):
            with self.assertRaises(OSError):
                executor.apply(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)

    def test_interrupted_after_delete_can_recover(self):
        # SystemExit emulates interruption that bypasses the normal exception recovery.
        with patch.object(executor, 'verify_target', side_effect=SystemExit('interrupted')):
            with self.assertRaises(SystemExit):
                executor.apply(self.fixture, self.approval)
        self.assertFalse((self.fixture / executor.TARGET).exists())
        executor.recover(self.fixture, self.approval)
        self.assertEqual(binding(self.fixture), self.before)



if __name__ == '__main__':
    unittest.main(verbosity=2)
