"""Create a new synthetic fixture without overwriting existing files."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    fixtures = ROOT / "artifacts" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix="cleanup-", dir=fixtures))
    uploads = fixture / "uploads"
    uploads.mkdir()
    now = int(time.time())
    samples = [
        ("current.json", json.dumps({"status": "ready", "document": "customer-demo.txt"}).encode(), 0, True),
        ("customer-demo.txt", b"Synthetic customer document. Must remain readable.\n", 60, True),
        ("old.tmp", b"Disposable demo data.\n" * 4096, 45, False),
        ("recent.tmp", b"Recent temporary upload. Preserve under 30-day retention.\n", 1, False),
    ]
    inventory = []
    for name, content, age_days, protected in samples:
        path = uploads / name
        path.write_bytes(content)
        modified = now - age_days * 86400
        os.utime(path, (modified, modified))
        inventory.append({"path": "uploads/" + name, "size_bytes": len(content),
                          "modified_at": modified, "protected": protected,
                          "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"fixture_version": 1, "created_at": now, "retention_days": 30,
                "goal": "Remove temporary files older than 30 days while preserving active documents.",
                "files": inventory}
    (fixture / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    config = json.loads((uploads / "current.json").read_text(encoding="utf-8"))
    assert config["status"] == "ready"
    assert (uploads / config["document"]).read_bytes() == samples[1][1]
    for entry in inventory:
        assert hashlib.sha256((fixture / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]
    print("Demo fixture created:", fixture)
    print("PASS: all four files match the baseline manifest.")
    print("PASS: application configuration points to a readable protected document.")
    print("Eligible later: uploads/old.tmp (45 days old).")
    print("Preserve: current.json, customer-demo.txt, recent.tmp.")
    print("No cleanup performed. Container execution and HTTP checks are the next step.")
    return fixture


if __name__ == "__main__":
    main()
