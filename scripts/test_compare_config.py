"""Candidate orchestration tests with simulated container responses; no API calls."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import config_fixture as config
from check_config_container import snapshot
from compare_config import compare


def plan(value):
    return {'steps': [{'tool': 'SET_CONFIG', 'path': 'app.json', 'key': 'max_upload_bytes', 'value': value}]}


class ConfigComparisonTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.object(config, 'ROOT', Path(temp.name)):
            self.baseline = config.create_fixture()
        self.before = snapshot(self.baseline)
        self.calls = []

    def runner(self, fixture, value):
        self.calls.append(fixture)
        self.assertNotEqual(fixture, self.baseline)
        self.assertEqual(snapshot(fixture), self.before)
        if value < 2*config.MIB:
            raise ValueError('Task outcome failed')
        checks = {key: True for key in ['baseline_rejected', 'upload_roundtrip', 'oversized_rejected',
                                       'unauthorized_rejected', 'health', 'document_preserved', 'protected_settings']}
        checks.update(status='passed', configured_upload_bytes=value,
                      required_upload_bytes=2*config.MIB, excess_capacity_bytes=value-2*config.MIB)
        evidence = {'status': 'passed', 'fixture': fixture.name, 'target_applied': False,
                    'original_unchanged': True, 'baseline_hashes': self.before, 'limit_bytes': value, 'checks': checks}
        path = fixture / 'futureproof-config-123456abcdef.json'
        path.write_text(json.dumps(evidence))
        return path

    def run_compare(self, plans, runner=None):
        with contextlib.redirect_stdout(io.StringIO()):
            report, path = compare(self.baseline, plans, runner or self.runner)
        self.assertTrue(path.exists())
        self.assertFalse(report['target_applied'])
        self.assertFalse(report['approval_recorded'])
        self.assertEqual(snapshot(self.baseline), self.before)
        return report

    def test_distinct_candidates_rank_smallest_sufficient_first(self):
        report = self.run_compare([plan(4*config.MIB), plan(2*config.MIB)])
        self.assertEqual(report['recommended_candidate'], 2)
        self.assertEqual(len(set(self.calls)), 2)
        self.assertEqual([r['status'] for r in report['candidates']], ['passed', 'passed'])

    def test_duplicate_not_simulated_twice(self):
        report = self.run_compare([plan(2*config.MIB)]*2)
        self.assertEqual(report['candidates'][1]['status'], 'duplicate')
        self.assertEqual(len(self.calls), 1)

    def test_protected_setting_rejected_before_runner(self):
        proposal = plan(2*config.MIB)
        proposal['steps'][0]['key'] = 'auth_required'
        report = self.run_compare([proposal])
        self.assertIsNone(report['recommended_candidate'])
        self.assertEqual(self.calls, [])

    def test_insufficient_candidate_fails_outcome(self):
        report = self.run_compare([plan(config.MIB)])
        self.assertEqual(report['status'], 'no_candidate_passed')

    def test_container_failure_never_recommended(self):
        def failure(*args):
            raise ValueError('Container failed')
        self.assertIsNone(self.run_compare([plan(2*config.MIB)], failure)['recommended_candidate'])

    def test_mismatched_report_rejected(self):
        def wrong(fixture, value):
            path = self.runner(fixture, value)
            evidence = json.loads(path.read_text())
            evidence['limit_bytes'] = 4*config.MIB
            path.write_text(json.dumps(evidence))
            return path
        self.assertIsNone(self.run_compare([plan(2*config.MIB)], wrong)['recommended_candidate'])

    def test_bad_candidate_count_denied(self):
        for plans in [[], [plan(2*config.MIB)]*4]:
            with self.assertRaises(ValueError):
                self.run_compare(plans)


if __name__ == '__main__':
    unittest.main(verbosity=2)
