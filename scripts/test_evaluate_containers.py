import copy
import unittest
from approval_state import digest
from evaluate_ai import suite
from evaluate_containers import select_cases


class EvaluationContainerTests(unittest.TestCase):
    def setUp(self):
        self.frozen = {'suite': suite(), 'suite_sha256': digest(suite())}
        rows = []
        for case in suite()['cases']:
            plan = {'steps': [{'tool': 'SET_CONFIG', 'path': 'app.json', 'key': 'max_upload_bytes', 'value': case['expected_bytes']}]} if case['expected_bytes'] else {'steps': []}
            rows.append(dict(case, passed=True, policy_allowed=case['expected_bytes'] is not None,
                             validated_plan=plan, response_sha256=digest(plan)))
        self.evaluation = {'suite_sha256': digest(suite()), 'model': suite()['model'],
                          'status': 'completed', 'fixture_unchanged': True, 'actions_executed': False, 'rows': rows}

    def test_only_ten_supported_cases_selected(self):
        chosen = select_cases(self.frozen, self.evaluation)
        self.assertEqual(len(chosen), 10)
        self.assertTrue(all(case['expected_bytes'] is not None for case, _ in chosen))

    def test_changed_plan_denied(self):
        self.evaluation['rows'][0]['validated_plan']['steps'][0]['value'] = 123
        with self.assertRaises(ValueError):
            select_cases(self.frozen, self.evaluation)

    def test_duplicate_or_missing_cases_denied(self):
        for rows in [self.evaluation['rows'][:-1], [self.evaluation['rows'][0]]*15]:
            with self.assertRaises(ValueError):
                select_cases(self.frozen, dict(self.evaluation, rows=rows))

    def test_failed_or_wrong_suite_denied(self):
        for field, value in [('status', 'running'), ('suite_sha256', 'wrong'), ('fixture_unchanged', False)]:
            with self.assertRaises(ValueError):
                select_cases(self.frozen, dict(self.evaluation, **{field: value}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
