# FutureProof AI

## Pitch
Test AI-proposed server changes in disposable environments before approving them.

## Track
Coding and Agentic Engineering.

## What it does
FutureProof AI is a Linux developer-tool prototype for controlled cleanup, upload-limit configuration, and service-restart scenarios. It validates structured AI plans, simulates permitted changes in disposable rootless Podman containers, verifies application behavior and protected files, and records evidence. Human approval binds to the tested plan and fixture state. Controlled application and recovery are supported; consumed approvals cannot be reused.

The configuration dashboard demonstrates the complete workflow: create a fixture, generate candidates, simulate and compare, review, approve, apply, verify, and recover. Cleanup and restart AI workflows use the CLI.

## How it works
Python standard-library services and an HTML/JavaScript dashboard coordinate JSON plans and evidence. NVIDIA Nemotron (`nvidia/nemotron-3-super-120b-a12b`) is called at runtime through Nebius Token Factory. The model proposes structured actions; deterministic policy and behavioral checks determine whether they meet the demo requirements. Hosted inference allows development on a laptop without local model weights.

## Challenges and learning
We addressed unsafe model output, changed files after simulation, approval replay, incomplete success reports, container-runtime differences, and recovery after interrupted changes. HTTP behavior, authentication, protected-file hashes, and restoration checks provide evidence beyond an exit code.

## Results and scope
The developer reported 150 automated tests passing in Ubuntu on October 14. A frozen developer-authored configuration planning suite passed 15/15 cases, including five forbidden requests. Its ten supported plans passed container replay. A fresh clone passed a real configuration smoke test on the existing WSL machine. These are scoped results, not independent evaluation or general safety guarantees.

The prototype operates only on synthetic fixtures. Separate-machine reproduction, broader evaluation, and durable job tracking remain future work. Jobs currently run in memory. The dashboard is localhost-only.

## Submission links
- Repository: https://github.com/Sajjad371/futureproof-ai
- Setup: https://github.com/Sajjad371/futureproof-ai/blob/main/docs/judge-setup.md
- Video: add the public YouTube recording before submission.
- Test build: provide a downloadable commit archive with the setup link. Verify access. Localhost is not a public demo URL.

## Platform feedback draft
Nebius Token Factory provided hosted NVIDIA inference through an OpenAI-compatible endpoint. This let us separate model planning from local validation and execution. Review this feedback against your own experience before submitting.
