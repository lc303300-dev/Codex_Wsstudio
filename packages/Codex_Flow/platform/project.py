from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


def stable_hash(data: object) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_project(projects_root: Path, skill: dict, settings: dict, project_id: str | None = None) -> dict:
    project = {
        "schema": "codex-flow-project/v1",
        "project_id": project_id or f"flow_{uuid.uuid4().hex}",
        "skill": skill,
        "settings": settings,
        "artifacts": [],
        "approvals": [],
        "execution": [],
    }
    save(projects_root, project)
    return project


def save(projects_root: Path, project: dict) -> None:
    write_json_atomic(projects_root / f"{project['project_id']}.json", project)


def load(projects_root: Path, project_id: str) -> dict:
    return json.loads((projects_root / f"{project_id}.json").read_text(encoding="utf-8-sig"))


def upsert_artifact(project: dict, stage: str, artifact_id: str, content: object, depends_on: list[str] | None = None) -> dict:
    depends_on = depends_on or []
    content_hash = stable_hash(content)
    existing_versions = [item["version"] for item in project["artifacts"] if item["artifact_id"] == artifact_id]
    version = max(existing_versions, default=0) + 1
    artifact = {
        "artifact_id": artifact_id,
        "stage": stage,
        "version": version,
        "hash": content_hash,
        "depends_on": depends_on,
        "status": "draft",
    }
    project["artifacts"].append(artifact)
    invalidate_dependents(project, f"{artifact_id}:v{version - 1}") if version > 1 else None
    return artifact


def approve_artifact(project: dict, artifact_id: str, version: int) -> dict:
    artifact = find_artifact(project, artifact_id, version)
    artifact["status"] = "approved"
    approval = {
        "approval_id": f"project_approval_{uuid.uuid4().hex}",
        "artifact": f"{artifact_id}:v{version}",
        "artifact_hash": artifact["hash"],
        "status": "active",
    }
    project["approvals"].append(approval)
    return approval


def record_execution(project: dict, stage_id: str, prompt_hash: str, artifact_refs: list[str], settings: dict, attempt_number: int) -> dict:
    key_data = {
        "project_id": project["project_id"],
        "stage_id": stage_id,
        "artifact_refs": artifact_refs,
        "prompt_hash": prompt_hash,
        "settings_hash": stable_hash(settings),
        "attempt_number": attempt_number,
    }
    idempotency_key = stable_hash(key_data)
    for item in project["execution"]:
        if item["idempotency_key"] == idempotency_key:
            raise ValueError("duplicate execution idempotency key")
    record = {
        "stage_id": stage_id,
        "artifact_refs": artifact_refs,
        "prompt_hash": prompt_hash,
        "settings_hash": key_data["settings_hash"],
        "attempt_number": attempt_number,
        "idempotency_key": idempotency_key,
        "status": "created",
    }
    project["execution"].append(record)
    return record


def invalidate_dependents(project: dict, changed_ref: str) -> None:
    changed = {changed_ref}
    while changed:
        current = changed.pop()
        for artifact in project["artifacts"]:
            ref = f"{artifact['artifact_id']}:v{artifact['version']}"
            if artifact.get("status") != "invalidated" and current in artifact.get("depends_on", []):
                artifact["status"] = "invalidated"
                changed.add(ref)
        for approval in project["approvals"]:
            if approval.get("status") == "active" and approval.get("artifact") == current:
                approval["status"] = "invalidated"


def find_artifact(project: dict, artifact_id: str, version: int) -> dict:
    for artifact in project["artifacts"]:
        if artifact["artifact_id"] == artifact_id and artifact["version"] == version:
            return artifact
    raise ValueError(f"artifact not found: {artifact_id}:v{version}")
