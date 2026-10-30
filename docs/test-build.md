# Verified source test build

Revision: `c022049e452313fc745071513778994d68f6b078`.

[Download source test build (ZIP)](https://codeload.github.com/Sajjad371/futureproof-ai/zip/c022049e452313fc745071513778994d68f6b078)

[Setup instructions at the tested revision](https://github.com/Sajjad371/futureproof-ai/blob/c022049e452313fc745071513778994d68f6b078/docs/judge-setup.md)

This is runnable Python source, not a prebuilt desktop executable or hosted service. Extract the ZIP, open its directory in Ubuntu, and follow the setup instructions. Fixed container checks require no API key. Live AI planning requires the judge's own Nebius credentials and credits.

Downloaded without authentication and checked on October 30: 73 ZIP entries, valid archive integrity, required README/license/setup/runtime scripts present. No .env file, Git metadata, or artifacts directory included.

Downloaded archive SHA-256: `049032f25fb34b6ec869b41afe8abe70b547b858adc2ddc838130efc9ef01b1b`.

## Independent runtime verification

[GitHub Actions run 41032583789](https://github.com/Sajjad371/futureproof-ai/actions/runs/41032583789) completed successfully on a fresh Ubuntu 24.04 hosted runner. Checkout, runtime installation, rootless preflight, repeated automated tests, real-container checks, and result upload all passed. This verifies the workflow on another machine; it does not verify hosted interactive execution or live AI requests from CI.

Local Ubuntu container timings reported by the developer:

| Scenario | First run | Second run |
|---|---:|---:|
| Cleanup baseline | 7.848 s | 9.558 s |
| Configuration simulation | 9.201 s | 8.800 s |
| Restart simulation | 11.725 s | 13.478 s |

All six passed. Timings include container preparation and cleanup, may reuse image caches, and are not AI latency or peak-memory measurements. The complete dashboard configuration approval/application/recovery rehearsal also passed locally on October 30, confirmed in the exported summary.

Public hosted interactive execution remains unimplemented. Video and Devpost submission remain pending. Do not use the localhost URL as a publicly accessible demo link.

