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

from skill_package import VALIDATOR_VERSION, file_sha256, load_contract, package_sha256, validate_package


SCRIPT_ROOT = Path(__file__).resolve().parent
ALLOWED_REPORT_STATES = {"ready_for_approval", "approved"}
ALLOWED_SUPPLEMENT_STATES = {"not_required", "user_approved"}


class UpgradeRejected(RuntimeError):
    """Raised when a governed upgrade precondition is not satisfied."""


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


def load_intake_report(package: Path) -> dict:
    path = package / "intake-report.json"
    if not path.is_file():
        raise UpgradeRejected("Staging package is missing intake-report.json")
    try:
        report = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpgradeRejected(f"Cannot read intake-report.json: {exc}") from exc
    if not isinstance(report, dict):
        raise UpgradeRejected("intake-report.json must contain a JSON object")
    return report


def validate_report(report: dict, skill_id: str, sources: list[dict]) -> None:
    if report.get("skill_id") != skill_id:
        raise UpgradeRejected("intake-report.json skill_id does not match the staging package")
    if report.get("status") not in ALLOWED_REPORT_STATES:
        raise UpgradeRejected("Intake report is not ready for approval")

    for field in ("blocking_questions", "contract_conflicts", "validation_issues"):
        value = report.get(field)
        if not isinstance(value, list) or value:
            raise UpgradeRejected(f"Intake report field {field} must be an empty array")

    supplement = report.get("creative_supplement")
    if not isinstance(supplement, dict) or supplement.get("status") not in ALLOWED_SUPPLEMENT_STATES:
        raise UpgradeRejected("Creative supplement must be user_approved or not_required")

    reported_sources = report.get("sources")
    if not isinstance(reported_sources, list) or not reported_sources:
        raise UpgradeRejected("Intake report must list the reviewed source files")
    reported_hashes = {
        item.get("sha256")
        for item in reported_sources
        if isinstance(item, dict) and isinstance(item.get("sha256"), str)
    }
    missing = [item["name"] for item in sources if item["sha256"] not in reported_hashes]
    if missing:
        raise UpgradeRejected(
            "Submitted source files are not covered by the intake report: " + ", ".join(missing)
        )


def build_receipt(skill_id: str, approved_by: str, sources: list[dict], package: Path) -> dict:
    return {
        "schema_version": 1,
        "skill_id": skill_id,
        "status": "published",
        "validator_version": VALIDATOR_VERSION,
        "approved_by": approved_by,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "package_sha256": package_sha256(package),
    }


def rebuild_registry(library: Path) -> subprocess.CompletedProcess[str] | None:
    codex_cs_root = SCRIPT_ROOT.parents[1]
    registry_script = codex_cs_root / "skill-registry" / "scripts" / "build_registry.py"
    production_library = (codex_cs_root / "business-skills").resolve()
    if not registry_script.is_file() or library != production_library:
        return None
    return subprocess.run(
        [sys.executable, str(registry_script), "--library", str(library)],
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def upgrade(package: Path, library: Path, source_paths: list[Path], approved_by: str) -> dict:
    package = package.resolve(strict=True)
    if not package.is_dir():
        raise UpgradeRejected(f"Staging package is not a directory: {package}")

    issues = validate_package(package)
    if issues:
        raise UpgradeRejected(
            "Staging package validation failed: "
            + json.dumps([issue.to_dict() for issue in issues], ensure_ascii=False)
        )
    contract = load_contract(package)
    skill_id = contract["skill_id"]

    library = library.resolve(strict=True)
    if not library.is_dir():
        raise UpgradeRejected(f"Skill library is not a directory: {library}")
    destination = library / skill_id
    if not destination.is_dir():
        raise UpgradeRejected(f"Published Skill does not exist and cannot be upgraded: {destination}")
    current_issues = validate_package(destination, require_receipt=True)
    if current_issues:
        raise UpgradeRejected(
            "Existing published Skill has an invalid credential: "
            + json.dumps([issue.to_dict() for issue in current_issues], ensure_ascii=False)
        )

    sources: list[dict] = []
    for source in source_paths:
        resolved = source.resolve(strict=True)
        if not resolved.is_file():
            raise UpgradeRejected(f"Source is not a file: {resolved}")
        sources.append({"name": resolved.name, "sha256": file_sha256(resolved)})
    report = load_intake_report(package)
    validate_report(report, skill_id, sources)

    transaction_id = uuid.uuid4().hex
    # Keep transaction and backup directories outside the published library.
    # The registry intentionally scans every child directory of business-skills,
    # so in-library hidden transaction folders would be treated as invalid Skills.
    transaction_parent = library.parent / ".codex-cs-private" / "upgrade-transactions"
    transaction_parent.mkdir(parents=True, exist_ok=True)
    transaction_root = transaction_parent / f"{skill_id}.upgrade-{transaction_id}"
    candidate = transaction_root / skill_id
    backup = transaction_parent / f"{skill_id}.backup-{transaction_id}"
    replaced = False
    try:
        transaction_root.mkdir()
        shutil.copytree(package, candidate)
        receipt_path = candidate / "intake-receipt.json"
        if receipt_path.exists():
            receipt_path.unlink()
        receipt = build_receipt(skill_id, approved_by, sources, candidate)
        write_json_atomic(receipt_path, receipt)
        post_issues = validate_package(candidate, require_receipt=True)
        if post_issues:
            raise UpgradeRejected(
                "Upgraded package failed validation after receipt generation: "
                + json.dumps([issue.to_dict() for issue in post_issues], ensure_ascii=False)
            )

        destination.replace(backup)
        try:
            candidate.replace(destination)
            replaced = True
        except BaseException:
            backup.replace(destination)
            raise

        registry = rebuild_registry(library)
        if registry is not None and registry.returncode != 0:
            failed_candidate = library / f".{skill_id}.failed-{transaction_id}"
            destination.replace(failed_candidate)
            backup.replace(destination)
            rebuild_registry(library)
            shutil.rmtree(failed_candidate, ignore_errors=True)
            replaced = False
            raise UpgradeRejected(
                "Registry update failed; the previous published Skill was restored. "
                f"stdout={registry.stdout!r} stderr={registry.stderr!r}"
            )

        shutil.rmtree(backup)
        return {
            "status": "upgraded",
            "skill_id": skill_id,
            "destination": str(destination),
            "previous_package_replaced": True,
            "package_sha256": receipt["package_sha256"],
        }
    finally:
        if transaction_root.exists():
            shutil.rmtree(transaction_root, ignore_errors=True)
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        elif backup.exists() and replaced:
            # Any unexpected failure after replacement restores the last valid package.
            failed_candidate = library / f".{skill_id}.failed-{transaction_id}"
            destination.replace(failed_candidate)
            backup.replace(destination)
            shutil.rmtree(failed_candidate, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade an existing approved Codex_CS video business Skill.")
    parser.add_argument("package", type=Path, help="Reviewed staging Skill package")
    parser.add_argument("--library-root", required=True, type=Path)
    parser.add_argument("--source", action="append", required=True, type=Path)
    parser.add_argument("--approved-by", required=True, choices=["user"])
    args = parser.parse_args()

    try:
        result = upgrade(args.package, args.library_root, args.source, args.approved_by)
    except (UpgradeRejected, FileNotFoundError, OSError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
