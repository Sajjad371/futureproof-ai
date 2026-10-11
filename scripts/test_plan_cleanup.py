import unittest
from plan_cleanup import parse_plan


class PlanParsingTests(unittest.TestCase):
    def test_valid_json(self):
        self.assertEqual(parse_plan('{"steps": []}'), {'steps': []})

    def test_reject_duplicate_keys(self):
        with self.assertRaises(ValueError):
            parse_plan('{"steps": [], "steps": [{"tool":"BASH"}]}')

    def test_reject_non_json_and_oversized_content(self):
        for content in ['```json\n{}\n```', 'not json', None, ' ' * 16001]:
            with self.subTest(content_type=type(content).__name__), self.assertRaises(ValueError):
                parse_plan(content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
