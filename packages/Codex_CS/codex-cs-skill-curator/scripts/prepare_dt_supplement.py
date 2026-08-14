from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from skill_package import REQUIRED_KNOWLEDGE, load_contract, read_text


MISSING_EXAMPLE_PATTERNS = (
    r"原始资料未提供示例",
    r"未提供(?:提示词)?范例",
    r"没有(?:提示词)?示例",
)
CREATIVE_HINT_PATTERN = re.compile(
    r"镜头|运镜|camera|dolly|pan|tilt|动作|变化|转场|光|色|材质|声音|音效|节奏|连续性",
    re.IGNORECASE,
)


def compact_text(text: str, limit: int = 6000) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[TRUNCATED_FOR_DT_REQUEST]"


def should_request_supplement(root: Path) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    examples = read_text(root / REQUIRED_KNOWLEDGE["examples"])
    creative = read_text(root / REQUIRED_KNOWLEDGE["creative_guidance"])

    if any(re.search(pattern, examples) for pattern in MISSING_EXAMPLE_PATTERNS):
        reasons.append("examples_missing")
    if not re.search(r"正例|positive|反例|negative|边界|boundary", examples, re.IGNORECASE):
        reasons.append("example_categories_incomplete")
    if not CREATIVE_HINT_PATTERN.search(creative):
        reasons.append("creative_guidance_too_thin")

    return bool(reasons), reasons


def build_request(root: Path, *, force: bool = False) -> dict:
    root = root.resolve()
    contract = load_contract(root)
    required, reasons = should_request_supplement(root)
    status = "creative_supplement_pending" if required or force else "not_required"

    knowledge = {
        key: compact_text(read_text(root / path))
        for key, path in REQUIRED_KNOWLEDGE.items()
    }
    contract_summary = {
        "skill_id": contract.get("skill_id"),
        "display_name": contract.get("display_name"),
        "description": contract.get("description"),
        "references": contract.get("references", []),
        "allowed_modes": contract.get("video", {}).get("allowed_modes", []),
    }

    return {
        "schema_version": 1,
        "status": status,
        "operation": "supplement_skill_creative_examples",
        "source_skill_id": contract.get("skill_id", root.name),
        "source_material": {
            "skill_summary": read_text(root / "SKILL.md"),
            "contract_summary": contract_summary,
            "creative_guidance": knowledge["creative_guidance"],
            "community_experience": knowledge["community_experience"],
            "failure_cases": knowledge["failure_cases"],
            "existing_examples": knowledge["examples"],
        },
        "constraints": {
            "preserve_meaning": True,
            "do_not_infer_contract": True,
            "do_not_select_provider": True,
            "do_not_select_model": True,
            "do_not_submit_video": True,
            "language": "zh-CN",
            "preserve_professional_english": True,
            "requires_user_review": True,
        },
        "requested_outputs": [
            "positive_examples",
            "negative_examples",
            "boundary_examples",
            "optional_creative_guidance",
        ],
        "detected_reasons": reasons,
        "integration_note": "Pass this request to Codex_DT text authoring only. Do not call video generation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a constrained Codex_DT creative supplement request.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--force", action="store_true", help="Generate a pending request even when examples look complete.")
    args = parser.parse_args()

    payload = build_request(args.package, force=args.force)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
