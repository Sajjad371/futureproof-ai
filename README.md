# FutureProof AI

Test AI-proposed Linux application changes in disposable environments before approving them.

## Status

Version 1 now supports one complete simulation flow: generate a structured cleanup plan through Nebius, validate it against a narrow read-only policy, execute it inside a disposable restricted Podman container, and verify the result. Human approval, target application, recovery, candidate comparison, and the dashboard are not implemented yet.

## Run the current checks

From the repository folder in Ubuntu with Python 3.11+ and rootless Podman installed:

```bash
python3 scripts/check_nebius.py --check-config
python3 scripts/check_nebius.py
python3 scripts/create_demo_fixture.py
python3 scripts/check_demo_container.py
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/plan_cleanup.py
```

The planner creates a new fixture and prints its directory. Use that directory name in the next command (replace `cleanup-REPLACE_ME`):

```bash
python3 scripts/simulate_cleanup.py cleanup-REPLACE_ME
```

The Nebius checks read local `.env` configuration. Copy `.env.example` to `.env` only if `.env` does not already exist, then supply your own key. The live check uses API credits. Never commit `.env`.

The container check downloads a Python image, builds only synthetic fixture data into a temporary image, and runs without host mounts or external network access. It uses a read-only root filesystem, non-root user, dropped capabilities, no-new-privileges, and memory/CPU/PID limits. Temporary container/image cleanup is attempted afterward; the base image and local fixtures remain. The baseline check performs no cleanup. The simulation deletes eligible files only from a container-local copy, verifies preserved file hashes and HTTP behavior, checks the original fixture remains unchanged, and writes JSON evidence under ignored `artifacts/`. The host rejects incomplete or inconsistent worker reports.

Validation recorded on October 7, 2026: the real Nebius smoke test passed; the developer reported the baseline container check passing on Ubuntu 24.04 / WSL 2 with rootless Podman 4.9.3. On October 11, 2026, the developer reported successful live Nebius planning, all 10 simulation tests, and a real Podman cleanup simulation with the strengthened report checks. Local test discovery ran 22 tests: 21 passed and one Windows symlink test was skipped; the developer previously ran all nine policy tests successfully in Ubuntu. Simulation unit tests mock Podman responses; the real container run is separate. This is a controlled demo, not a complete security evaluation.

## Planned workflow

1. Inspect a controlled demo fixture.
2. Generate structured candidate plans with an NVIDIA model through Nebius.
3. Validate plans and enforce server-side policy.
4. Execute permitted candidates in independent disposable environments.
5. Verify application behavior and requested outcomes.
6. Compare evidence and request approval for an exact plan.
7. Apply to the controlled demo target, verify, and report recovery outcomes if needed.

## Delivery plan

- October 6–10: One connected cleanup scenario.
- October 11–15: Candidate comparison, approval, application, and recovery.
- October 16–20: Configuration/restart fixtures, stronger checks, dashboard, and evaluation.
- October 21–25: Release testing and reproducibility.
- October 26–29: Submission preparation and buffer.

See [the acceptance checklist](docs/acceptance-checklist.md) for requirements and verification gates.

## Development setup

Planned stack: Python 3.11+, FastAPI, Pydantic, Next.js/React, SQLite, and a restricted Linux container runtime. Dependency versions and executable setup commands will be added with the first implementation.

Keep API credentials in local environment configuration. Never commit real keys. The example configuration includes the verified Nebius endpoint and model ID, with an empty API key.

## Scope and limits

The first release targets synthetic Linux demo fixtures for cleanup, configuration changes, and service restarts. It does not support arbitrary production administration or unrestricted shell execution. Passing a simulation is evidence under stated conditions, not a universal safety guarantee.
