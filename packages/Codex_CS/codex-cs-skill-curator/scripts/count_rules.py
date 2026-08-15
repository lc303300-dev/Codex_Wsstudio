from __future__ import annotations

from copy import deepcopy


FIXED_ROLES = {"identity", "style", "start_frame", "end_frame", "music", "sound"}


def default_count_rule(reference: dict) -> dict:
    minimum = int(reference.get("min_count", 0))
    maximum = reference.get("max_count")
    role = reference.get("role")
    if role in FIXED_ROLES or maximum == minimum:
        fixed = max(minimum, 1 if reference.get("required") else 0)
        if maximum is not None:
            fixed = min(fixed, maximum)
        return {
            "type": "fixed",
            "enforcement": "required",
            "fixed_count": fixed,
            "seconds_per_item": None,
            "rounding": None,
            "duration_share": 1,
            "duration_to_count": [],
            "provenance": "curator_default",
            "confidence": "medium",
            "rationale": "该素材承担稳定身份、风格、边界帧或声音基准职责，默认数量不随视频时长增加。",
        }
    return {
        "type": "bounded_recommendation",
        "enforcement": "recommended",
        "fixed_count": None,
        "seconds_per_item": 5,
        "rounding": "ceil",
        "duration_share": 1,
        "duration_to_count": [],
        "provenance": "curator_default",
        "confidence": "low",
        "rationale": "来源没有明确节奏时，默认每约五秒推荐一项可变场景素材，并保留契约上下限作为硬边界。",
    }


def add_missing_count_rules(contract: dict) -> tuple[dict, list[dict]]:
    result = deepcopy(contract)
    additions = []
    for reference in result.get("references", []):
        if "count_rule" in reference:
            continue
        rule = default_count_rule(reference)
        reference["count_rule"] = rule
        additions.append({"slot_id": reference.get("id"), **rule})
    return result, additions
