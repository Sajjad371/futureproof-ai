import json
from pathlib import Path
import tempfile
import unittest
from dashboard import export_summary


class ExportTests(unittest.TestCase):
    def test_projection_excludes_secrets_and_fixture_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / 'artifacts/config-fixtures/config-demo'
            fixture.mkdir(parents=True)
            (root / '.env').write_text('SECRET_SENTINEL')
            (fixture / 'report.json').write_text(json.dumps({'status': 'passed',
                'api_key': 'SECRET_SENTINEL', 'checks': {'health': True, 'unknown': 'SECRET_SENTINEL'}}))
            result = export_summary(root)
            self.assertNotIn('SECRET_SENTINEL', json.dumps(result))
            self.assertEqual(result['runs']['records'][0]['details']['checks'], {'health': True})
            self.assertEqual(result['schema_version'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
