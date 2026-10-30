"""Additional trusted-inventory variations; no model calls or deletions."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from cleanup_policy import PolicyDenied, validate_plan


class CleanupVariations(unittest.TestCase):
    def test_retention_second_boundaries_and_content_sizes(self):
        for age, allowed in [(30*86400-1, False), (30*86400, False), (30*86400+1, True), (90*86400, True)]:
            for content in [b'', b'x', b'x'*65536]:
                with self.subTest(age=age, size=len(content)), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / 'uploads').mkdir()
                    target = root / 'uploads/varied.tmp'
                    target.write_bytes(content)
                    modified = 1800000000-age
                    os.utime(target, (modified, modified))
                    manifest = {'fixture_version': 1, 'retention_days': 30, 'created_at': 1800000000,
                        'files': [{'path': 'uploads/varied.tmp', 'modified_at': modified,
                            'size_bytes': len(content), 'protected': False,
                            'sha256': hashlib.sha256(content).hexdigest()}]}
                    plan = {'steps': [{'tool': 'DELETE_FILE', 'path': 'uploads/varied.tmp'}]}
                    if allowed:
                        self.assertEqual(validate_plan(plan, manifest, root), ['uploads/varied.tmp'])
                    else:
                        with self.assertRaises(PolicyDenied):
                            validate_plan(plan, manifest, root)
                    self.assertEqual(target.read_bytes(), content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
