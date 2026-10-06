# FutureProof AI requirements and acceptance checklist

Planning baseline: 6 October 2026. Submission date: 30 October 2026.

This checklist translates the supplied 27-section blueprint into verifiable work. All implementation items start unchecked because no source code or running system has been inspected. A checkbox means its acceptance test passed and evidence was recorded, not merely that code exists. The target is a controlled Linux demonstration covering cleanup, configuration changes, and service restarts; it is not arbitrary production administration.

## How to use this checklist

- Record each requirement's status as Not started, In progress, Blocked, or Verified.
- For Verified items, record the commit, test command or manual procedure, result, and evidence location. Never put credentials in evidence.
- Test while building. Every milestone must exercise the connected system available at that point.
- Keep one codebase. Each version improves the preceding version.
- Use explicit scope decisions for unfinished requirements. Do not silently mark deferred work complete.
- Core means required for a trustworthy end-to-end demo. Coverage means required to fulfill the full blueprint. Submission means required preparation or rule verification. Stretch means optional.

## Five-day milestones

| Stage | Dates | Connected deliverable | Exit gate |
|---|---|---|---|
| Version 1 | Oct 6–10 | One cleanup request, real model call, validated plan, policy checks, isolated execution, independent checks, simple results display | A permitted operation changes only its temporary fixture; a deliberately broken fixture fails verification; the target remains unchanged |
| Version 2 | Oct 11–15 | Up to three alternatives, identical baselines, comparison, approval, target execution, backup and restore | Only an eligible, exactly approved plan applies; stale state and replay are rejected; recovery is demonstrated |
| Version 3 | Oct 16–20 | Configuration and restart fixtures, stronger failure handling, complete dashboard and evidence, evaluation harness | All three families execute through the same workflow; security and failure cases pass; held-out evaluation is runnable |
| Release testing | Oct 21–25 | Fresh installation, deployed test build, repeated complete workflows, measured evaluation | A second person or clean environment reproduces the documented demo; no unresolved defect permits unauthorized target mutation |
| Submission buffer | Oct 26–29 | Final fixes, public repository, video, write-up, feedback, submission | Required links and artifacts verified; submission completed before the deadline |

Dates are targets, not guarantees. Reserve part of every stage for testing and fixes. Do not add a new task family while the core execution or approval boundary is failing.

## Requirements and acceptance tests

### Foundation and model integration

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | F01 | Core / V1 | Confirm execution environment | Record OS, RAM, runtime versions, and virtualization if local; successfully start and remove a restricted Linux test container. Use a remote Linux environment if local compatibility is insufficient. |
| [ ] | F02 | Core / V1 | Repository structure and configuration | Backend, frontend, fixtures, tests, scripts, and docs exist; placeholder environment file works; secrets and generated private artifacts are excluded from version control. |
| [ ] | F03 | Core / V1 | Real NVIDIA model on Nebius | A runtime request succeeds; record exact model ID, endpoint type, latency, and available token usage without exposing the key. |
| [ ] | F04 | Core / V1 | Structured action contract | Validate tool type, parameters, bounded step count, paths, preconditions, and checks; reject malformed JSON and unknown fields/actions as defined by the schema. No arbitrary generated shell execution. |
| [ ] | F05 | Core / V1–2 | Grounded alternative plans | Requests and inventories affect proposed actions; at most three candidates are accepted; duplicates are identified; bounded retries end with a visible failure if output stays invalid. |
| [ ] | F06 | Core / V1 | Minimal, untrusted model inputs | Send only required redacted inventory. Instructions embedded in filenames, logs, and file contents cannot override policy or authorize execution in adversarial tests. |

### Policy, fixtures, and isolated execution

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | S01 | Core / V1 | Server-enforced action policy | Model output cannot change policy, approve actions, or mark verification passed. Forbidden operations are rejected before runner invocation. |
| [ ] | S02 | Core / V1–3 | Safe filesystem operations | Test traversal, outside-root absolute paths, symlink components, hardlinks, unsupported file types, Unicode/path ambiguity, and changed inventory. Supported operations stay inside their workspace; ambiguous or unsupported cases fail closed. |
| [ ] | S03 | Core / V1 | Restricted runner | Inspect actual runtime configuration: non-root, dropped capabilities, no-new-privileges, bounded writable storage, resource limits, and restricted network. No host secrets, Docker socket, or broad host mounts are accessible. |
| [ ] | S04 | Core / V2 | Independent identical clones | Candidate IDs and sandbox IDs are distinct; each clone has the same baseline state hash before execution; changes in one do not appear in another or in the target. |
| [ ] | S05 | Core / V1–3 | Bounded execution and cleanup | Timeout, process failure, and memory-limit failure produce explicit failed results. Temporary environments are removed after success or failure; startup cleanup handles leftovers from an interrupted worker. |
| [ ] | S06 | Core / V1 | Cleanup fixture | Include eligible old files, protected active data, and a dependency that an aggressive change would damage. Check actual bytes reclaimed and application behavior. A forbidden candidate is blocked, not executed for dramatic effect. |
| [ ] | S07 | Coverage / V3 | Configuration fixture | A supported setting changes successfully; invalid syntax and a behavior-breaking value fail independent checks; protected settings remain unchanged. |
| [ ] | S08 | Coverage / V3 | Service restart fixture | Only the named demo service can restart. Verify readiness and a functional request afterward; startup failure or timeout disqualifies the candidate. |

### Verification, selection, and target execution

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | V01 | Core / V1–3 | Independent checks | Verifiers are controlled by the application, not the model. Test meaningful read/upload/download behavior as applicable, protected content hashes, and the requested task outcome. Intentionally damaged fixtures fail. |
| [ ] | V02 | Core / V2 | Hard gates before scoring | Policy, health, preservation, task completion, and required recovery artifacts must all pass. A candidate with any failed gate is ineligible even if its score would otherwise be high. |
| [ ] | V03 | Core / V2 | Reproducible ranking | Record normalized measurements and calculate the blueprint weights: completeness 0.40, reversibility 0.25, minimal change 0.20, runtime efficiency 0.15. Test calculation and deterministic tie handling. |
| [ ] | V04 | Core / V2 | No passing candidate | When all candidates fail, show reasons and disable application. Never fall back to the least-bad failed plan. |
| [ ] | A01 | Core / V2 | Exact approval | Approval contains approver, candidate, plan hash, baseline hash, scope, expiry, and consumption state. Wrong, missing, expired, or already consumed approval cannot mutate the target. |
| [ ] | A02 | Core / V2–3 | Drift and concurrency control | Modify the target after simulation: apply is rejected and resimulation required. Serialize controlled target mutations during preflight/apply to close the check-to-use window within the demo's supported scope. |
| [ ] | A03 | Core / V2 | Verified backup | A mutating operation requires a valid recovery artifact and sufficient space. Missing/corrupt backup blocks apply. Backup placement must not falsely satisfy a disk-space goal. |
| [ ] | A04 | Core / V2–3 | Apply, postflight, recovery | Execute only the approved plan; rerun independent checks. Inject a postflight failure, perform bounded restoration, verify restoration, and distinguish restored, restore failed, and unknown outcomes. |
| [ ] | A05 | Core / V2–3 | Durable workflow and duplicate protection | Task states survive backend restart. Repeated simulate/apply requests do not duplicate unsafe work. Interrupted mutation becomes an explicit recoverable/attention-required state, never an assumed success. |

### API, interface, and evidence

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | U01 | Core / V1–3 | Task API | Implement create task, get status, simulate, approve, apply, evidence, and health endpoints from the blueprint. Test valid transitions, invalid requests, missing tasks, and simulation idempotency keys. |
| [ ] | U02 | Core / V1–3 | Complete dashboard | User can submit a supported request, follow progress, compare plans and observed checks, inspect exact changes, approve, see postflight status, and export evidence. Failure and empty states are understandable. |
| [ ] | U03 | Core / V2–3 | Evidence and audit records | Every applied execution has plan/baseline/pre/post hashes, timestamps, policy version, action traces, independent check results, model metadata, and approval reference. No raw secrets appear. |
| [ ] | U04 | Core / V3 | Honest boundaries | Interface separates blocked, tested-failed, tested-passed, approved, applied, and recovery outcomes. It states fixture assumptions and never labels sandbox success as universal proof of safety. |
| [ ] | U05 | Core / release | Hosted-demo controls | Visitors use controlled fixtures; separate sessions cannot view or mutate one another's jobs. Authorization gates target operations; request/concurrency limits prevent unbounded execution. |
| [ ] | U06 | Core / V3 | Outages and resource budgets | Model/API failure produces a clear error with no target mutation. Record execution duration and usage; bound retry count, candidate count, log size, retained artifacts, and queued jobs. |

### Evaluation and reproducibility

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | E01 | Coverage / prepare V1, run V3–release | Held-out suite | At least 15 tasks across all three families, including at least five intentionally unsafe variants. Separate development cases from held-out cases and document any later reuse for debugging. |
| [ ] | E02 | Coverage / release | Comparison approaches | Evaluate direct model-to-tool selection using the same allowlist/approval controls, a static-rule planner, and FutureProof simulation on equivalent disposable targets. Keep unsafe outcomes off real systems. |
| [ ] | E03 | Coverage / release | Measured metrics | Report successes/attempts, unsafe-action prevention, false blocks, latency, model usage/cost where available, and restoration success. Preserve failures and raw results; label unavailable measurements. |
| [ ] | E04 | Coverage / release | Blueprint targets | Assess at least 80% success on 15 held-out tasks, zero target safety violations in the scripted suite, evidence for every applied action, and the aspirational under-120-second scenario latency. Record actual results even when targets are missed. |
| [ ] | E05 | Core / throughout | Regression checks | Run relevant policy, verification, approval, and end-to-end checks after changes. Continuous integration runs deterministic tests; real API tests require controlled credentials and are identified separately. |
| [ ] | E06 | Core / release | Clean installation | With pinned dependencies and the documented setup, reproduce the demo from a clean environment. No hidden local files or hardcoded outcomes are needed. |

### Documentation and submission

| Done | ID | Priority / stage | Requirement | Acceptance test |
|---|---|---|---|---|
| [ ] | D01 | Submission / start early, finish buffer | Architecture and limitations | Document trust boundaries, supported task families, threat model, fixture assumptions, policy, recovery limits, and evaluation method. Diagram matches the implemented system. |
| [ ] | D02 | Submission / buffer | Public source and license | Public repository includes a suitable open-source license, setup/run instructions, environment placeholders, fixtures, screenshots, and reproducible evaluation commands. Scan for exposed credentials before publishing. |
| [ ] | D03 | Submission / release–buffer | Accessible working build | Test the submitted demo/test-build URL and judge instructions from a fresh session; plan availability through the official judging period. Verify current rules before submission. |
| [ ] | D04 | Submission / buffer | Video | Prepare a public YouTube demonstration under three minutes showing actual behavior, audience/problem, NVIDIA/Nebius use, candidate evidence, approval, and verified application. |
| [ ] | D05 | Submission / buffer | Description and feedback | Explain what was built and why, identify model and Nebius product, provide specific platform feedback, and disclose pre-existing work if applicable. |
| [ ] | D06 | Submission / buffer | Final rules and track check | Recheck official deadline/timezone, eligibility, track fit, submission fields, repository access, video visibility, and all links. Best Apps and Agents is the current working track choice, subject to final scope and rules. |

## Explicit additional engineering work

The blueprint already mentions several of these concerns, but implementation needs explicit acceptance tests: visitor/job separation (U05), storage and request budgets (U06), interrupted-job recovery (A05/S05), meaningful application checks (V01), and reproducible installations (E06). These are supporting requirements, not new product features.

## Optional features that must not displace the core

- [ ] A second presentation/demo scenario beyond the required fixture coverage.
- [ ] Richer charts after the core comparison is readable.
- [ ] Additional task types beyond the three original families.

Windows target execution, unrestricted shell, arbitrary production servers, multi-host control, persistent assistant memory, package installation, and universal safety guarantees are outside this release. Some are explicitly outside the original MVP as well.

## Milestone review record

Copy this block at each checkpoint:

- Date / version:
- Commit and environment:
- Requirement IDs verified:
- Tests run and evidence locations:
- Failed tests and unresolved risks:
- Actual latency and resource usage:
- Scope deferred, reason, and effect on the blueprint:
- Next milestone decision:

## Immediate first-day work

1. Confirm RAM, Windows version, virtualization availability, and local versus remote Linux execution.
2. Locate existing code, if any; inspect it before selecting or replacing its structure.
3. Create the repository skeleton and protected configuration.
4. Make one real NVIDIA model call through Nebius without exposing credentials.
5. Start a minimal demo fixture, record baseline state, run its health checks, and remove its temporary environment.

## Reference

Project source: FutureProof_AI_Complete_Build_Blueprint.docx supplied by the user, sections 1–27.

Official hackathon rules to recheck at submission: https://nebiusglobalaihackathon.devpost.com/rules
