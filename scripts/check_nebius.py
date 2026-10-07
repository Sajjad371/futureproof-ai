"""Minimal connection check; uses Python's standard library and never logs keys."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"
MODEL = "nvidia/nemotron-3-super-120b-a12b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true", help="Validate locally without an API request")
    args = parser.parse_args()
    config = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print("Invalid .env format. Use one NAME=value per line.")
                return 1
            name, value = line.split("=", 1)
            config[name.strip()] = value.strip().strip("\"'")
    for name in ("NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NVIDIA_MODEL_ID"):
        if name in os.environ:
            config[name] = os.environ[name]
    key = config.get("NEBIUS_API_KEY", "")
    if not key or any(char.isspace() for char in key):
        print("Set NEBIUS_API_KEY in the local .env file. Do not paste it into chat.")
        return 1
    if config.get("NEBIUS_BASE_URL") != BASE_URL or config.get("NVIDIA_MODEL_ID") != MODEL:
        print("Endpoint or model differs from the configured project selection.")
        return 1
    if args.check_config:
        print("Configuration valid. Key not displayed. No network request made.")
        return 0
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with: FutureProof AI connection test successful."}],
        "max_tokens": 256,
    }).encode()
    request = urllib.request.Request(BASE_URL + "chat/completions", data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
    })
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
        message = result["choices"][0]["message"].get("content") or ""
        expected = "FutureProof AI connection test successful."
        passed = expected in message
        print("Connection test passed." if passed else "API responded, but the expected final answer was absent.")
        print("Model:", MODEL)
        print("Elapsed seconds:", round(time.monotonic() - start, 2))
        return 0 if passed else 1
    except urllib.error.HTTPError as error:
        print("API request failed with HTTP status", error.code)
        print("Check key, credits, model access, and endpoint. Response details withheld.")
    except (urllib.error.URLError, TimeoutError):
        print("Network request failed or timed out. No credentials displayed.")
    except (ValueError, KeyError, IndexError, TypeError):
        print("Unexpected API response format. No response body displayed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
