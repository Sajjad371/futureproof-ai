# FutureProof AI

Test AI-proposed Linux application changes in disposable environments before approving them.

## Status

Version 1 foundation: a Nebius connection smoke test, synthetic cleanup fixture generator, and restricted Podman baseline check are implemented. The baseline check verifies file hashes, HTTP health, and protected document retrieval. Planning, cleanup policy enforcement, action execution, and the dashboard are not implemented yet.

## Run the current checks

From the repository folder in Ubuntu with Python 3.11+ and rootless Podman installed:

```bash
python3 scripts/check_nebius.py --check-config
python3 scripts/check_nebius.py
python3 scripts/create_demo_fixture.py
python3 scripts/check_demo_container.py
```

The Nebius checks read local `.env` configuration. Copy `.env.example` to `.env` only if `.env` does not already exist, then supply your own key. The live check uses API credits. Never commit `.env`.

The container check downloads a Python image, builds only synthetic fixture data into a temporary image, and runs without host mounts or external network access. It uses a read-only root filesystem, non-root user, dropped capabilities, no-new-privileges, and memory/CPU/PID limits. Temporary container/image cleanup is attempted afterward; the base image and local fixtures remain. No cleanup action is performed against fixture files.

Validation recorded on October 7, 2026: the real Nebius smoke test passed; the developer reported the baseline container check passing on Ubuntu 24.04 / WSL 2 with rootless Podman 4.9.3. These are foundation checks, not a complete security evaluation.

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

Keep API credentials in local environment configuration. Never commit real keys. The example configuration intentionally leaves the endpoint and model unspecified until verified against the account.

## Scope and limits

The first release targets synthetic Linux demo fixtures for cleanup, configuration changes, and service restarts. It does not support arbitrary production administration or unrestricted shell execution. Passing a simulation is evidence under stated conditions, not a universal safety guarantee.
