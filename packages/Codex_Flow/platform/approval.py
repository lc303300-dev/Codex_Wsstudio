from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import registry


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def stable_hash(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_review_card(package: Path) -> dict:
    issues = registry.skill_package.validate_package(package)
    if issues:
        raise ValueError(f"package has blocking issues: {', '.join(issues)}")
    frontmatter, _ = registry.skill_package.parse_frontmatter(package / "SKILL.md")
    meta = registry.skill_package.parse_yaml_text(package / "meta.yaml")
    return {
        "skill_id": meta["name"],
        "version": meta["version"],
        "description": frontmatter["description"],
        "primary_output": meta["primary-output"],
        "intermediate_outputs": meta.get("intermediate-outputs", []),
        "workflow_profile": meta["workflow-profile"],
        "interaction_profile": meta["interaction-profile"],
        "capabilities": meta.get("capabilities", []),
        "paid_points": extract_paid_points(package),
        "package_hash": registry.skill_package.package_sha256(package),
    }


def extract_paid_points(package: Path) -> list[str]:
    workflow_path = package / "workflow.yaml"
    if not workflow_path.is_file():
        return []
    workflow = registry.skill_package.parse_yaml_text(workflow_path)
    points = []
    for stage in workflow.get("stages", []) or []:
        if isinstance(stage, dict) and stage.get("gate") in {"paid-execution", "batch-approval"}:
            points.append(str(stage.get("id")))
    return points


def create_review(package: Path, reviews_root: Path, source_hash: str) -> dict:
    card = build_review_card(package)
    record = {
        "schema": "codex-flow-review/v1",
        "review_id": f"review_{uuid.uuid4().hex}",
        "skill_id": card["skill_id"],
        "version": card["version"],
        "source_hash": source_hash,
        "package_hash": card["package_hash"],
        "review_card_hash": stable_hash(card),
        "review_card": card,
        "created_at": utc_now(),
    }
    write_json_atomic(reviews_root / f"{record['review_id']}.json", record)
    return record


def approve_review(review: dict, approvals_root: Path) -> dict:
    record = {
        "schema": "codex-flow-approval/v1",
        "approval_id": f"approval_{uuid.uuid4().hex}",
        "review_id": review["review_id"],
        "skill_id": review["skill_id"],
        "version": review["version"],
        "source_hash": review["source_hash"],
        "package_hash": review["package_hash"],
        "review_card_hash": review["review_card_hash"],
        "approved_at": utc_now(),
        "consumed": False,
    }
    write_json_atomic(approvals_root / f"{record['approval_id']}.json", record)
    return record


def consume_approval(approval_path: Path, package: Path, review: dict) -> dict:
    approval = read_json(approval_path)
    if approval.get("consumed"):
        raise ValueError("approval has already been consumed")
    current_card = build_review_card(package)
    current_card_hash = stable_hash(current_card)
    current_package_hash = registry.skill_package.package_sha256(package)
    if approval.get("review_id") != review.get("review_id"):
        raise ValueError("approval does not match review")
    if approval.get("package_hash") != current_package_hash:
        raise ValueError("approval package hash is stale")
    if approval.get("review_card_hash") != current_card_hash:
        raise ValueError("approval review card hash is stale")
    approval["consumed"] = True
    approval["consumed_at"] = utc_now()
    write_json_atomic(approval_path, approval)
    return approval


def publish(package: Path, library_root: Path, registry_output: Path, release_root: Path, review_path: Path, approval_path: Path) -> dict:
    review = read_json(review_path)
    package = package.resolve(strict=True)
    target = library_root / package.name
    if target.exists():
        raise ValueError(f"target already exists: {target}")
    staging_root = library_root / f".staging-{package.name}-{uuid.uuid4().hex}"
    staging = staging_root / package.name
    previous_registry = registry_output.read_bytes() if registry_output.exists() else None
    previous_approval = approval_path.read_bytes() if approval_path.exists() else None
    try:
        library_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(package, staging)
        consumed = consume_approval(approval_path, staging, review)
        target_tmp = library_root / f".install-{package.name}-{uuid.uuid4().hex}"
        staging.replace(target_tmp)
        shutil.rmtree(staging_root, ignore_errors=True)
        target_tmp.replace(target)
        build_result = registry.build(library_root, registry_output)
        if build_result["rejected"]:
            raise ValueError(f"registry rejected published packages: {build_result['rejected']}")
        release = {
            "schema": "codex-flow-release/v1",
            "release_id": f"release_{uuid.uuid4().hex}",
            "skill_id": review["skill_id"],
            "version": review["version"],
            "package_hash": consumed["package_hash"],
            "review_id": review["review_id"],
            "approval_id": consumed["approval_id"],
            "registry": registry_output.resolve().as_posix(),
            "released_at": utc_now(),
        }
        write_json_atomic(release_root / f"{release['release_id']}.json", release)
        return release
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if previous_registry is None:
            registry_output.unlink(missing_ok=True)
        else:
            registry_output.parent.mkdir(parents=True, exist_ok=True)
            registry_output.write_bytes(previous_registry)
        if previous_approval is not None:
            approval_path.write_bytes(previous_approval)
        raise
