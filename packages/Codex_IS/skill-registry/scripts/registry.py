from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


IS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(IS_ROOT / "shared"))
from package_integrity import package_sha256, validate_receipt  # noqa: E402
CURATOR_ROOT = IS_ROOT / "image-skill-curator" / "scripts"
if str(CURATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(CURATOR_ROOT))
from skill_package import validate_package  # noqa: E402

DEFAULT_SKILLS = IS_ROOT / "business-skills"
DEFAULT_DB = IS_ROOT / ".codex-is-private" / "registry" / "skills.sqlite3"
SEARCH_FIELDS = ("display_name", "aliases", "user_intents", "subjects", "styles", "narrative_patterns")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def discover(skills_root: Path) -> tuple[list[dict], list[dict]]:
    records, rejected = [], []
    if not skills_root.exists():
        return records, rejected
    for root in sorted(item for item in skills_root.iterdir() if item.is_dir()):
        skill_id = root.name
        required = [root / "SKILL.md", root / "contract.json", root / "routing.json"]
        missing = [path.name for path in required if not path.is_file()]
        receipt, issues = validate_receipt(root, skill_id)
        package_issues = validate_package(root, require_report=True, require_receipt=True) if not missing else []
        if missing or issues or package_issues:
            rejected.append({"skill_id": skill_id, "issues": [*(f"MISSING_{name}" for name in missing), *issues, *package_issues]})
            continue
        contract, routing = read_json(root / "contract.json"), read_json(root / "routing.json")
        if contract.get("skill_id") != skill_id or routing.get("skill_id") != skill_id:
            rejected.append({"skill_id": skill_id, "issues": ["IDENTITY_MISMATCH"]})
            continue
        records.append({
            "skill_id": skill_id,
            "display_name": contract["display_name"],
            "description": contract["description"],
            "priority": int(routing.get("priority", 0)),
            "package_hash": package_sha256(root),
            "routing": routing,
            "contract": contract,
            "package_root": str(root.resolve()),
            "receipt": receipt,
        })
    return records, rejected


def build(skills_root: Path, db_path: Path) -> dict:
    records, rejected = discover(skills_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_suffix(".tmp.sqlite3")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    connection.execute("CREATE TABLE skills (skill_id TEXT PRIMARY KEY, display_name TEXT, description TEXT, priority INTEGER, package_hash TEXT, package_root TEXT, routing_json TEXT, contract_json TEXT)")
    for item in records:
        connection.execute("INSERT INTO skills VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
            item["skill_id"], item["display_name"], item["description"], item["priority"], item["package_hash"], item["package_root"],
            json.dumps(item["routing"], ensure_ascii=False), json.dumps(item["contract"], ensure_ascii=False),
        ))
    connection.commit()
    connection.close()
    temporary.replace(db_path)
    return {"indexed": len(records), "rejected": rejected, "database": db_path.resolve().as_posix()}


def score(query: str, record: dict) -> int:
    query_folded = query.casefold().strip()
    routing = record["routing"]
    negatives = " ".join(routing.get("negative_intents", [])).casefold()
    if query_folded and query_folded in negatives:
        return -1000
    total = 0
    for field in SEARCH_FIELDS:
        value = record["display_name"] if field == "display_name" else routing.get(field, [])
        values = [value] if isinstance(value, str) else value
        for text in values:
            folded = text.casefold()
            if query_folded == folded:
                total += 100
            elif query_folded in folded or folded in query_folded:
                total += 30
            else:
                total += sum(2 for token in query_folded.replace("3×3", "九宫格").split() if token and token in folded)
    return total + record["priority"]


def lookup(query: str, db_path: Path, limit: int) -> dict:
    if not db_path.is_file():
        raise ValueError("registry is missing; run build first")
    connection = sqlite3.connect(db_path)
    rows = connection.execute("SELECT skill_id, display_name, description, priority, package_hash, package_root, routing_json, contract_json FROM skills").fetchall()
    connection.close()
    candidates = []
    for row in rows:
        item = {"skill_id": row[0], "display_name": row[1], "description": row[2], "priority": row[3], "package_hash": row[4], "package_root": row[5], "routing": json.loads(row[6]), "contract": json.loads(row[7])}
        current, issues = validate_receipt(Path(item["package_root"]), item["skill_id"])
        if issues or current is None or current["package_sha256"] != item["package_hash"]:
            raise ValueError(f"registry is stale for {item['skill_id']}; rebuild it")
        item_score = score(query, item)
        if item_score > 0:
            candidates.append({"skill_id": item["skill_id"], "display_name": item["display_name"], "description": item["description"], "score": item_score, "reference_slots": [slot["id"] for slot in item["contract"]["references"]]})
    candidates.sort(key=lambda item: (-item["score"], item["skill_id"]))
    return {"query": query, "candidates": candidates[:limit]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    lookup_parser = sub.add_parser("lookup")
    lookup_parser.add_argument("query")
    lookup_parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        result = build(args.skills_root, args.db) if args.command == "build" else lookup(args.query, args.db, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
