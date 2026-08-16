from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from skill_package import CANONICAL_HASH_ALGORITHM, VALIDATOR_VERSION, package_sha256, validate_package

from package_integrity import LEGACY_HASH_ALGORITHM

CS_ROOT = Path(__file__).resolve().parents[2]


class MigrationRejected(RuntimeError):
    pass


def write_json_atomic(path: Path, payload: dict) -> None:
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


def migrate(library: Path, approved_by: str) -> dict:
    library = library.resolve(strict=True)
    packages = sorted(path for path in library.iterdir() if path.is_dir())
    if not packages:
        raise MigrationRejected("No published Skill packages found")

    transaction_parent = library.parent / ".codex-cs-private" / "receipt-v2-migrations"
    transaction_parent.mkdir(parents=True, exist_ok=True)
    transaction_root = transaction_parent / uuid.uuid4().hex
    candidates = transaction_root / "candidates"
    backups = transaction_root / "backups"
    archive = transaction_root / "legacy-receipts"
    candidates.mkdir(parents=True)
    backups.mkdir()
    archive.mkdir()
    prepared: list[tuple[Path, Path]] = []
    replaced: list[tuple[Path, Path]] = []
    try:
        for source in packages:
            receipt_path = source / "intake-receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            if receipt.get("schema_version") != 1:
                raise MigrationRejected(f"Expected a v1 receipt: {source.name}")
            legacy_hash = package_sha256(source, algorithm=LEGACY_HASH_ALGORITHM)
            if receipt.get("package_sha256") != legacy_hash:
                raise MigrationRejected(f"Legacy receipt does not match raw package bytes: {source.name}")

            candidate = candidates / source.name
            shutil.copytree(source, candidate)
            shutil.copy2(receipt_path, archive / f"{source.name}.intake-receipt.v1.json")
            new_receipt = {
                "schema_version": 2,
                "hash_algorithm": CANONICAL_HASH_ALGORITHM,
                "skill_id": receipt["skill_id"],
                "status": "published",
                "validator_version": VALIDATOR_VERSION,
                "approved_by": approved_by,
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "sources": receipt["sources"],
                "package_sha256": package_sha256(candidate),
            }
            write_json_atomic(candidate / "intake-receipt.json", new_receipt)
            issues = validate_package(candidate, require_receipt=True)
            if issues:
                raise MigrationRejected(
                    f"Candidate validation failed for {source.name}: "
                    + json.dumps([issue.to_dict() for issue in issues], ensure_ascii=False)
                )
            prepared.append((source, candidate))

        for destination, candidate in prepared:
            backup = backups / destination.name
            destination.replace(backup)
            candidate.replace(destination)
            replaced.append((destination, backup))

        registry_script = CS_ROOT / "skill-registry" / "scripts" / "build_registry.py"
        completed = subprocess.run(
            [sys.executable, str(registry_script), "--library", str(library), "--rebuild"],
            text=True, capture_output=True, encoding="utf-8", check=False,
        )
        if completed.returncode != 0:
            raise MigrationRejected(f"Registry rebuild failed: {completed.stdout} {completed.stderr}")

        archive_root = transaction_parent / f"completed-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        archive.replace(archive_root)
        return {
            "status": "migrated",
            "packages": [path.name for path in packages],
            "legacy_receipt_archive": str(archive_root),
        }
    except BaseException:
        for destination, backup in reversed(replaced):
            failed = transaction_root / f"failed-{destination.name}"
            if destination.exists():
                destination.replace(failed)
            backup.replace(destination)
            shutil.rmtree(failed, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(transaction_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomically migrate published Codex_CS receipts to canonical hash v2.")
    parser.add_argument("--library-root", required=True, type=Path)
    parser.add_argument("--approved-by", required=True, choices=["user"])
    args = parser.parse_args()
    try:
        result = migrate(args.library_root, args.approved_by)
    except (MigrationRejected, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
