from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency fallback
    yaml = None


ALLOWED_WORKFLOW_PROFILES = {"simple", "staged"}
ALLOWED_INTERACTION_PROFILES = {"conversation", "gui", "hybrid"}
ALLOWED_GATES = {"none", "decision", "approval", "paid-execution", "batch-approval"}
REQUIRED_META_FIELDS = {
    "schema",
    "name",
    "version",
    "primary-output",
    "workflow-profile",
    "interaction-profile",
}
POLLUTION_PATTERNS = {
    "PROVIDER_POLLUTION": re.compile(r"\b(Nano Banana|MiniMax|Kling|Seedance|Dreamina|Jimeng|ComfyUI|Gemini)\b", re.IGNORECASE),
    "MODEL_POLLUTION": re.compile(r"\b(seedance\s*2(?:\.0|\.5)?|gpt-image|gemini-\d|kling|h3)\b", re.IGNORECASE),
    "DAG_POLLUTION": re.compile(r"\b(DAG[_ -]?ID|workflow[_ -]?id|gateway protocol)\b", re.IGNORECASE),
    "CREDENTIAL_POLLUTION": re.compile(r"\b(API[_-]?KEY|Authorization|Bearer\s+[A-Za-z0-9._-]+|Cookie:)\b", re.IGNORECASE),
    "LOCAL_PATH_POLLUTION": re.compile(r"[A-Za-z]:\\|/[Uu]sers/|/[Hh]ome/"),
    "DANGEROUS_COMMAND": re.compile(r"\b(rm\s+-rf|Remove-Item\s+.*-Recurse|git\s+reset\s+--hard)\b", re.IGNORECASE),
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\r\n")
    return parse_yaml(raw), body


def parse_yaml_text(path: Path) -> dict[str, Any]:
    return parse_yaml(read_text(path))


def parse_yaml(raw: str) -> dict[str, Any]:
    if yaml is not None:
        data = yaml.safe_load(raw) or {}
        return data if isinstance(data, dict) else {}
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(line[4:].strip().strip("'\""))
            continue
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if value:
                data[key] = value.strip("'\"")
            else:
                data[key] = []
    return data


def package_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if ".codex-flow-private" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_package(root: Path) -> list[str]:
    root = root.resolve()
    issues: list[str] = []
    skill_path = root / "SKILL.md"
    meta_path = root / "meta.yaml"
    if not skill_path.is_file():
        issues.append("MISSING_SKILL_MD")
    if not meta_path.is_file():
        issues.append("MISSING_META_YAML")
    if issues:
        return issues

    frontmatter, body = parse_frontmatter(skill_path)
    meta = parse_yaml_text(meta_path)
    name = meta.get("name") or frontmatter.get("name")
    if not frontmatter.get("name"):
        issues.append("MISSING_FRONTMATTER_NAME")
    if not frontmatter.get("description"):
        issues.append("MISSING_FRONTMATTER_DESCRIPTION")
    for field in sorted(REQUIRED_META_FIELDS):
        if field not in meta:
            issues.append(f"MISSING_META_{field.upper().replace('-', '_')}")
    if name and frontmatter.get("name") and meta.get("name") and frontmatter["name"] != meta["name"]:
        issues.append("NAME_MISMATCH")
    if name and root.name != name:
        issues.append("DIRECTORY_NAME_MISMATCH")
    if meta.get("workflow-profile") not in ALLOWED_WORKFLOW_PROFILES:
        issues.append("INVALID_WORKFLOW_PROFILE")
    if meta.get("interaction-profile") not in ALLOWED_INTERACTION_PROFILES:
        issues.append("INVALID_INTERACTION_PROFILE")
    if meta.get("workflow-profile") == "staged" and not (root / "workflow.yaml").is_file():
        issues.append("MISSING_WORKFLOW_YAML")
    if (root / "ui" / "dist").exists():
        issues.append("UI_DIST_PRESENT_DO_NOT_LOAD")

    text_to_scan = "\n".join([json.dumps(frontmatter, ensure_ascii=False), json.dumps(meta, ensure_ascii=False), body])
    for issue, pattern in POLLUTION_PATTERNS.items():
        if pattern.search(text_to_scan):
            issues.append(issue)

    issues.extend(validate_references(root, meta))
    if (root / "workflow.yaml").is_file():
        issues.extend(validate_workflow(root / "workflow.yaml"))
    return sorted(set(issues))


def validate_references(root: Path, meta: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    declared_paths = collect_declared_reference_paths(meta)
    for relative in sorted(declared_paths):
        if not (root / relative).is_file():
            issues.append(f"MISSING_REFERENCE:{relative}")
    references_root = root / "references"
    if references_root.is_dir():
        for path in sorted(item for item in references_root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if relative not in declared_paths:
                issues.append(f"UNREFERENCED_RESOURCE:{relative}")
    seen: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name in {"SKILL.md", "meta.yaml", "workflow.yaml"}:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(root).as_posix()
        if digest in seen:
            issues.append(f"DUPLICATE_RESOURCE:{seen[digest]}:{relative}")
        else:
            seen[digest] = relative
    return issues


def collect_declared_reference_paths(meta: dict[str, Any]) -> set[str]:
    declared: set[str] = set()
    references = meta.get("references") or {}
    if isinstance(references, dict):
        for value in references.values():
            if isinstance(value, dict) and value.get("path"):
                declared.add(str(value["path"]).replace("\\", "/"))
    elif isinstance(references, list):
        for value in references:
            if isinstance(value, dict) and value.get("path"):
                declared.add(str(value["path"]).replace("\\", "/"))
            elif isinstance(value, str):
                declared.add(value.replace("\\", "/"))
    return declared


def validate_workflow(path: Path) -> list[str]:
    issues: list[str] = []
    workflow = parse_yaml_text(path)
    stages = workflow.get("stages")
    if not isinstance(stages, list) or not stages:
        return ["MISSING_WORKFLOW_STAGES"]
    ids: set[str] = set()
    dependencies: dict[str, list[str]] = {}
    for stage in stages:
        if not isinstance(stage, dict):
            issues.append("INVALID_STAGE")
            continue
        stage_id = stage.get("id")
        if not stage_id:
            issues.append("MISSING_STAGE_ID")
            continue
        if stage_id in ids:
            issues.append(f"DUPLICATE_STAGE:{stage_id}")
        ids.add(str(stage_id))
        gate = stage.get("gate", "none")
        if gate not in ALLOWED_GATES:
            issues.append(f"INVALID_GATE:{stage_id}:{gate}")
        depends_on = stage.get("depends-on", []) or []
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        dependencies[str(stage_id)] = [str(item) for item in depends_on]
    for stage_id, deps in dependencies.items():
        for dep in deps:
            if dep not in ids:
                issues.append(f"UNKNOWN_DEPENDENCY:{stage_id}:{dep}")
    for stage_id in dependencies:
        if has_cycle(stage_id, dependencies, set(), set()):
            issues.append("WORKFLOW_CYCLE")
            break
    return issues


def has_cycle(node: str, graph: dict[str, list[str]], visiting: set[str], visited: set[str]) -> bool:
    if node in visited:
        return False
    if node in visiting:
        return True
    visiting.add(node)
    for dep in graph.get(node, []):
        if has_cycle(dep, graph, visiting, visited):
            return True
    visiting.remove(node)
    visited.add(node)
    return False
