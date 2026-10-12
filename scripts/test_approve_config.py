"""Approval checks with temporary data and simulated comparison evidence."""
import contextlib
import io
import json
import unittest
from datetime import datetime, timedelta
import test_compare_config
from compare_config import compare
from approve_config import approve, review


class ConfigApprovalTests(unittest.TestCase):
    def setUp(self):
        helper = test_compare_config.ConfigComparisonTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        self.baseline = helper.baseline
        with contextlib.redirect_stdout(io.StringIO()):
            report, self.path = compare(self.baseline, [test_compare_config.plan(2097152)], helper.runner)
        self.fixture = self.baseline.parent / report['candidates'][0]['fixture']

    def confirm(self, prompt):
        return 'APPROVE ' + self.fixture.name

    def run_approval(self, confirm=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return approve(self.baseline, self.path, confirm=confirm or self.confirm)

    def denied(self, confirm=None):
        with self.assertRaises(ValueError):
            self.run_approval(confirm)
        self.assertEqual(list(self.fixture.glob('config-approval-*.json')), [])

    def test_approval_records_exact_scope_without_mutation(self):
        before = (self.fixture / 'app.json').read_bytes()
        record = json.loads(self.run_approval().read_text())
        self.assertEqual(record['scope']['value'], 2097152)
        self.assertEqual(record['scope']['fixture'], self.fixture.name)
        self.assertEqual(datetime.fromisoformat(record['expires_at'])-datetime.fromisoformat(record['approved_at']), timedelta(hours=24))
        self.assertFalse(record['target_applied'])
        self.assertEqual((self.fixture / 'app.json').read_bytes(), before)

    def test_wrong_confirmation_denied(self):
        self.denied(lambda _: 'yes')

    def test_modified_candidate_denied(self):
        (self.fixture / 'customer-demo.txt').write_text('changed')
        self.denied()

    def test_modified_plan_denied(self):
        path = self.fixture / 'config-plan.json'
        record = json.loads(path.read_text())
        record['plan']['steps'][0]['value'] = 4194304
        path.write_text(json.dumps(record))
        self.denied()

    def test_modified_evidence_denied(self):
        path = next(self.fixture.glob('futureproof-config-*.json'))
        record = json.loads(path.read_text())
        record['checks']['upload_roundtrip'] = False
        path.write_text(json.dumps(record))
        self.denied()

    def test_failed_candidate_denied(self):
        record = json.loads(self.path.read_text())
        record['candidates'][0]['status'] = 'rejected'
        self.path.write_text(json.dumps(record))
        self.denied()

    def test_change_during_confirmation_denied(self):
        def change(prompt):
            (self.fixture / 'app.json').write_text('{}')
            return self.confirm(prompt)
        self.denied(change)

    def test_unknown_candidate_denied(self):
        with self.assertRaises(ValueError):
            review(self.baseline, self.path, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
