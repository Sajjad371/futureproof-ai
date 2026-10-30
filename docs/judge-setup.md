# Judge setup

Supported runtime: Ubuntu 24.04, native or WSL 2; Python 3.11+, Git, rootless Podman. No pip dependencies. Container downloads need internet access.

Install missing prerequisites on Ubuntu:
```bash
sudo apt update
sudo apt install -y python3 git podman
```

Clone into a new directory:
```bash
git clone https://github.com/Sajjad371/futureproof-ai.git
cd futureproof-ai
python3 scripts/check_environment.py
python3 -m unittest discover -s scripts -p "test_*.py"
python3 scripts/evaluate_policies.py
python3 scripts/dashboard.py
```

Open http://127.0.0.1:8765 on the same computer. Keep the terminal running; Ctrl+C stops it.

## No-key demo
Select configuration, click Create fixture, then Run fixed container check. Wait for passed and expand the fixture evidence. This checks a fixed 2 MiB candidate in a disposable container without AI credits or target application. Restart fixtures also have fixed checks.

## Full AI configuration flow
For a new checkout, copy `.env.example` to `.env` and privately set NEBIUS_API_KEY. Retain the supplied endpoint and NVIDIA_MODEL_ID if supported by your account. Never publish the key. Live inference uses credits. Restart the dashboard after configuring it.

1. Create a new configuration fixture.
2. Generate AI candidates and simulate; wait for completion.
3. Expand the comparison and review its recommended candidate.
4. Type the exact displayed approval phrase and record approval.
5. Open the candidate's approval record. Type `APPLY` followed by a space and its fixture name, then click Apply approved change.
6. Wait for passing application checks. Type `RECOVER` followed by a space and that same fixture name, then click Recover original configuration.
7. Confirm restored and passing recovery checks. The approval is consumed.

Use the names generated in your run. Local evidence under artifacts/ is ignored by Git. Changes affect synthetic fixtures only. Cleanup and restart CLI instructions are in the main README. Fresh-machine reproduction remains unverified; the recorded fresh-clone test used the existing WSL environment.
