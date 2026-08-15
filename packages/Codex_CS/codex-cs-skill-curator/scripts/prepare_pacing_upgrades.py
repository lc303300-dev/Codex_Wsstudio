from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def rule(rule_type: str, enforcement: str, *, fixed=None, seconds=None, rounding=None, share=1, lookup=None,
         provenance="source_explicit", confidence="high", rationale: str) -> dict:
    return {
        "type": rule_type,
        "enforcement": enforcement,
        "fixed_count": fixed,
        "seconds_per_item": seconds,
        "rounding": rounding,
        "duration_share": share,
        "duration_to_count": lookup or [],
        "provenance": provenance,
        "confidence": confidence,
        "rationale": rationale,
    }


RULES = {
    "architectural-assembly-reveal": {
        "assembly-frames": (1, 6, rule("duration_formula", "required", seconds=5, rounding="ceil", rationale="原始 Skill 明确每完整五秒使用一张尾帧参考，剩余不足五秒仍增加一张。")),
    },
    "dawn-mist-aerial-real-estate": {
        "aerial-scene-frames": (2, 8, rule("duration_lookup", "required", lookup=[
            {"duration_seconds": 5, "count": 2}, {"duration_seconds": 10, "count": 3},
            {"duration_seconds": 15, "count": 5}, {"duration_seconds": 20, "count": 6},
            {"duration_seconds": 25, "count": 7}, {"duration_seconds": 30, "count": 8},
        ], rationale="原始 Skill 提供五至三十秒的非线性镜头数量表，其他时长采用最近锚点。")),
    },
    "giant-ip-landmark-parade": {
        "ip-character": (1, 1, rule("fixed", "required", fixed=1, rationale="IP 身份设定图固定一张，用于全片角色一致性锁定。")),
        "parade-scenes": (1, 10, rule("duration_formula", "required", seconds=3, rounding="floor", rationale="原始 Skill 的正式案例以约三秒一个巡游场景硬切，余量并入末景。")),
    },
    "giant-3d-logo-landmark-video": {
        "logo-design": (1, 1, rule("fixed", "required", fixed=1, rationale="Logo 身份设定图固定一张，用于全片徽标结构与材质一致性锁定。")),
        "landmark-scenes": (1, 7, rule("duration_formula", "required", seconds=4, rounding="floor", provenance="user_approved_inference", confidence="low", rationale="根据十二秒三场景与十秒双场景案例推导约四秒一景，余量并入末景。")),
    },
    "city-real-estate-habitat-promo": {
        "city-context": (1, 2, rule("bounded_recommendation", "recommended", seconds=5, rounding="round", share=2/3, provenance="user_approved_inference", confidence="medium", rationale="城市叙事约占全片三分之二，按约五秒一个城市段落推荐一至两张参考。")),
        "real-estate-context": (1, 3, rule("bounded_recommendation", "recommended", seconds=5, rounding="round", share=1, provenance="user_approved_inference", confidence="medium", rationale="按约五秒推荐一张地产空间参考，并限制为布局、立面、阳台等最多三类。")),
    },
    "sci-fi-city-promo": {
        "city-visual-references": (3, 5, rule("bounded_recommendation", "recommended", seconds=4, rounding="round", provenance="user_approved_inference", confidence="medium", rationale="原始 Skill 稳定建议三至五张城市视觉参考，按约四秒一张计算推荐值并限制在该范围。")),
    },
}


def prepare(library: Path, output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for skill_id, slot_rules in RULES.items():
        source = library / skill_id
        target = output / skill_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        receipt = target / "intake-receipt.json"
        if receipt.exists():
            receipt.unlink()
        contract_path = target / "contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
        summary = []
        for reference in contract["references"]:
            minimum, maximum, count_rule = slot_rules[reference["id"]]
            reference["min_count"] = minimum
            reference["max_count"] = maximum
            reference["count_rule"] = count_rule
            summary.append({"slot_id": reference["id"], **count_rule, "min_count": minimum, "max_count": maximum})
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path = target / "intake-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        report["status"] = "approved"
        report["reference_summary"] = contract["references"]
        report["pacing_rule_summary"] = summary
        report["user_approval"] = {"required": True, "approved": True}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append({"skill_id": skill_id, "staging": str(target), "pacing_rule_summary": summary})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare governed pacing-rule upgrades for the current published Skill library.")
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.library.resolve(), args.output.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
