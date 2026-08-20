from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

from style_library import archetypes as community_archetypes


FLOW_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS = FLOW_ROOT / "business-skills"
DEFAULT_REGISTRY = FLOW_ROOT / ".codex-flow-private" / "compiled" / "registry.json"
IMAGE_STYLE_LIBRARY_TERMS = (
    "style",
    "style transfer",
    "reference image",
    "redraw",
    "风格",
    "风格迁移",
    "参考图",
    "重绘",
    "版式",
    "视觉语言",
)


def load_skill_package_module():
    path = Path(__file__).with_name("skill_package.py")
    spec = importlib.util.spec_from_file_location("codex_flow_platform_skill_package", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_package = load_skill_package_module()


def discover(skills_root: Path) -> tuple[list[dict], list[dict], dict]:
    records: list[dict] = []
    rejected: list[dict] = []
    runtime: dict = {}
    if not skills_root.exists():
        return records, rejected, runtime
    for root in sorted(item for item in skills_root.iterdir() if item.is_dir()):
        issues = skill_package.validate_package(root)
        if issues:
            rejected.append({"skill_id": root.name, "issues": issues})
            continue
        frontmatter, _ = skill_package.parse_frontmatter(root / "SKILL.md")
        meta = skill_package.parse_yaml_text(root / "meta.yaml")
        records.append({
            "skill_id": meta["name"],
            "source": meta.get("source", "codex-flow"),
            "version": meta.get("version", "1.0.0"),
            "description": frontmatter["description"],
            "display_name": meta.get("display-name-zh", meta["name"]),
            "category": meta.get("primary-output", "creative"),
            "styles": meta.get("tags", []),
            "scenes": [],
            "use_when": frontmatter["description"],
            "guidance": [],
            "pitfalls": meta.get("exclude-intents", []),
            "example_cases": [],
            "aliases": meta.get("aliases", []),
            "tags": meta.get("tags", []),
            "capabilities": meta.get("capabilities", []),
            "release_tier": meta.get("release-tier", "experimental"),
            "record_type": "skill",
        })
        runtime[meta["name"]] = {
            "source": meta.get("source", "codex-flow"),
            "version": meta.get("version", "1.0.0"),
            "package_hash": skill_package.package_sha256(root),
            "entry": (root / "SKILL.md").resolve().as_posix(),
            "references": reference_routes(meta),
            "intermediate_outputs": meta.get("intermediate-outputs", []),
            "workflow_profile": meta.get("workflow-profile"),
            "interaction_profile": meta.get("interaction-profile"),
            "primary_output": meta.get("primary-output"),
            "exclude_intents": meta.get("exclude-intents", []),
        }
    return records, rejected, runtime


def reference_routes(meta: dict) -> dict:
    references = meta.get("references") or {}
    if not isinstance(references, dict):
        return {}
    result = {}
    for name, value in references.items():
        if isinstance(value, dict) and value.get("path"):
            result[name] = {
                "path": value["path"],
                "load_at": value.get("load-at", []),
            }
    return result


def build(skills_root: Path, output: Path, *, include_community: bool = False) -> dict:
    records, rejected, runtime = discover(skills_root)
    community_records = community_archetypes() if include_community else []
    for record in community_records:
        runtime[record["skill_id"]] = {
            "source": record["source"],
            "version": record.get("version"),
            "template_id": record.get("template_id"),
            "corpus": "awesome-gpt-image-2",
            "case_ids": record.get("example_cases", []),
        }
    all_records = records + community_records
    registry = {
        "schema": "codex-flow-registry/v2",
        "indexed": len(all_records),
        "skills": all_records,
        "runtime": runtime,
        "rejected": rejected,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return {"indexed": len(all_records), "community_archetypes": len(community_records), "rejected": rejected, "registry": output.resolve().as_posix()}


def lookup(query: str, registry_path: Path, limit: int) -> dict:
    if not registry_path.is_file():
        raise ValueError("registry is missing; run build first")
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    query_folded = query.casefold()
    candidates = []
    for skill in registry.get("skills", []):
        negative_text = " ".join(skill.get("pitfalls", [])).casefold()
        if query_folded and query_folded in negative_text:
            continue
        haystack = " ".join([
            skill.get("skill_id", ""),
            skill.get("description", ""),
            " ".join(skill.get("aliases", [])),
            " ".join(skill.get("tags", [])),
            " ".join(skill.get("capabilities", [])),
        ]).casefold()
        score = 0
        if query_folded in haystack:
            score += 50
        score += sum(3 for token in query_folded.split() if token and token in haystack)
        if score > 0:
            candidates.append({"skill_id": skill["skill_id"], "description": skill["description"], "score": score})
    candidates.sort(key=lambda item: (-item["score"], item["skill_id"]))
    return {"query": query, "candidates": candidates[:limit]}


def resolve(skill_id: str, registry_path: Path) -> dict:
    """Resolve a compact Skill Record to its executable runtime descriptor."""
    if not registry_path.is_file():
        raise ValueError("registry is missing; run build first")
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    record = next((item for item in registry.get("skills", []) if item.get("skill_id") == skill_id), None)
    if record is None:
        raise ValueError(f"skill is not registered: {skill_id}")
    runtime = registry.get("runtime", {}).get(skill_id)
    if runtime is None:
        raise ValueError(f"skill runtime is missing: {skill_id}")
    result = {"record": record, "runtime": runtime}
    entry = runtime.get("entry")
    if entry:
        result["available"] = Path(entry).is_file()
    else:
        result["available"] = True
    return result


def route(query: str, registry_path: Path, capability: str = "image.generate", limit: int = 3) -> dict:
    """Return one fast-path decision without loading skill bodies or references."""
    if not registry_path.is_file():
        raise ValueError("registry is missing; run build first")
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    query_folded = query.casefold().strip()
    candidates = []
    for skill in registry.get("skills", []):
        if capability not in skill.get("capabilities", []):
            continue
        if skill.get("skill_id") == "generic-image":
            continue
        excluded = [str(value).casefold() for value in skill.get("pitfalls", [])]
        if any(value and value in query_folded for value in excluded):
            continue
        score = route_score(query_folded, skill)
        if score:
            candidates.append({
                "skill_id": skill["skill_id"],
                "display_name": skill.get("display_name", skill["skill_id"]),
                "description": skill["description"],
                "source": skill.get("source", "codex-flow"),
                "record_type": skill.get("record_type", "skill"),
                "template_id": skill.get("template_id"),
                "score": score,
            })
    candidates.sort(key=lambda item: (-item["score"], item["skill_id"]))
    best = candidates[0] if candidates else None
    if best and best["score"] >= 60:
        decision = {
            "mode": "specialized_skill",
            "skill_id": best["skill_id"],
            "confidence": "high",
            "score": best["score"],
            "source": best.get("source"),
            "template_id": best.get("template_id"),
        }
    else:
        decision = {
            "mode": "generic_image",
            "skill_id": "generic-image",
            "confidence": "fallback",
            "style_library": "recommended" if should_consult_style_library(query_folded) else "not_needed",
            "case_corpus": "recommended" if should_consult_style_library(query_folded) else "not_needed",
        }
    return {"query": query, "capability": capability, "decision": decision, "candidates": candidates[:limit]}


def route_score(query: str, skill: dict) -> int:
    if not query:
        return 0
    score = 0
    weighted_fields = (
        (skill.get("skill_id", ""), 70),
        (skill.get("display_name", ""), 80),
        (skill.get("aliases", []), 80),
        (skill.get("tags", []), 60),
    )
    for values, weight in weighted_fields:
        if isinstance(values, str):
            values = [values]
        for value in values:
            phrase = str(value).casefold().strip()
            if len(phrase) >= 2 and phrase in query:
                score += weight
            else:
                phrase_tokens = [token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", phrase) if len(token) > 1]
                if phrase_tokens and any(token in query for token in phrase_tokens):
                    score += max(8, weight // 2)
    haystack = " ".join([
        skill.get("skill_id", ""),
        skill.get("display_name", ""),
        skill.get("description", ""),
        " ".join(skill.get("aliases", [])),
        " ".join(skill.get("tags", [])),
        " ".join(skill.get("capabilities", [])),
    ]).casefold()
    score += sum(4 for token in query.split() if len(token) > 1 and token in haystack)
    return score


def should_consult_style_library(query: str) -> bool:
    return any(term in query for term in IMAGE_STYLE_LIBRARY_TERMS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--private-root", type=Path, default=FLOW_ROOT / ".codex-flow-private")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("package", type=Path)
    review_parser = sub.add_parser("review")
    review_parser.add_argument("package", type=Path)
    review_parser.add_argument("--source-hash", required=True)
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("review", type=Path)
    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("package", type=Path)
    publish_parser.add_argument("--review", type=Path, required=True)
    publish_parser.add_argument("--approval", type=Path, required=True)
    sub.add_parser("build")
    lookup_parser = sub.add_parser("lookup")
    lookup_parser.add_argument("query")
    lookup_parser.add_argument("--limit", type=int, default=3)
    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("skill_id")
    route_parser = sub.add_parser("route")
    route_parser.add_argument("query")
    route_parser.add_argument("--capability", default="image.generate")
    route_parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            issues = skill_package.validate_package(args.package)
            print(json.dumps({"package": args.package.resolve().as_posix(), "issues": issues}, ensure_ascii=False, indent=2))
            return 1 if issues else 0
        if args.command in {"review", "approve", "publish"}:
            import approval
            if args.command == "review":
                result = approval.create_review(args.package, args.private_root / "reviews", args.source_hash)
            elif args.command == "approve":
                result = approval.approve_review(json.loads(args.review.read_text(encoding="utf-8-sig")), args.private_root / "approvals")
            else:
                result = approval.publish(args.package, args.skills_root, args.registry, args.private_root / "releases", args.review, args.approval)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "build":
            result = build(args.skills_root, args.registry, include_community=True)
        elif args.command == "lookup":
            result = lookup(args.query, args.registry, args.limit)
        elif args.command == "resolve":
            result = resolve(args.skill_id, args.registry)
        else:
            result = route(args.query, args.registry, args.capability, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
