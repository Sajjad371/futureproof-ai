import unittest
from unittest.mock import patch, Mock
import dashboard_jobs as jobs


class DashboardJobsTests(unittest.TestCase):
    def test_failure_messages_do_not_echo_process_output(self):
        manager = jobs.Jobs()
        failures = [(jobs.subprocess.TimeoutExpired('secret', 1), 'timeout'),
                    (OSError('secret'), 'launch_failed')]
        for error, kind in failures:
            with patch.object(jobs.subprocess, 'run', side_effect=error):
                manager.run(['fixed'])
            self.assertEqual(manager.status()['failure_kind'], kind)
            self.assertNotIn('secret', str(manager.status()))

    def test_execution_requires_exact_scope_and_confirmation(self):
        body = {'family': 'configuration', 'fixture': 'config-demo', 'action': 'apply',
                'approval': 'config-approval-' + 'a'*32 + '.json', 'confirmation': 'APPLY config-demo'}
        self.assertEqual(jobs.execution_command(body)[-3:], ['apply', 'config-demo', body['approval']])
        for key, value in [('family', 'restart'), ('fixture', '../config-demo'),
                           ('approval', '../approval.json'), ('confirmation', 'yes'), ('action', 'shell')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                jobs.execution_command(dict(body, **{key: value}))
        recovery = dict(body, action='recover', confirmation='RECOVER config-demo')
        self.assertEqual(jobs.execution_command(recovery)[-3], 'recover')

    def test_execution_dispatch_and_duplicate_denial(self):
        body = {'family': 'configuration', 'fixture': 'config-demo', 'action': 'apply',
                'approval': 'config-approval-' + 'a'*32 + '.json', 'confirmation': 'APPLY config-demo'}
        manager = jobs.Jobs()
        with patch.object(jobs.threading, 'Thread') as thread:
            manager.submit(body)
            self.assertTrue(thread.called)
            with self.assertRaises(ValueError):
                manager.submit(body)

    def test_ai_action_is_explicit_and_configuration_only(self):
        self.assertTrue(jobs.command('configuration', 'config-demo', 'ai_compare')[1].endswith('compare_config.py'))
        self.assertTrue(jobs.command('configuration', 'config-demo')[1].endswith('check_config_container.py'))
        for action in ('apply', 'approve', 'shell'):
            with self.assertRaises(ValueError):
                jobs.command('configuration', 'config-demo', action)
        with self.assertRaises(ValueError):
            jobs.command('restart', 'restart-demo', 'ai_compare')

    def test_only_fixed_commands_allowed(self):
        self.assertTrue(jobs.command('restart', 'restart-demo')[1].endswith('check_restart_container.py'))
        for family, fixture in [('cleanup', 'cleanup-demo'), ('restart', '../restart-demo'),
                                ('restart', 'restart-demo;reboot'), ('shell', 'test')]:
            with self.assertRaises(ValueError):
                jobs.command(family, fixture)

    def test_duplicate_running_job_denied(self):
        manager = jobs.Jobs()
        with patch.object(jobs.threading, 'Thread'):
            manager.submit({'family': 'restart', 'fixture': 'restart-demo'})
            with self.assertRaises(ValueError):
                manager.submit({'family': 'restart', 'fixture': 'restart-demo'})

    def test_failed_runner_cannot_pass(self):
        manager = jobs.Jobs()
        with patch.object(jobs.subprocess, 'run', return_value=Mock(returncode=1)):
            manager.run(['fixed-command'])
        self.assertEqual(manager.status()['status'], 'failed')

    def test_unknown_fields_denied(self):
        with self.assertRaises(ValueError):
            jobs.Jobs().submit({'family': 'restart', 'fixture': 'restart-demo', 'command': 'reboot'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
