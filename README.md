# FutureProof AI

Test AI-proposed Linux application changes in disposable environments before approving them.

## Status

Version 1 now supports one complete simulation flow: generate a structured cleanup plan through Nebius, validate it against a narrow read-only policy, execute it inside a disposable restricted Podman container, and verify the result. The local human-approval command has passed unit tests and a manual Ubuntu run. Controlled demo application and recovery have passed Ubuntu tests and a manual recovery run. The live comparison-to-approval-to-application-to-recovery flow passed in Ubuntu on October 11, 2026, with one valid candidate. The cleanup fixture has only one valid complete plan; distinct valid alternatives have now been demonstrated in the configuration scenario. The configuration workflow also passed live comparison, approval, application and recovery in Ubuntu on October 12. Service restart, dashboard, and held-out evaluation are not implemented yet.

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

Validation recorded on October 7, 2026: the real Nebius smoke test passed; the developer reported the baseline container check passing on Ubuntu 24.04 / WSL 2 with rootless Podman 4.9.3. On October 11, 2026, the developer reported successful live Nebius planning, all 10 simulation tests, and a real Podman cleanup simulation with the strengthened report checks. Latest local test discovery ran 86 tests: 85 passed and one Windows symlink test was skipped; the developer previously ran all nine policy tests successfully in Ubuntu. Approval and comparison tests also passed in Ubuntu. The live recommended candidate was approved, applied, and restored, with file hashes and HTTP checks passing. Simulation/comparison unit tests mock Podman responses; the real container runs are separate. This is a controlled demo, not a complete security evaluation.

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

## Configuration scenario foundation (October 12)

```bash
python3 scripts/test_config_fixture.py
python3 scripts/config_fixture.py
```

The new fixture starts with a 1 MiB upload limit and requires a 2 MiB upload, with an 8 MiB policy ceiling. Only `SET_CONFIG` on `app.json` / `max_upload_bytes` is allowed. The document reference, authentication requirement, bind address, and protected document must be preserved. Both 2 MiB and 4 MiB settings pass configuration outcome checks; an insufficient but policy-bounded 1 MiB value fails the task outcome. Eight local tests cover these distinctions, protected settings, invalid actions/values, JSON syntax, and content drift.

The fixture and read-only policy tests passed in Ubuntu. Real HTTP upload verification and a restricted container test runner are now implemented; local and Ubuntu HTTP tests pass, and the 2 MiB and 4 MiB candidates passed real restricted Podman runs in Ubuntu. Nebius configuration planning and candidate comparison are implemented and locally tested; the live run passed in Ubuntu with distinct 2 MiB and 4 MiB AI candidates. Configuration approval, application, and recovery passed Ubuntu tests and a live manual run on October 12, 2026. The approved 2 MiB setting was applied, checked over HTTP, then restored to the original 1 MiB configuration with all checks passing. Do not use the cleanup commands on configuration fixtures. All original blueprint requirements remain subject to the acceptance checklist; a working cleanup demonstration does not mean the complete milestone or release criteria are satisfied.

### Configuration HTTP/container checks

```bash
python3 scripts/test_config_http.py
python3 scripts/check_config_container.py config-REPLACE_ME
python3 scripts/check_config_container.py config-REPLACE_ME --limit-mib 4
```

Use a fixture name printed by `config_fixture.py`. The default tests a fixed 2 MiB candidate; the optional command tests 4 MiB. These are developer-defined test candidates, not model-generated proposals. Each run copies only the fixture's two files and manifest into an isolated build context, checks rootless Podman, and runs with no host mounts, no external network, a read-only root, dropped capabilities, and bounded writable storage/resources. It does not change the original configuration.

The synthetic app must reject the 2 MiB upload before modification, accept it afterward, and return identical uploaded bytes. Oversized and unauthenticated uploads must be rejected without overwriting accepted data. Health, protected document hashes, and protected settings are also checked. The test credential is a public synthetic constant used only by this loopback demo. This app is not a production authentication implementation. Evidence stays in ignored artifacts; temporary container/image removal is attempted on success and failure.

### Nebius configuration comparison

```bash
python3 scripts/test_compare_config.py
python3 scripts/compare_config.py config-REPLACE_ME
```

The live command uses API credits to request one to three structured configuration plans. It validates each plan, rejects protected-setting changes, deduplicates identical limit values, and tests eligible values on independent copies of the same baseline. It accepts no shell commands. Only candidates with matching baseline/limit evidence and all required HTTP checks can be recommended. Ranking chooses the smallest sufficient limit, with input order as a deterministic tie-breaker. This scenario-specific ranking does not yet implement the blueprint's full weighted score.

The comparison saves validated plans, fingerprints, per-candidate evidence references, durations, and a recommendation under ignored artifacts. No approval or target application occurs. Seven orchestration tests simulate runner responses; the five HTTP tests separately exercise the actual loopback application. Live AI candidates may differ in count and values; no fixed fallback replaces a failed model call.

### Review configuration approval

```bash
python3 scripts/test_approve_config.py
python3 scripts/approve_config.py config-BASELINE config-comparison-REPORT.json
```

Use the baseline and comparison filename from the live comparison. The recommended passing candidate is selected by default; `--candidate 2` can explicitly select another passing candidate. Review the exact setting/value and type the displayed phrase only if you agree. The command verifies the comparison, candidate plan, simulation fingerprints, original baseline, candidate file contents and metadata, then checks again after confirmation. It records the local username, exact candidate fixture scope, and a 24-hour expiry. Records remain trusted-local artifacts, not authenticated multi-user approvals. No configuration is changed. The configuration executor enforces expiry before application and uses a per-approval transaction directory to prevent reuse, including after restoration.

### Apply and recover an approved configuration

```bash
python3 scripts/test_apply_config.py
python3 scripts/apply_config.py apply config-CANDIDATE config-approval-APPROVAL.json
python3 scripts/apply_config.py recover config-CANDIDATE config-approval-APPROVAL.json
```

Use the candidate fixture and approval filename printed by the approval command. Application rechecks expiry, scope, comparison, simulation, plan, file hashes and metadata while holding a cooperating-process lock. A verified original `app.json` backup is required before atomic replacement. Real loopback HTTP checks read the applied configuration; temporary upload data is isolated and removed. On postflight failure, the executor attempts restoration and verifies original bytes, metadata, upload behavior, authentication, health and document preservation. Explicit recovery can restore an interrupted or successful attempt and does not require an unexpired approval. Recovery refuses to overwrite unexpected edits or use a corrupt backup.

Only the named synthetic candidate fixture changes. The comparison baseline remains intact. Backups and transaction records are retained under ignored artifacts. As with cleanup, local records are trusted, locks do not stop unrelated writers, and power-loss durability is not guaranteed. A restored approval remains consumed. Nine tests cover real application/recovery, expiry, wrong scope, backup failure, failed postflight, interruption, replay and recovery conflicts.

## Milestone checkpoint — October 12, 2026

| Original target dates | Current demonstrated result | Remaining work |
|---|---|---|
| October 6–10 | Connected cleanup demo, live model call, policy and container verification | Full V1 checklist coverage is not certified; see acceptance checklist |
| October 11–15 | Candidate evaluation, exact approval, controlled application and restoration demonstrated; two distinct valid AI configurations compared | Blueprint weighted ranking, fuller audit records, uniform approval/expiry semantics and broader failure coverage |
| October 16–20 | Configuration scenario demonstrated end to end | Service restart, common API/dashboard, held-out evaluation, further integration and hardening |
| October 21–25 | Not started as a release milestone | Clean-install reproduction, deployed build, full release/evaluation runs |
| October 26–29 | Repository and ongoing documentation available | Video, final write-up, rule/link checks and submission |

Two of three planned task families have a working controlled command-line demonstration. This is not a percentage of total project completion: interface, evaluation, release and submission work remain substantial. The dates are the original schedule, not claims that every acceptance criterion for a date range is finished.
