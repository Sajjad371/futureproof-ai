"""Approval tests use synthetic evidence; they do not run containers or API calls."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import restart_fixture as fixture
from plan_restart import generate
from check_restart_container import snapshot
from restart_http_worker import CHECKS
from approval_state import digest
from approve_restart import approve, review


class RestartApprovalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.object(fixture, 'ROOT', Path(temp.name)):
            self.root = fixture.create_fixture()
        self.plan = generate(self.root, lambda _: {'steps': [
            {'tool': 'RESTART_SERVICE', 'service': fixture.SERVICE}]})
        record = json.loads(self.plan.read_text())
        self.simulation = 'futureproof-restart-123456789abc.json'
        self.evidence = {'status': 'passed', 'fixture': self.root.name,
            'original_unchanged': True, 'target_applied': False,
            'baseline_hashes': snapshot(self.root), 'candidate_source': 'validated planning record',
            'plan_file': self.plan.name, 'plan_sha256': record['plan_sha256'],
            'planning_sha256': digest(record), 'checks': dict(status='passed',
                before_revision=1, after_revision=2, **{k: True for k in CHECKS})}
        self.save()

    def save(self):
        (self.root / self.simulation).write_text(json.dumps(self.evidence))

    def test_approval_exact_scope_expiry_and_no_mutation(self):
        before = snapshot(self.root)
        path = approve(self.root, self.simulation, lambda _: 'APPROVE ' + self.root.name)
        record = json.loads(path.read_text())
        self.assertEqual(record['binding'], review(self.root, self.simulation))
        self.assertEqual(record['scope'], {'fixture': self.root.name, 'service': fixture.SERVICE, 'revision': 2})
        self.assertIs(record['target_applied'], False)
        self.assertEqual(datetime.fromisoformat(record['expires_at']) -
                         datetime.fromisoformat(record['approved_at']), timedelta(hours=24))
        self.assertEqual(snapshot(self.root), before)

    def test_wrong_confirmation_denied(self):
        with self.assertRaises(ValueError):
            approve(self.root, self.simulation, lambda _: 'yes')
        self.assertEqual(list(self.root.glob('restart-approval-*.json')), [])

    def test_failed_or_unbound_simulation_denied(self):
        for field, value in [('status', 'failed'), ('candidate_source', 'fixed'),
                             ('original_unchanged', False), ('fixture', 'restart-other')]:
            original = self.evidence[field]
            self.evidence[field] = value
            self.save()
            with self.assertRaises(ValueError):
                review(self.root, self.simulation)
            self.evidence[field] = original

    def test_changed_plan_record_denied(self):
        record = json.loads(self.plan.read_text())
        record['model'] = 'changed'
        self.plan.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            review(self.root, self.simulation)

    def test_changed_fixture_denied(self):
        (self.root / 'customer-demo.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            review(self.root, self.simulation)

    def test_false_http_check_denied(self):
        self.evidence['checks']['health'] = False
        self.save()
        with self.assertRaises(ValueError):
            review(self.root, self.simulation)

    def test_evidence_change_during_confirmation_denied(self):
        def confirm(_):
            self.evidence['extra'] = 'modified'
            self.save()
            return 'APPROVE ' + self.root.name
        with self.assertRaises(ValueError):
            approve(self.root, self.simulation, confirm)
        self.assertEqual(list(self.root.glob('restart-approval-*.json')), [])

    def test_fixture_change_during_confirmation_denied(self):
        def confirm(_):
            (self.root / 'app.json').write_text('{}')
            return 'APPROVE ' + self.root.name
        with self.assertRaises(ValueError):
            approve(self.root, self.simulation, confirm)

    def test_path_escape_denied(self):
        with self.assertRaises(ValueError):
            review(self.root, '../' + self.simulation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
