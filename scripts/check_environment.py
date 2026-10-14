"""Read-only setup preflight. No installs, model requests, or container runs."""
import platform
import shutil
import subprocess
import sys


def main():
    checks = []
    checks.append(('Python 3.11+', sys.version_info >= (3, 11)))
    checks.append(('Linux runtime (run this inside Ubuntu/WSL)', platform.system() == 'Linux'))
    executable = shutil.which('podman')
    checks.append(('Podman installed', executable is not None))
    if executable:
        try:
            result = subprocess.run([executable, 'info', '--format', '{{.Host.Security.Rootless}}'],
                                    capture_output=True, text=True, timeout=30)
            checks.append(('Rootless Podman available', result.returncode == 0 and result.stdout.strip() == 'true'))
        except (OSError, subprocess.SubprocessError):
            checks.append(('Rootless Podman available', False))
    for name, passed in checks:
        print(('PASS: ' if passed else 'FAIL: ') + name)
    print('No API calls, software installation, or target changes performed.')
    print('This checks prerequisites only; a fresh clone and live smoke test are still required.')
    return 0 if all(passed for _, passed in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
