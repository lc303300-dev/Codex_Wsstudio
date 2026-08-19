from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


FLOW_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS = FLOW_ROOT / "business-skills"
DEFAULT_REGISTRY = FLOW_ROOT / ".codex-flow-private" / "compiled" / "registry.json"


def load_skill_package_module():
    path = Path(__file__).with_name("skill_package.py")
    spec = importlib.util.spec_from_file_location("codex_flow_platform_skill_package", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_package = load_skill_package_module()


def discover(skills_root: Path) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    rejected: list[dict] = []
    if not skills_root.exists():
        return records, rejected
    for root in sorted(item for item in skills_root.iterdir() if item.is_dir()):
        issues = skill_package.validate_package(root)
        if issues:
            rejected.append({"skill_id": root.name, "issues": issues})
            continue
        frontmatter, _ = skill_package.parse_frontmatter(root / "SKILL.md")
        meta = skill_package.parse_yaml_text(root / "meta.yaml")
        records.append({
            "skill_id": meta["name"],
            "description": frontmatter["description"],
            "aliases": meta.get("aliases", []),
            "exclude_intents": meta.get("exclude-intents", []),
            "tags": meta.get("tags", []),
            "primary_output": meta.get("primary-output"),
            "intermediate_outputs": meta.get("intermediate-outputs", []),
            "workflow_profile": meta.get("workflow-profile"),
            "interaction_profile": meta.get("interaction-profile"),
            "capabilities": meta.get("capabilities", []),
            "release_tier": meta.get("release-tier", "experimental"),
            "package_hash": skill_package.package_sha256(root),
            "entry": (root / "SKILL.md").resolve().as_posix(),
            "references": reference_routes(meta),
        })
    return records, rejected


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


def build(skills_root: Path, output: Path) -> dict:
    records, rejected = discover(skills_root)
    registry = {
        "schema": "codex-flow-registry/v1",
        "indexed": len(records),
        "skills": records,
        "rejected": rejected,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return {"indexed": len(records), "rejected": rejected, "registry": output.resolve().as_posix()}


def lookup(query: str, registry_path: Path, limit: int) -> dict:
    if not registry_path.is_file():
        raise ValueError("registry is missing; run build first")
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    query_folded = query.casefold()
    candidates = []
    for skill in registry.get("skills", []):
        negative_text = " ".join(skill.get("exclude_intents", [])).casefold()
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
        result = build(args.skills_root, args.registry) if args.command == "build" else lookup(args.query, args.registry, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
