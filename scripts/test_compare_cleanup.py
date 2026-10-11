"""Comparison tests mock container execution; no API credits are used."""
import contextlib
import copy
import io
import json
import unittest
import test_approve_cleanup
from approval_state import binding
from compare_cleanup import compare, baseline_state, parse_candidates


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        helper = test_approve_cleanup.ApprovalTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.baseline = helper.fixture
        self.plan = helper.plan['plan']
        self.calls = []
        self.initial = baseline_state(self.baseline)

    def runner(self, fixture):
        self.calls.append(fixture)
        self.assertNotEqual(fixture, self.baseline)
        self.assertEqual(baseline_state(fixture), self.initial)
        path = fixture / 'futureproof-simulation-123456abcdef.json'
        manifest = json.loads((fixture / 'manifest.json').read_text())
        report = {'evidence_version': 2, 'binding': binding(fixture), 'status': 'passed',
                  'original_unchanged': True, 'target_applied': False, 'http_health': True,
                  'document_download': True, 'container': path.stem,
                  'deleted': ['uploads/old.tmp'],
                  'preserved': ['uploads/current.json', 'uploads/customer-demo.txt', 'uploads/recent.tmp'],
                  'removed_file_bytes': next(e['size_bytes'] for e in manifest['files'] if e['path'] == 'uploads/old.tmp')}
        path.write_text(json.dumps(report))
        return path

    def run_compare(self, plans, runner=None):
        with contextlib.redirect_stdout(io.StringIO()):
            result = compare(self.baseline, plans, runner or self.runner)
        self.assertFalse(result['target_applied'])
        self.assertFalse(result['approval_recorded'])
        return result

    def test_valid_candidate_recommended_with_original_unchanged(self):
        result = self.run_compare([self.plan])
        self.assertEqual(result['recommended_candidate'], 1)
        self.assertEqual(baseline_state(self.baseline), self.initial)
        self.assertEqual(len(self.calls), 1)

    def test_duplicates_are_not_presented_as_alternatives(self):
        result = self.run_compare([self.plan, copy.deepcopy(self.plan), self.plan])
        self.assertEqual([r['status'] for r in result['candidates']], ['passed', 'duplicate', 'duplicate'])
        self.assertEqual(len(self.calls), 1)

    def test_unsafe_candidate_rejected_without_simulation(self):
        unsafe = {'steps': [{'tool': 'DELETE_FILE', 'path': 'uploads/customer-demo.txt'}]}
        result = self.run_compare([unsafe, self.plan])
        self.assertEqual(result['recommended_candidate'], 2)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result['candidates'][0]['status'], 'rejected')

    def test_no_passing_candidate_means_no_recommendation(self):
        result = self.run_compare([{'steps': []}, {'steps': [{'tool': 'BASH', 'path': 'uploads/old.tmp'}]}])
        self.assertEqual(result['status'], 'no_candidate_passed')
        self.assertIsNone(result['recommended_candidate'])
        self.assertEqual(self.calls, [])

    def test_simulation_failure_never_ranked(self):
        def failure(fixture):
            raise ValueError('simulated container failure')
        result = self.run_compare([self.plan], failure)
        self.assertIsNone(result['recommended_candidate'])

    def test_false_outcome_report_rejected(self):
        def false_report(fixture):
            path = self.runner(fixture)
            report = json.loads(path.read_text())
            report['removed_file_bytes'] = 999999
            path.write_text(json.dumps(report))
            return path
        self.assertIsNone(self.run_compare([self.plan], false_report)['recommended_candidate'])

    def test_candidate_response_schema(self):
        self.assertEqual(parse_candidates(json.dumps({'candidates': [self.plan]})), [self.plan])
        for value in ['{}', '{"candidates":[]}', '{"candidates":[{},{},{},{}]}',
                      '{"candidates":[{}],"approved":true}', '{"candidates":[],"candidates":[{}]}']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_candidates(value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
