from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


IS_ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RATIOS = {"21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    block = text.split("\n---\n", 1)[0].splitlines()[1:]
    result = {}
    for line in block:
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError("invalid frontmatter line")
        result[key.strip()] = value.strip()
    return result


def validate(root: Path) -> list[str]:
    issues: list[str] = []
    required = ["SKILL.md", "contract.json", "routing.json", "references/creative-guidance.md", "references/failure-cases.md", "references/examples.md"]
    for relative in required:
        if not (root / relative).is_file():
            issues.append(f"MISSING:{relative}")
    if issues:
        return issues
    try:
        metadata = frontmatter(root / "SKILL.md")
        contract = read_json(root / "contract.json")
        routing = read_json(root / "routing.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"INVALID:{exc}"]
    skill_id = root.name
    if set(metadata) != {"name", "description"} or metadata.get("name") != skill_id or not SKILL_NAME.fullmatch(skill_id):
        issues.append("INVALID_SKILL_FRONTMATTER")
    if contract.get("schema_version") != 1 or contract.get("skill_id") != skill_id:
        issues.append("INVALID_CONTRACT_IDENTITY")
    if routing.get("schema_version") != 1 or routing.get("skill_id") != skill_id:
        issues.append("INVALID_ROUTING_IDENTITY")
    references = contract.get("references")
    if not isinstance(references, list) or not references:
        issues.append("INVALID_REFERENCES")
        references = []
    ids = [item.get("id") for item in references if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or contract.get("reference_policy", {}).get("allowed_slot_ids") != ids:
        issues.append("INVALID_REFERENCE_POLICY")
    for reference in references:
        required_fields = {"id", "media_type", "role", "required", "min_count", "max_count", "ordered", "observation_required", "send_to_generation", "description"}
        if set(reference) != required_fields or reference.get("media_type") != "image" or reference.get("min_count", 0) < 0:
            issues.append(f"INVALID_REFERENCE:{reference.get('id')}")
        maximum = reference.get("max_count")
        if maximum is not None and maximum < reference.get("min_count", 0):
            issues.append(f"INVALID_REFERENCE_COUNT:{reference.get('id')}")
    output = contract.get("output", {})
    if not output.get("requires_ratio_confirmation") or not set(output.get("supported_ratios", [])) <= RATIOS:
        issues.append("INVALID_OUTPUT_RATIOS")
    if contract.get("execution", {}).get("provider_neutral") is not True:
        issues.append("PROVIDER_NEUTRAL_REQUIRED")
    package_text = "\n".join(path.read_text(encoding="utf-8-sig") for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".json", ".yaml", ".yml"})
    forbidden = ["API_KEY", "authorization header", "dreamina cli"]
    for token in forbidden:
        if token.casefold() in package_text.casefold():
            issues.append(f"FORBIDDEN_IMPLEMENTATION:{token}")
    if skill_id == "scene-storyboard-grid" and ids != ["scene-base", "identity-design"]:
        issues.append("SCENE_GRID_MUST_HAVE_EXACTLY_TWO_DECLARED_SLOTS")
    return list(dict.fromkeys(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    issues = validate(args.package.resolve())
    print(json.dumps({"package": args.package.resolve().as_posix(), "valid": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())

