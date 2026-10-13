"""Exercise approved restart and recovery with real local child processes."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
import apply_restart as app
from approve_restart import approve
import test_approve_restart as approval_tests


class RestartApplyTests(unittest.TestCase):
    def setUp(self):
        # Reuse only the synthetic evidence setup, not the approval test methods.
        approval_tests.RestartApprovalTests.setUp(self)
        self.approval = approve(self.root, self.simulation, lambda _: 'APPROVE ' + self.root.name)

    def save(self):
        approval_tests.RestartApprovalTests.save(self)

    def test_real_apply_recover_and_replay_denial(self):
        path = app.run_session(self.root, self.approval, lambda _: 'RECOVER')
        result = json.loads((path / 'result.json').read_text())
        self.assertEqual(result['status'], 'restored')
        self.assertEqual(result['application_checks']['revision'], 2)
        self.assertEqual(result['recovery_checks']['revision'], 1)
        self.assertTrue(result['owned_processes_stopped'])
        with self.assertRaises(ValueError):
            app.run_session(self.root, self.approval)

    def test_expired_approval_denied_before_process(self):
        record = json.loads(self.approval.read_text())
        begin = datetime.now(timezone.utc) - timedelta(days=2)
        record.update(approved_at=begin.isoformat(), expires_at=(begin+timedelta(hours=24)).isoformat())
        self.approval.write_text(json.dumps(record))
        with patch.object(app, 'start') as start, self.assertRaises(ValueError):
            app.run_session(self.root, self.approval)
        start.assert_not_called()

    def test_changed_scope_denied(self):
        record = json.loads(self.approval.read_text())
        record['scope']['service'] = 'sshd'
        self.approval.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            app.run_session(self.root, self.approval)

    def test_interrupt_recovers_and_stops_processes(self):
        def interrupt(_):
            raise KeyboardInterrupt()
        with self.assertRaises(RuntimeError):
            app.run_session(self.root, self.approval, interrupt)
        record = json.loads((self.root / ('apply-' + self.approval.stem) / 'result.json').read_text())
        self.assertEqual(record['status'], 'restored')
        self.assertTrue(record['owned_processes_stopped'])

    def test_postflight_failure_recovers(self):
        real_verify = app.verify
        def fail(*args):
            if args[4] == 2:
                raise ValueError('Injected postflight failure')
            return real_verify(*args)
        with patch.object(app, 'verify', side_effect=fail), self.assertRaises(RuntimeError):
            app.run_session(self.root, self.approval)
        record = json.loads((self.root / ('apply-' + self.approval.stem) / 'result.json').read_text())
        self.assertEqual(record['status'], 'restored')

    def test_recovery_preserves_unexpected_edit(self):
        def change(_):
            (self.root / 'app.json').write_text('unexpected edit')
            return 'RECOVER'
        with self.assertRaises(RuntimeError):
            app.run_session(self.root, self.approval, change)
        self.assertEqual((self.root / 'app.json').read_text(), 'unexpected edit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
