from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from receive_dt_supplement import DraftValidationError, validate_draft
from skill_package import load_contract


class SupplementApprovalError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupplementApprovalError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SupplementApprovalError(f"JSON root must be an object: {path}")
    return value


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def render_examples(draft: dict[str, Any]) -> str:
    outputs = draft["outputs"]
    benchmark_ids = "、".join(draft["provenance"]["benchmark_skill_ids"])
    lines = [
        "## Codex_DT 创意补充（用户已批准）",
        "",
        f"> 来源：Codex_DT 创意补充草稿；状态：user_approved；质量基准：{benchmark_ids}。",
        "> 仅借鉴范例结构与完整度，不定义素材契约，不复制基准 Skill 的题材规则。",
        "",
        "### 正例",
    ]
    for index, item in enumerate(outputs["positive_examples"], 1):
        lines.extend([
            "",
            f"#### 正例 {index}",
            "",
            f"- 输入条件：{item['input_conditions']}",
            "- 提示词或写法：",
            "",
            item["prompt"],
            "",
            f"- 合格原因：{item['why_it_works']}",
        ])
    lines.extend(["", "### 反例"])
    for index, item in enumerate(outputs["negative_examples"], 1):
        lines.extend([
            "",
            f"#### 反例 {index}",
            "",
            f"- 输入条件：{item['input_conditions']}",
            f"- 错误写法：{item['prompt']}",
            f"- 失败原因：{item['reason']}",
            f"- 修正策略：{item['correction']}",
        ])
    lines.extend(["", "### 边界案例"])
    for index, item in enumerate(outputs["boundary_examples"], 1):
        lines.extend([
            "",
            f"#### 边界案例 {index}",
            "",
            f"- 输入条件：{item['input_conditions']}",
            f"- 边界：{item['boundary']}",
            f"- 处理：{item['handling']}",
            f"- 原因：{item['why']}",
        ])
    lines.extend([
        "",
        "### 质量审计",
        "",
        f"- 维度：{'、'.join(draft['quality_rubric']['dimensions'])}",
        f"- 结论：{draft['quality_rubric']['assessment']}",
        "",
    ])
    return "\n".join(lines)


def render_guidance(draft: dict[str, Any]) -> str:
    guidance = draft["outputs"].get("optional_creative_guidance", [])
    if not guidance:
        return ""
    lines = [
        "## Codex_DT 可选创意补充（用户已批准）",
        "",
        "> 来源：Codex_DT 创意补充草稿；状态：user_approved；不定义素材契约。",
        "",
    ]
    lines.extend(f"- {item}" for item in guidance)
    return "\n".join(lines) + "\n"


def approve(package: Path, approved_by: str) -> dict[str, Any]:
    if approved_by != "user":
        raise SupplementApprovalError("Creative supplement approval must come from the user")
    package = package.resolve(strict=True)
    skill_id = str(load_contract(package).get("skill_id") or "")
    if skill_id != package.name:
        raise SupplementApprovalError("Staging package identity is invalid")
    report_path = package / "intake-report.json"
    report = read_json(report_path)
    supplement = report.get("creative_supplement")
    if not isinstance(supplement, dict) or supplement.get("status") != "draft_received":
        raise SupplementApprovalError("Creative supplement must be in draft_received state")
    relative = supplement.get("draft_path")
    if not isinstance(relative, str) or not relative:
        raise SupplementApprovalError("Creative supplement draft_path is missing")
    draft_path = (package / relative).resolve(strict=True)
    try:
        draft = validate_draft(read_json(draft_path), skill_id)
    except DraftValidationError as exc:
        raise SupplementApprovalError(str(exc)) from exc

    examples_path = package / "references" / "examples.md"
    examples = examples_path.read_text(encoding="utf-8-sig").rstrip()
    marker = "## Codex_DT 创意补充（用户已批准）"
    if marker in examples:
        raise SupplementApprovalError("Approved DT examples are already present")
    write_text_atomic(examples_path, examples + "\n\n" + render_examples(draft))

    guidance_block = render_guidance(draft)
    if guidance_block:
        guidance_path = package / "references" / "creative-guidance.md"
        guidance = guidance_path.read_text(encoding="utf-8-sig").rstrip()
        write_text_atomic(guidance_path, guidance + "\n\n" + guidance_block)

    supplement.update({
        "status": "user_approved",
        "generated_by": "Codex_DT",
        "requires_user_review": False,
        "reason": "User approved the validated DT creative supplement and it was merged into references.",
    })
    summary = report.setdefault("extraction_summary", {})
    summary["positive_examples"] = len(draft["outputs"]["positive_examples"])
    summary["negative_examples"] = len(draft["outputs"]["negative_examples"])
    summary["boundary_examples"] = len(draft["outputs"]["boundary_examples"])
    if not report.get("blocking_questions") and not report.get("contract_conflicts") and not report.get("validation_issues"):
        report["status"] = "ready_for_approval"
    write_json_atomic(report_path, report)
    return {
        "status": "user_approved",
        "skill_id": skill_id,
        "references_modified": True,
        "published": False,
        "intake_report_status": report.get("status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge a user-approved Codex_DT creative supplement into a staging Skill.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--approved-by", required=True, choices=["user"])
    args = parser.parse_args()
    try:
        result = approve(args.package, args.approved_by)
    except (SupplementApprovalError, FileNotFoundError, OSError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
