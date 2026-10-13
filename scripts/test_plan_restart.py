"""Restart planner rejection and simulation binding checks without API calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import restart_fixture as fixture
from plan_restart import generate
from check_restart_container import load_plan, snapshot


def valid(_):
    return {'steps': [{'tool': 'RESTART_SERVICE', 'service': fixture.SERVICE}]}


class RestartPlannerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.object(fixture, 'ROOT', Path(temporary.name)):
            self.root = fixture.create_fixture()

    def test_valid_plan_bound_without_execution(self):
        before = snapshot(self.root)
        path = generate(self.root, valid)
        record = load_plan(self.root, path.name, before)
        self.assertEqual(record['plan'], valid(None))
        self.assertIs(record['actions_executed'], False)
        self.assertEqual(snapshot(self.root), before)

    def test_unsafe_model_output_not_saved(self):
        for proposal in [None, {'steps': []}, {'steps': [{'tool': 'BASH', 'command': 'reboot'}]}]:
            with self.assertRaises(ValueError):
                generate(self.root, lambda _: proposal)
        self.assertEqual(list(self.root.glob('restart-plan-*.json')), [])

    def test_drift_during_request_rejected(self):
        def requester(inventory):
            (self.root / 'customer-demo.txt').write_bytes(b'changed')
            return valid(inventory)
        with self.assertRaises(ValueError):
            generate(self.root, requester)
        self.assertEqual(list(self.root.glob('restart-plan-*.json')), [])

    def test_changed_record_rejected(self):
        path = generate(self.root, valid)
        record = json.loads(path.read_text())
        record['plan']['steps'][0]['service'] = 'sshd'
        path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            load_plan(self.root, path.name, snapshot(self.root))

    def test_stale_binding_and_path_escape_rejected(self):
        path = generate(self.root, valid)
        with self.assertRaises(ValueError):
            load_plan(self.root, path.name, {})
        with self.assertRaises(ValueError):
            load_plan(self.root, '../' + path.name, snapshot(self.root))


if __name__ == '__main__':
    unittest.main(verbosity=2)
