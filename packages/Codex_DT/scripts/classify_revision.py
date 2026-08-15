#!/usr/bin/env python3
"""Build a deterministic, constrained DT revision request for a CS prompt draft.

This helper does not rewrite prompts, search the corpus, or submit media. It only
classifies user feedback and emits the contract that a later DT authoring step
must follow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


CLASS_EXPLICIT_LOCAL = "explicit_local"
CLASS_AMBIGUOUS_CREATIVE = "ambiguous_creative"
CLASS_STRUCTURAL_REWRITE = "structural_rewrite"
VALID_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}

STRUCTURAL_PATTERNS = (
    r"(?:整体|全部|整段|从头|彻底).{0,8}(?:重写|重构|重做|改写|重新设计|重新编排)",
    r"(?:重写|重构|重做|改写|重新设计|重新编排).{0,8}(?:整体|全部|整段|叙事|结构|镜头顺序|时间线)",
    r"(?:叙事|故事线|时间线|镜头顺序|段落结构).{0,8}(?:重构|重排|重写|重做|调整)",
    r"(?:重新分配|重排).{0,8}(?:所有|全部|整体|镜头|时间|节奏)",
)

AMBIGUOUS_PATTERNS = (
    r"^(?:不满意|不好|不行|不对|再改改|优化一下|调整一下|重来|换一个)[。！!,.， ]*$",
    r"(?:更|不够|太).{0,5}(?:高级|震撼|电影感|有感觉|大气|精彩|好看|自然|流畅|专业|吸引人)",
    r"(?:整体|画面|感觉|效果).{0,5}(?:一般|平淡|无聊|不好|不够|不对)",
    r"(?:提升|加强|优化|改善).{0,5}(?:质感|氛围|风格|感觉|效果|创意)$",
)

LOCAL_TARGET_PATTERNS = (
    r"第[一二三四五六七八九十\d]+(?:个|段|镜|镜头|秒)",
    r"(?:开头|结尾|首帧|尾帧|某个镜头|这个镜头|运镜|动作|音乐|音效|字幕|光线|色调|速度|时长|比例|画幅)",
    r"\d+(?:\.\d+)?\s*(?:秒|s|帧|%)",
    r"(?:改成|换成|替换为|删除|去掉|不要|保留|增加|添加|缩短|延长|调到|改为)",
)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_feedback(user_feedback: str) -> tuple[str, list[str]]:
    """Classify feedback, returning a stable class and human-readable reasons."""
    feedback = re.sub(r"\s+", " ", user_feedback).strip()
    if not feedback:
        raise ValueError("user_feedback must not be empty")

    if _matches_any(STRUCTURAL_PATTERNS, feedback):
        return CLASS_STRUCTURAL_REWRITE, ["反馈明确要求重排叙事、时间线或整体提示词结构。"]

    has_ambiguous_signal = _matches_any(AMBIGUOUS_PATTERNS, feedback)
    has_local_target = _matches_any(LOCAL_TARGET_PATTERNS, feedback)
    if has_ambiguous_signal and not has_local_target:
        return CLASS_AMBIGUOUS_CREATIVE, ["反馈表达审美目标或不满意，但缺少可直接执行的局部修改。"]

    if has_local_target:
        return CLASS_EXPLICIT_LOCAL, ["反馈包含明确的修改对象、位置、参数或替换动作。"]

    return CLASS_AMBIGUOUS_CREATIVE, ["反馈没有形成可确定执行的局部编辑指令。"]


def validate_input(payload: dict[str, Any]) -> None:
    for key in ("current_prompt", "user_feedback", "locked_context"):
        if key not in payload:
            raise ValueError(f"missing required field: {key}")
    if not isinstance(payload["current_prompt"], str) or not payload["current_prompt"].strip():
        raise ValueError("current_prompt must be a non-empty string")
    if not isinstance(payload["user_feedback"], str) or not payload["user_feedback"].strip():
        raise ValueError("user_feedback must be a non-empty string")

    locked = payload["locked_context"]
    if not isinstance(locked, dict):
        raise ValueError("locked_context must be an object")
    for key in ("contract_rules", "material_order", "ratio", "duration_seconds"):
        if key not in locked:
            raise ValueError(f"missing locked_context field: {key}")
    if not isinstance(locked["contract_rules"], list) or not all(
        isinstance(item, str) and item.strip() for item in locked["contract_rules"]
    ):
        raise ValueError("locked_context.contract_rules must be a list of non-empty strings")
    if not isinstance(locked["material_order"], list) or not all(
        isinstance(item, str) and item.strip() for item in locked["material_order"]
    ):
        raise ValueError("locked_context.material_order must be a list of non-empty strings")
    if locked["ratio"] not in VALID_RATIOS:
        raise ValueError(f"locked_context.ratio must be one of: {', '.join(sorted(VALID_RATIOS))}")
    duration = locked["duration_seconds"]
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError("locked_context.duration_seconds must be a positive number")


def build_revision_request(payload: dict[str, Any]) -> dict[str, Any]:
    validate_input(payload)
    classification, reasons = classify_feedback(payload["user_feedback"])
    should_search = classification in {CLASS_AMBIGUOUS_CREATIVE, CLASS_STRUCTURAL_REWRITE}
    scope = "仅修改用户明确指出的局部内容" if classification == CLASS_EXPLICIT_LOCAL else "按用户反馈优化，但保留所有锁定上下文"

    return {
        "schema_version": "1.0",
        "kind": "codex_dt_prompt_revision_request",
        "classification": classification,
        "classification_reasons": reasons,
        "should_search_corpus": should_search,
        "corpus_search": {
            "max_results": 3 if should_search else 0,
            "purpose": "仅提取可迁移的镜头结构或导演方法，不复制案例提示词。" if should_search else "明确局部修改不需要语料库。",
        },
        "current_prompt": payload["current_prompt"],
        "current_prompt_sha256": _canonical_hash(payload["current_prompt"]),
        "user_feedback": payload["user_feedback"],
        "locked_context": payload["locked_context"],
        "locked_context_sha256": _canonical_hash(payload["locked_context"]),
        "revision_policy": {
            "scope": scope,
            "preserve_unspecified_content": True,
            "contract_rules_are_immutable": True,
            "material_order_is_immutable": True,
            "ratio_is_immutable_unless_feedback_explicitly_changes_project_settings": True,
            "duration_is_immutable_unless_feedback_explicitly_changes_project_settings": True,
            "forbid_model_selection_from_corpus": True,
            "forbid_media_submission": True,
        },
        "required_result_fields": [
            "schema_version",
            "kind",
            "classification",
            "revised_prompt",
            "changed_sections",
            "preserved_unspecified_content",
            "locked_context_sha256",
            "corpus_usage",
        ],
    }


def _read_payload(path: Path | None) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify CS prompt feedback and build a constrained DT revision request.")
    parser.add_argument("--input", type=Path, help="UTF-8 JSON input. Reads stdin when omitted.")
    parser.add_argument("--out", type=Path, help="Optional UTF-8 JSON output path.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        result = build_revision_request(_read_payload(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
