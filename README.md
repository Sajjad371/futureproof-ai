# FutureProof AI

Test AI-proposed Linux application changes in disposable environments before approving them.

## Status

Version 1 now supports one complete simulation flow: generate a structured cleanup plan through Nebius, validate it against a narrow read-only policy, execute it inside a disposable restricted Podman container, and verify the result. The local human-approval command has passed unit tests and a manual Ubuntu run. Controlled demo application and recovery have passed Ubuntu tests and a manual recovery run. The live comparison-to-approval-to-application-to-recovery flow passed in Ubuntu on October 11, 2026, with one valid candidate. Multiple distinct valid strategies remain unverified. The dashboard is not implemented yet.

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

Validation recorded on October 7, 2026: the real Nebius smoke test passed; the developer reported the baseline container check passing on Ubuntu 24.04 / WSL 2 with rootless Podman 4.9.3. On October 11, 2026, the developer reported successful live Nebius planning, all 10 simulation tests, and a real Podman cleanup simulation with the strengthened report checks. Latest local test discovery ran 49 tests: 48 passed and one Windows symlink test was skipped; the developer previously ran all nine policy tests successfully in Ubuntu. Approval and comparison tests also passed in Ubuntu. The live recommended candidate was approved, applied, and restored, with file hashes and HTTP checks passing. Simulation/comparison unit tests mock Podman responses; the real container runs are separate. This is a controlled demo, not a complete security evaluation.

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

## Review and record approval

Run `python3 scripts/test_approve_cleanup.py` to test the approval gate without API calls or containers. Generate a fresh simulation report with the current simulator; older reports lack state fingerprints and are rejected.

```bash
python3 scripts/simulate_cleanup.py cleanup-REPLACE_ME
python3 scripts/approve_cleanup.py cleanup-REPLACE_ME futureproof-simulation-REPLACE_ME.json
```

Use the exact fixture and report names printed by your run. Review the displayed deletion and type the exact `APPROVE ...` phrase only if you agree. The command rechecks the plan, manifest, inventoried file hashes and metadata, and uploads directory membership after confirmation. A successful review writes a unique ignored approval record; it does not delete target files.

These records assume a trusted local user and local filesystem. Hashes detect state mismatch; they do not authenticate records against malicious local edits. The apply command rechecks the approval and state while holding a cooperating-process lock; other programs must not edit the fixture during application. Approval alone does not prevent changes afterward.

## Apply and recover the controlled demo

First run `python3 scripts/test_apply_cleanup.py`. These tests perform real file changes and loopback HTTP checks inside temporary fixtures, with injected failures for recovery paths. They do not touch your existing approved fixture or use API credits.

```bash
python3 scripts/apply_cleanup.py apply cleanup-REPLACE_ME approval-REPLACE_ME.json
python3 scripts/apply_cleanup.py recover cleanup-REPLACE_ME approval-REPLACE_ME.json
```

Application is deliberately limited to the approved deletion of `uploads/old.tmp` in the generated four-file fixture. It revalidates the saved approval and simulation, takes a per-fixture lock, creates an exclusive per-approval transaction directory, and verifies a backup before deleting. File and synthetic HTTP checks run afterward. Verification failure triggers restoration; an interrupted process can be recovered with the second command. Recovery refuses to overwrite different content or use a corrupt backup. A used approval cannot be applied again, even after restoration.

Backups and transaction records remain under ignored fixture artifacts. Backups use the same disk, so this demonstration does not claim net disk-space savings. Locks coordinate these commands only. Local record tampering, uncooperative writers, power-loss durability, and general production-server recovery are outside the current demo guarantees. Keep the backup and transaction record if recovery reports an error.

## Compare candidate plans

```bash
python3 scripts/test_compare_cleanup.py
python3 scripts/compare_cleanup.py
```

The comparison command creates a fresh baseline and requests one to three structured plans from Nebius (uses API credits). Policy-denied plans never reach a container. Duplicate action sets are reported as duplicates and simulated once. Each distinct eligible candidate gets a separate identical fixture copy and a restricted container simulation, with evidence tied to that copy. Passing candidates are ordered by removed file bytes, then fewer actions, then original input order for ties. This is a deterministic outcome ranking, not a safety score or net disk-space measurement.

The current one-file cleanup task has only one valid complete deletion plan; returning one candidate is expected. Do not interpret duplicate proposals as diverse strategies. Broader meaningful alternatives require additional supported tasks. If no candidate passes, no recommendation is made. Otherwise the command prints the exact review command for the recommended candidate copy; it never approves or applies it automatically. Reports remain under ignored artifacts. Unit tests mock simulation; live container verification is a separate step.
