from pathlib import Path
import unittest
from unittest.mock import patch
import dashboard_approval as module


class ReviewTicketTests(unittest.TestCase):
    def setUp(self):
        self.reviews = module.Reviews()
        self.binding = {'candidate': 1, 'plan_sha256': 'test-hash'}
        self.review = patch.object(module, 'review', return_value=(Path('config-candidate'), self.binding, 2097152))
        self.review.start()
        self.addCleanup(self.review.stop)
        self.body = {'fixture': 'config-demo', 'comparison': 'config-comparison-' + 'a'*32 + '.json'}

    def test_review_displays_exact_scope(self):
        result = self.reviews.prepare(self.body)
        self.assertEqual(result['confirmation'], 'APPROVE config-candidate')
        self.assertEqual(result['new_limit_bytes'], 2097152)

    def test_confirmation_delegated_and_ticket_consumed(self):
        result = self.reviews.prepare(self.body)
        def approve(baseline, comparison, confirm):
            self.assertEqual(confirm(''), result['confirmation'])
            return Path('config-candidate/config-approval-test.json')
        body = {'ticket': result['ticket'], 'confirmation': result['confirmation']}
        with patch.object(module, 'approve', side_effect=approve):
            self.assertFalse(self.reviews.confirm(body)['target_applied'])
        with self.assertRaises(ValueError):
            self.reviews.confirm(body)

    def test_changed_evidence_denied(self):
        result = self.reviews.prepare(self.body)
        with patch.object(module, 'review', return_value=(Path('config-candidate'), {}, 2097152)), patch.object(module, 'approve', side_effect=lambda a,b,confirm: confirm('')):
            with self.assertRaises(ValueError):
                self.reviews.confirm({'ticket': result['ticket'], 'confirmation': result['confirmation']})

    def test_expired_ticket_denied(self):
        result = self.reviews.prepare(self.body)
        with patch.object(module.time, 'monotonic', return_value=float('inf')):
            with self.assertRaises(ValueError):
                self.reviews.confirm({'ticket': result['ticket'], 'confirmation': result['confirmation']})

    def test_path_escape_denied(self):
        with self.assertRaises(ValueError):
            self.reviews.prepare(dict(self.body, fixture='../config-demo'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
