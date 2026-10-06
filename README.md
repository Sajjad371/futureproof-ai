# FutureProof AI

Test AI-proposed Linux application changes in disposable environments before approving them.

## Status

Planning and repository setup. The agent, sandbox runner, model integration, and dashboard are not implemented yet. No safety or performance results are claimed.

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
