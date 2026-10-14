import json
from pathlib import Path
import tempfile
import unittest
from evaluation_summary import summaries


class SummaryTests(unittest.TestCase):
    def test_projection_rejects_inconsistent_totals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'artifacts/evaluations'
            directory.mkdir(parents=True)
            path = directory / 'ai-evaluation-demo.json'
            report = {'status': 'completed', 'passed': 1, 'total': 1,
                      'rows': [{'passed': True}], 'secret': 'private'}
            path.write_text(json.dumps(report))
            result = summaries(root)
            self.assertEqual(result['reports'][0]['passed'], 1)
            self.assertNotIn('private', json.dumps(result))
            report['total'] = 15
            path.write_text(json.dumps(report))
            self.assertEqual(summaries(root)['skipped'], 1)

    def test_partial_report_is_not_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'artifacts/evaluations'
            directory.mkdir(parents=True)
            (directory / 'container-evaluation-demo.json').write_text(json.dumps(
                {'status': 'running', 'rows': [{'passed': False}]}))
            self.assertEqual(summaries(root)['reports'][0]['status'], 'incomplete')


if __name__ == '__main__':
    unittest.main(verbosity=2)
