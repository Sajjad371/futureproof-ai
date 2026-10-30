# Release gates - October 30

This checklist records evidence, not a claim that all milestones are complete.

| Gate | Evidence or next action |
|---|---|
| Core cleanup/configuration/restart flows | Previously demonstrated locally with approval and recovery |
| Full configuration dashboard flow | October 30 rehearsal passed: config-_lvrid_y comparison, config-wpqweur_ candidate approved, applied and restored; all five application and recovery checks true in inspected export |
| Historical Ubuntu suite | 150 tests passed October 14 |
| Broader cleanup policy cases | Added second-level retention boundaries and zero/small/large file content tests; not broader AI cleanup evaluation |
| Evidence summary export | Downloaded JSON inspected October 30: 55 records, zero skipped, restored transaction and consumed approval confirmed; projected historical summaries only |
| Dashboard presentation | Responsive styles, focus states, workflow guidance added; user desktop screenshots reviewed October 30 |
| Repeatability and timing | User reported three Ubuntu suite runs passing in 21.22, 25.86 and 19.02 seconds; median 21.22 seconds. This measures suite wall time, not model latency or resource usage |
| Fresh clone on existing machine | Previously passed real configuration Podman smoke test |
| Independent machine | GitHub-hosted Ubuntu 24.04 run 41032583789 passed runtime setup, repeated tests, and real container checks |
| Hosted executable demo | October 30 temporary authenticated Cloudflare tunnel: config-dtf2ac97 comparison, config-ftswk_co approved/applied/restored; five application and five recovery checks true, approval consumed. Laptop and tunnel must remain running; not permanent hosting |
| AI evaluation | Historical developer-authored 15/15 planning, ten supported container replays; not independent benchmark |
| MIT and submission text | Published in commit 1c90779 |
| Video | User recording pending after final rehearsal |
| Final feedback and links | Review submission.md, add video and test-build URL, test signed-out access |
| Devpost submission | Pending; require actual submission confirmation |

Four fixed-plan cleanup container variations passed locally: standard, retention-edge, empty-expired and large-expired. These are container regression cases, not broader AI evaluation.

Public demo mode requires an exact HTTPS tunnel origin and a demo-only password. Keep the listener bound to loopback. Only trusted reviewers should receive credentials: authenticated users can run demo workflows and consume inference credits. This shared, temporary demonstration is not a hardened multi-user service.
