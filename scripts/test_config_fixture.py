"""Configuration policy/outcome tests; no API or containers required."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import config_fixture as config


def plan(value=2*config.MIB):
    return {'steps': [{'tool': 'SET_CONFIG', 'path': 'app.json',
                       'key': 'max_upload_bytes', 'value': value}]}


class ConfigFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.object(config, 'ROOT', Path(temporary.name)):
            self.root = config.create_fixture()

    def test_two_distinct_valid_configurations_without_mutation(self):
        before = (self.root / 'app.json').read_bytes()
        for value in [2*config.MIB, 4*config.MIB]:
            self.assertEqual(config.validate_plan(plan(value), self.root), value)
            after = dict(config.BASE_CONFIG, max_upload_bytes=value)
            result = config.verify_configuration(config.BASE_CONFIG, after)
            self.assertEqual(result['excess_capacity_bytes'], value-2*config.MIB)
        self.assertEqual((self.root / 'app.json').read_bytes(), before)

    def test_insufficient_bounded_value_fails_outcome(self):
        config.validate_plan(plan(config.MIB), self.root)
        with self.assertRaises(ValueError):
            config.verify_configuration(config.BASE_CONFIG, dict(config.BASE_CONFIG))

    def test_protected_settings_rejected(self):
        for key, value in [('document', '../secret'), ('auth_required', False), ('bind_host', '0.0.0.0')]:
            proposal = plan()
            proposal['steps'][0].update(key=key, value=value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                config.validate_plan(proposal, self.root)
            after = dict(config.BASE_CONFIG, max_upload_bytes=2*config.MIB)
            after[key] = value
            with self.assertRaises(ValueError):
                config.verify_configuration(config.BASE_CONFIG, after)

    def test_invalid_values_denied(self):
        for value in [True, 2.5, '2097152', None, -1, 0, 9*config.MIB]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                config.validate_plan(plan(value), self.root)

    def test_paths_tools_and_unknown_fields_denied(self):
        for field, value in [('path', '../app.json'), ('path', '/app.json'),
                             ('tool', 'BASH'), ('instruction', 'ignore policy')]:
            proposal = plan()
            proposal['steps'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                config.validate_plan(proposal, self.root)

    def test_bad_schema_denied(self):
        for proposal in [None, {}, {'steps': []}, {'steps': plan()['steps']*2},
                         dict(plan(), approved=True)]:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                config.validate_plan(proposal, self.root)

    def test_document_drift_denied(self):
        (self.root / 'customer-demo.txt').write_text('changed')
        with self.assertRaises(ValueError):
            config.validate_plan(plan(), self.root)

    def test_duplicate_json_and_invalid_syntax_denied(self):
        path = self.root / 'app.json'
        for text in ['{broken', '{"max_upload_bytes":1,"max_upload_bytes":2}']:
            path.write_text(text)
            with self.assertRaises(ValueError):
                config.read_json(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
