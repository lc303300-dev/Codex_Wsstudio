from __future__ import annotations

import argparse
import json
from pathlib import Path


MEDIA_NAMES = {"image": "图片", "video": "视频", "audio": "音频"}


def load_contract(path: Path) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(contract.get("references"), list) or not contract["references"]:
        raise ValueError("contract.json must contain at least one reference slot")
    return contract


def normalize_received(payload: dict | None) -> dict[str, int]:
    if not payload:
        return {}
    raw = payload.get("received", payload)
    if not isinstance(raw, dict):
        raise ValueError("received state must be an object")
    result: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"received count for {key} must be a non-negative integer")
        result[str(key)] = value
    return result


def build_collection_state(contract: dict, received: dict[str, int] | None = None) -> dict:
    received = received or {}
    slots = []
    missing_required = []
    invalid = []
    for item in contract["references"]:
        count = received.get(item["id"], 0)
        minimum = item["min_count"]
        maximum = item["max_count"]
        if maximum is not None and count > maximum:
            status = "too_many"
            invalid.append(item["id"])
        elif count < minimum:
            status = "missing" if count == 0 else "insufficient"
            if item["required"]:
                missing_required.append(item["id"])
        else:
            status = "ready"
        slots.append({
            "id": item["id"],
            "media_type": item["media_type"],
            "role": item["role"],
            "description": item["description"],
            "required": item["required"],
            "min_count": minimum,
            "max_count": maximum,
            "ordered": item["ordered"],
            "observation_required": item["observation_required"],
            "received_count": count,
            "status": status,
        })
    total_received = sum(slot["received_count"] for slot in slots)
    if total_received == 0:
        state = "skill_selected"
    elif invalid:
        state = "collecting_materials"
    elif missing_required:
        state = "collecting_materials"
    elif total_received:
        state = "materials_ready"
    return {
        "skill_id": contract["skill_id"],
        "display_name": contract["display_name"],
        "state": state,
        "slots": slots,
        "missing_required": missing_required,
        "invalid_slots": invalid,
    }


def count_text(minimum: int, maximum: int | None) -> str:
    if maximum is None:
        return f"至少 {minimum} 项"
    if minimum == maximum:
        return f"{minimum} 项"
    return f"{minimum}–{maximum} 项"


def render_guidance(state: dict, *, only_missing: bool = False) -> str:
    lines = [f"已选择「{state['display_name']}」。请按以下清单准备素材："]
    visible = []
    for slot in state["slots"]:
        if only_missing and slot["status"] == "ready":
            continue
        visible.append(slot)
    if not visible:
        return f"「{state['display_name']}」所需素材已经齐全，可以进入提示词创作流程。"
    for index, slot in enumerate(visible, 1):
        requirement = "必选" if slot["required"] else "可选"
        media = MEDIA_NAMES.get(slot["media_type"], slot["media_type"])
        details = [requirement, media, count_text(slot["min_count"], slot["max_count"])]
        if slot["ordered"]:
            details.append("多项时按使用顺序提供")
        if slot["observation_required"]:
            details.append("创作前需要观察内容")
        if slot["status"] == "too_many":
            details.append(f"当前已提供 {slot['received_count']} 项，数量超限")
        elif slot["received_count"]:
            details.append(f"当前已提供 {slot['received_count']} 项")
        lines.append(f"{index}. {slot['description']}（{'；'.join(details)}）")
    if only_missing:
        lines.append("请只补充以上尚未满足或需要修正的项目。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a contract-driven material checklist for a selected Codex_CS Skill.")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--state", type=Path, help="JSON containing received counts, keyed by reference slot id")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    contract = load_contract(args.contract)
    payload = json.loads(args.state.read_text(encoding="utf-8-sig")) if args.state else None
    state = build_collection_state(contract, normalize_received(payload))
    state["guidance"] = render_guidance(state, only_missing=args.only_missing)
    print(json.dumps(state, ensure_ascii=False, indent=2) if args.json else state["guidance"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
