from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from approval_display import state


class ApprovalDisplayTests(unittest.TestCase):
    def test_unused_expired_and_consumed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'config-approval-demo.json'
            now = datetime.now(timezone.utc)
            record = {'status': 'approved', 'target_applied': False,
                      'approved_at': now.isoformat(), 'expires_at': (now+timedelta(hours=24)).isoformat()}
            self.assertEqual(state(root, path, record, now), 'unused_not_revalidated')
            self.assertEqual(state(root, path, record, now+timedelta(days=1)), 'expired')
            (root / ('apply-' + path.stem)).mkdir()
            self.assertEqual(state(root, path, record, now), 'consumed')

    def test_missing_or_invalid_expiry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'approval.json'
            record = {'status': 'approved', 'target_applied': False}
            self.assertEqual(state(root, path, record), 'expiry_unknown')
            self.assertEqual(state(root, path, dict(record, expires_at='invalid')), 'invalid')


if __name__ == '__main__':
    unittest.main(verbosity=2)
