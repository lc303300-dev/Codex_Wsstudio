from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


IS_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_VERSION = "2.0.0"
HASH_ALGORITHM = "codex-is-package-sha256-v2"
TEXT_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt"}
TEMPLATE_MARKERS = re.compile(r"\{\{[^}]+\}\}|CURATOR-REQUIRED|\bTODO\b|\bTBD\b|START OF FILE", re.I)
FORBIDDEN = re.compile(r"API[_ -]?KEY|authorization\s*header|cookie\s*=|dreamina\s*cli|provider adapter|polling|download loop", re.I)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def package_sha256(root: Path, *, exclude: set[str] | None = None) -> str:
    excluded = exclude or {"intake-receipt.json"}
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in excluded):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = canonical_bytes(path)
        digest.update(len(relative).to_bytes(8, "big")); digest.update(relative)
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return digest.hexdigest()


def core_sha256(root: Path) -> str:
    return package_sha256(root, exclude={"intake-receipt.json", "intake-report.json"})


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    result = {}
    for line in text.split("\n---\n", 1)[0].splitlines()[1:]:
        key, separator, value = line.partition(":")
        if not separator: raise ValueError("invalid frontmatter line")
        result[key.strip()] = value.strip()
    return result


def schema_issues(instance: dict, schema_path: Path, label: str) -> list[str]:
    validator = Draft202012Validator(read_json(schema_path))
    return [f"{label}:{'/'.join(str(p) for p in error.absolute_path)}:{error.message}" for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))]


def validate_package(root: Path, *, require_report: bool = False, require_receipt: bool = False) -> list[str]:
    issues: list[str] = []
    required = ["SKILL.md", "contract.json", "routing.json", "references/creative-guidance.md", "references/failure-cases.md", "references/examples.md"]
    if require_report: required.append("intake-report.json")
    if require_receipt: required.append("intake-receipt.json")
    for relative in required:
        if not (root / relative).is_file(): issues.append(f"MISSING:{relative}")
    if issues: return issues
    try:
        metadata, contract, routing = frontmatter(root / "SKILL.md"), read_json(root / "contract.json"), read_json(root / "routing.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"INVALID:{exc}"]
    issues += schema_issues(contract, IS_ROOT / "shared" / "schemas" / "contract.schema.json", "CONTRACT_SCHEMA")
    issues += schema_issues(routing, IS_ROOT / "skill-registry" / "schemas" / "routing.schema.json", "ROUTING_SCHEMA")
    skill_id = root.name
    if set(metadata) != {"name", "description"} or metadata.get("name") != skill_id or contract.get("skill_id") != skill_id or routing.get("skill_id") != skill_id:
        issues.append("IDENTITY_MISMATCH")
    references = contract.get("references", [])
    ids = [item.get("id") for item in references]
    if len(ids) != len(set(ids)) or contract.get("reference_policy", {}).get("allowed_slot_ids") != ids: issues.append("REFERENCE_ORDER_MISMATCH")
    if contract.get("input_mode") == "text_only" and references: issues.append("TEXT_ONLY_MUST_NOT_DECLARE_REFERENCES")
    if contract.get("input_mode") == "reference_conditioned" and not references: issues.append("REFERENCE_CONDITIONED_REQUIRES_SLOTS")
    for reference in references:
        if reference.get("required") and reference.get("min_count", 0) < 1: issues.append(f"REQUIRED_SLOT_MIN:{reference.get('id')}")
        if not reference.get("required") and reference.get("min_count") != 0: issues.append(f"OPTIONAL_SLOT_MIN:{reference.get('id')}")
        maximum = reference.get("max_count")
        if maximum is not None and maximum < reference.get("min_count", 0): issues.append(f"SLOT_COUNT:{reference.get('id')}")
    workload = contract.get("workload", {})
    for key in ("scene_count", "candidate_count_per_scene"):
        bounds = workload.get(key, {}); maximum = bounds.get("max")
        if maximum is not None and maximum < bounds.get("min", 1): issues.append(f"WORKLOAD_RANGE:{key}")
    if not workload.get("batch_allowed") and ((workload.get("scene_count", {}).get("max") or 2) > 1 or (workload.get("candidate_count_per_scene", {}).get("max") or 2) > 1): issues.append("BATCH_RANGE_CONFLICT")
    for relative in contract.get("knowledge", {}).values():
        target = (root / relative).resolve()
        try: target.relative_to(root.resolve())
        except ValueError: issues.append(f"KNOWLEDGE_PATH_ESCAPE:{relative}"); continue
        if not target.is_file(): issues.append(f"MISSING_KNOWLEDGE:{relative}")
    package_text = "\n".join(path.read_text(encoding="utf-8-sig", errors="ignore") for path in root.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS)
    if TEMPLATE_MARKERS.search(package_text): issues.append("UNRESOLVED_TEMPLATE_MARKER")
    if FORBIDDEN.search(package_text): issues.append("FORBIDDEN_EXECUTION_OR_SECRET_CONTENT")
    if require_report:
        report = read_json(root / "intake-report.json")
        issues += schema_issues(report, IS_ROOT / "image-skill-curator" / "assets" / "intake-report.schema.json", "REPORT_SCHEMA")
        if report.get("skill_id") != skill_id: issues.append("REPORT_IDENTITY_MISMATCH")
    if require_receipt:
        receipt = read_json(root / "intake-receipt.json")
        issues += schema_issues(receipt, IS_ROOT / "image-skill-curator" / "assets" / "intake-receipt.schema.json", "RECEIPT_SCHEMA")
        if receipt.get("skill_id") != skill_id or receipt.get("package_sha256") != package_sha256(root): issues.append("STALE_RECEIPT")
    return list(dict.fromkeys(issues))
