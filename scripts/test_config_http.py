"""Real loopback HTTP checks on temporary fixtures; no Podman or API needed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import config_fixture as config
from config_http_worker import run_checks
from check_config_container import check_report


class ConfigHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def fixture(self):
        with patch.object(config, 'ROOT', Path(self.temp.name)):
            return config.create_fixture()

    def test_two_mib_real_upload_and_rejections(self):
        report = run_checks(self.fixture(), 2*config.MIB)
        check_report(report, 2*config.MIB)
        self.assertTrue(report['upload_roundtrip'])
        self.assertTrue(report['oversized_rejected'])
        self.assertTrue(report['unauthorized_rejected'])

    def test_four_mib_alternative_passes(self):
        report = run_checks(self.fixture(), 4*config.MIB)
        check_report(report, 4*config.MIB)
        self.assertEqual(report['excess_capacity_bytes'], 2*config.MIB)

    def test_insufficient_limit_fails(self):
        with self.assertRaisesRegex(ValueError, 'does not satisfy'):
            run_checks(self.fixture(), config.MIB)

    def test_out_of_policy_limit_fails_without_change(self):
        root = self.fixture()
        before = (root / 'app.json').read_bytes()
        with self.assertRaises(ValueError):
            run_checks(root, 9*config.MIB)
        self.assertEqual((root / 'app.json').read_bytes(), before)

    def test_missing_or_false_checks_rejected(self):
        report = run_checks(self.fixture(), 2*config.MIB)
        for key in ['baseline_rejected', 'upload_roundtrip', 'oversized_rejected',
                    'unauthorized_rejected', 'health', 'document_preserved', 'protected_settings']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_report(dict(report, **{key: False}), 2*config.MIB)
        with self.assertRaises(ValueError):
            check_report({}, 2*config.MIB)
        with self.assertRaises(ValueError):
            check_report(report, 4*config.MIB)


if __name__ == '__main__':
    unittest.main(verbosity=2)
