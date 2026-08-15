from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from skill_package import VALIDATOR_VERSION, file_sha256, load_contract, package_sha256, validate_package

SCRIPT_ROOT = Path(__file__).resolve().parent


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish an approved Codex_CS video business Skill.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--library-root", required=True, type=Path)
    parser.add_argument("--source", action="append", required=True, type=Path)
    parser.add_argument("--approved-by", required=True, choices=["user"])
    args = parser.parse_args()

    package = args.package.resolve(strict=True)
    issues = validate_package(package)
    if issues:
        print(json.dumps({"status": "invalid", "issues": [issue.to_dict() for issue in issues]}, ensure_ascii=False, indent=2))
        return 1

    contract = load_contract(package)
    library = args.library_root.resolve()
    library.mkdir(parents=True, exist_ok=True)
    destination = library / contract["skill_id"]
    if destination.exists():
        raise SystemExit(f"Refusing to overwrite an existing published Skill: {destination}")

    sources = []
    for source in args.source:
        resolved = source.resolve(strict=True)
        if not resolved.is_file():
            raise SystemExit(f"Source is not a file: {resolved}")
        sources.append({"name": resolved.name, "sha256": file_sha256(resolved)})

    with tempfile.TemporaryDirectory(prefix="codex-cs-publish-", dir=library) as raw:
        staging = Path(raw) / contract["skill_id"]
        shutil.copytree(package, staging)
        receipt_path = staging / "intake-receipt.json"
        if receipt_path.exists():
            receipt_path.unlink()
        receipt = {
            "schema_version": 1,
            "skill_id": contract["skill_id"],
            "status": "published",
            "validator_version": VALIDATOR_VERSION,
            "approved_by": args.approved_by,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
            "package_sha256": package_sha256(staging),
        }
        write_json_atomic(receipt_path, receipt)
        post_issues = validate_package(staging, require_receipt=True)
        if post_issues:
            print(json.dumps({"status": "invalid_after_receipt", "issues": [issue.to_dict() for issue in post_issues]}, ensure_ascii=False, indent=2))
            return 1
        staging.replace(destination)

    codex_cs_root = SCRIPT_ROOT.parents[1]
    registry_script = codex_cs_root / "skill-registry" / "scripts" / "build_registry.py"
    production_library = (codex_cs_root / "business-skills").resolve()
    if registry_script.is_file() and library == production_library:
        completed = subprocess.run(
            [sys.executable, str(registry_script), "--library", str(library)],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            shutil.rmtree(destination)
            subprocess.run(
                [sys.executable, str(registry_script), "--library", str(library)],
                text=True,
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            print(json.dumps({
                "status": "registry_update_failed",
                "skill_id": contract["skill_id"],
                "registry_stdout": completed.stdout,
                "registry_stderr": completed.stderr,
            }, ensure_ascii=False, indent=2))
            return 1

    print(json.dumps({
        "status": "published",
        "skill_id": contract["skill_id"],
        "destination": str(destination),
        "package_sha256": receipt["package_sha256"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
