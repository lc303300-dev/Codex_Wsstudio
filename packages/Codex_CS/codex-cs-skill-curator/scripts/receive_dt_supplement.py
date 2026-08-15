from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from skill_package import load_contract


SCHEMA_VERSION = 1
OPERATION = "supplement_skill_creative_examples"
REQUIRED_OUTPUTS = {"positive_examples", "negative_examples", "boundary_examples"}
OPTIONAL_OUTPUTS = {"optional_creative_guidance"}
REQUIRED_CONSTRAINTS = {
    "preserve_meaning": True,
    "do_not_infer_contract": True,
    "do_not_select_provider": True,
    "do_not_select_model": True,
    "do_not_submit_video": True,
    "requires_user_review": True,
}
FORBIDDEN_KEYS = {
    "contract", "contract_summary", "references", "reference_slots", "materials",
    "min_count", "max_count", "required", "ordered", "media_type", "role",
    "provider", "provider_id", "model", "model_version", "resolution",
    "poll", "download", "submit", "execution", "video_execution_mode",
}
FORBIDDEN_TEXT = re.compile(
    r"(?i)(?:\b(?:seedance|dreamina|即梦|gemini|gpt-image|apimart|comfly)\b|"
    r"\b(?:provider|model_version|resolution|poll(?:ing)?|download|submit_id|"
    r"generate_video|seedance-cli|dreamina\.exe|media_router)\b|"
    r"(?:供应商|提供商|模型版本|分辨率|轮询|下载结果|提交任务|付费执行)|"
    r"(?:必须|需要|应当).{0,18}(?:提供|上传|输入).{0,12}(?:张|个|段)(?:图片|视频|音频|素材)|"
    r"(?:素材|图片|视频|音频).{0,12}(?:min_count|max_count|必填|必选|上限)|"
    r"(?:修改|推断|新增|改写).{0,12}(?:契约|素材槽|素材数量|首帧|尾帧))"
)


class DraftValidationError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftValidationError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DraftValidationError(f"JSON root must be an object: {path}")
    return value


def _nonempty_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DraftValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _scan_pollution(value: Any, path: str = "draft") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                raise DraftValidationError(f"Forbidden contract or execution field at {path}.{key}")
            _scan_pollution(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_pollution(child, f"{path}[{index}]")
    elif isinstance(value, str) and FORBIDDEN_TEXT.search(value):
        raise DraftValidationError(f"Contract, provider, model, or execution pollution detected at {path}")


def validate_request(request: dict[str, Any], skill_id: str) -> None:
    if request.get("schema_version") != SCHEMA_VERSION:
        raise DraftValidationError("dt-request.json schema_version must be 1")
    if request.get("status") != "creative_supplement_pending":
        raise DraftValidationError("dt-request.json must be in creative_supplement_pending state")
    if request.get("operation") != OPERATION or request.get("source_skill_id") != skill_id:
        raise DraftValidationError("dt-request.json identity does not match the staging package")
    constraints = request.get("constraints")
    if not isinstance(constraints, dict):
        raise DraftValidationError("dt-request.json constraints must be an object")
    for key, expected in REQUIRED_CONSTRAINTS.items():
        if constraints.get(key) is not expected:
            raise DraftValidationError(f"dt-request.json constraint {key} must be {expected!r}")
    requested = request.get("requested_outputs")
    if (
        not isinstance(requested, list)
        or any(not isinstance(item, str) for item in requested)
        or not REQUIRED_OUTPUTS.issubset(set(requested))
    ):
        raise DraftValidationError("dt-request.json must request positive, negative, and boundary examples")


def validate_draft(draft: dict[str, Any], skill_id: str) -> dict[str, Any]:
    allowed = {
        "schema_version", "status", "operation", "source_skill_id", "generated_by",
        "provenance", "quality_rubric", "outputs",
    }
    if set(draft) != allowed:
        raise DraftValidationError(f"Draft fields must be exactly: {sorted(allowed)}")
    if draft.get("schema_version") != SCHEMA_VERSION or draft.get("status") != "draft":
        raise DraftValidationError("Draft schema_version must be 1 and status must be draft")
    if draft.get("operation") != OPERATION or draft.get("source_skill_id") != skill_id:
        raise DraftValidationError("Draft identity does not match the staging package")
    if draft.get("generated_by") != "Codex_DT":
        raise DraftValidationError("generated_by must be Codex_DT")

    provenance = draft.get("provenance")
    provenance_fields = {"benchmark_skill_ids", "benchmark_usage", "contract_inference", "topic_rule_copying"}
    if not isinstance(provenance, dict) or set(provenance) != provenance_fields:
        raise DraftValidationError(f"provenance fields must be exactly: {sorted(provenance_fields)}")
    benchmark_ids = provenance.get("benchmark_skill_ids")
    if (
        not isinstance(benchmark_ids, list)
        or not benchmark_ids
        or len(benchmark_ids) != len(set(benchmark_ids))
        or any(not isinstance(item, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item) for item in benchmark_ids)
    ):
        raise DraftValidationError("provenance.benchmark_skill_ids must be a non-empty unique list of Skill ids")
    if provenance.get("benchmark_usage") != "creative_quality_only":
        raise DraftValidationError("Benchmarks may only be used for creative quality")
    if provenance.get("contract_inference") is not False or provenance.get("topic_rule_copying") is not False:
        raise DraftValidationError("Benchmarks must not infer contracts or copy topic-specific rules")

    rubric = draft.get("quality_rubric")
    if not isinstance(rubric, dict) or set(rubric) != {"dimensions", "assessment"}:
        raise DraftValidationError("quality_rubric must contain only dimensions and assessment")
    dimensions = rubric.get("dimensions")
    if (
        not isinstance(dimensions, list)
        or len(dimensions) < 3
        or len(dimensions) != len(set(dimensions))
        or any(not isinstance(item, str) or len(item.strip()) < 2 for item in dimensions)
    ):
        raise DraftValidationError("quality_rubric.dimensions must contain at least three unique dimensions")
    rubric["assessment"] = _nonempty_text(rubric.get("assessment"), "quality_rubric.assessment")
    if len(rubric["assessment"]) < 10:
        raise DraftValidationError("quality_rubric.assessment must explain the quality review")

    outputs = draft.get("outputs")
    if not isinstance(outputs, dict):
        raise DraftValidationError("outputs must be an object")
    if set(outputs) - REQUIRED_OUTPUTS - OPTIONAL_OUTPUTS or not REQUIRED_OUTPUTS.issubset(outputs):
        raise DraftValidationError("outputs must contain positive, negative, and boundary examples only, plus optional creative guidance")

    positive = outputs["positive_examples"]
    if not isinstance(positive, list) or not positive:
        raise DraftValidationError("positive_examples must be a non-empty array")
    for item in positive:
        fields = {"input_conditions", "prompt", "why_it_works"}
        if not isinstance(item, dict) or set(item) != fields:
            raise DraftValidationError(f"Each positive example must contain exactly: {sorted(fields)}")
        for field, minimum in (("input_conditions", 8), ("prompt", 20), ("why_it_works", 8)):
            item[field] = _nonempty_text(item[field], f"positive_examples[].{field}")
            if len(item[field]) < minimum:
                raise DraftValidationError(f"positive_examples[].{field} is too short to be auditable")

    negative = outputs["negative_examples"]
    if not isinstance(negative, list) or not negative:
        raise DraftValidationError("negative_examples must be a non-empty array")
    for item in negative:
        fields = {"input_conditions", "prompt", "reason", "correction"}
        if not isinstance(item, dict) or set(item) != fields:
            raise DraftValidationError(f"Each negative example must contain exactly: {sorted(fields)}")
        for field in fields:
            item[field] = _nonempty_text(item[field], f"negative_examples[].{field}")
            if len(item[field]) < 8:
                raise DraftValidationError(f"negative_examples[].{field} is too short to be auditable")

    boundary = outputs["boundary_examples"]
    if not isinstance(boundary, list) or not boundary:
        raise DraftValidationError("boundary_examples must be a non-empty array")
    for item in boundary:
        fields = {"input_conditions", "boundary", "handling", "why"}
        if not isinstance(item, dict) or set(item) != fields:
            raise DraftValidationError(f"Each boundary example must contain exactly: {sorted(fields)}")
        for field in fields:
            item[field] = _nonempty_text(item[field], f"boundary_examples[].{field}")
            if len(item[field]) < 8:
                raise DraftValidationError(f"boundary_examples[].{field} is too short to be auditable")

    guidance = outputs.get("optional_creative_guidance", [])
    if not isinstance(guidance, list):
        raise DraftValidationError("optional_creative_guidance must be an array")
    outputs["optional_creative_guidance"] = [
        _nonempty_text(item, "optional_creative_guidance[]") for item in guidance
    ]
    _scan_pollution(outputs)
    return draft


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def receive(package: Path, draft_path: Path) -> dict[str, Any]:
    package = package.resolve()
    skill_id = str(load_contract(package).get("skill_id") or "")
    if skill_id != package.name:
        raise DraftValidationError("Staging package contract identity is invalid")
    request = _read_json(package / "dt-request.json")
    validate_request(request, skill_id)
    draft = validate_draft(_read_json(draft_path), skill_id)

    report_path = package / "intake-report.json"
    report = _read_json(report_path)
    if report.get("skill_id") != skill_id:
        raise DraftValidationError("intake-report.json identity does not match the staging package")
    approval = report.get("user_approval")
    if not isinstance(approval, dict) or approval.get("approved") is not False:
        raise DraftValidationError("DT drafts can only be received before user approval")
    supplement = report.get("creative_supplement")
    if not isinstance(supplement, dict):
        raise DraftValidationError("intake-report.json creative_supplement is missing")

    stored_relative = Path("review") / "dt-creative-supplement.draft.json"
    stored = package / stored_relative
    _atomic_json(stored, draft)
    supplement.update({
        "status": "draft_received",
        "generated_by": "Codex_DT",
        "request_path": "dt-request.json",
        "draft_path": stored_relative.as_posix(),
        "requires_user_review": True,
        "reason": "Validated DT creative draft received; not merged into confirmed references.",
    })
    report["user_approval"]["approved"] = False
    if report.get("status") not in {"needs_review", "ready_for_approval"}:
        report["status"] = "ready_for_approval"
    _atomic_json(report_path, report)
    return {
        "status": "draft_received",
        "skill_id": skill_id,
        "draft_path": stored_relative.as_posix(),
        "requires_user_review": True,
        "references_modified": False,
        "published": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and stage a Codex_DT creative supplement draft for user review.")
    parser.add_argument("package", type=Path, help="Staging Skill package containing dt-request.json and intake-report.json")
    parser.add_argument("draft", type=Path, help="Codex_DT draft JSON matching dt-supplement-draft.schema.json")
    args = parser.parse_args()
    try:
        result = receive(args.package, args.draft)
    except DraftValidationError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
