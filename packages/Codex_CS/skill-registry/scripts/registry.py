from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 1
ROUTING_FIELDS = ("aliases", "user_intents", "subjects", "styles", "narrative_patterns", "negative_intents")
DEFAULT_DB = Path(__file__).resolve().parents[2] / ".codex-cs-private" / "registry" / "video-skills.db"
DEFAULT_LIBRARY = Path(__file__).resolve().parents[2] / "business-skills"
TAXONOMY = Path(__file__).resolve().parents[1] / "config" / "taxonomy.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def package_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "intake-receipt.json")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_published_package(root: Path) -> tuple[dict | None, list[str]]:
    issues: list[str] = []
    required = ("SKILL.md", "contract.json", "intake-receipt.json")
    for name in required:
        if not (root / name).is_file():
            issues.append(f"missing {name}")
    if issues:
        return None, issues
    try:
        contract = read_json(root / "contract.json")
        receipt = read_json(root / "intake-receipt.json")
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"invalid JSON: {exc}"]
    skill_id = contract.get("skill_id")
    if not isinstance(skill_id, str) or root.name != skill_id:
        issues.append("skill_id does not match directory")
    if receipt.get("status") != "published" or receipt.get("approved_by") != "user":
        issues.append("receipt is not user-approved published state")
    if receipt.get("skill_id") != skill_id:
        issues.append("receipt skill_id mismatch")
    actual_hash = package_sha256(root)
    if receipt.get("package_sha256") != actual_hash:
        issues.append("stale publication receipt")
    for field in ("display_name", "description", "references"):
        if field not in contract:
            issues.append(f"contract missing {field}")
    return (contract if not issues else None), issues


def normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())


def unique_strings(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip().casefold() not in seen:
            result.append(value.strip())
            seen.add(value.strip().casefold())
    return result


def load_taxonomy() -> dict:
    return read_json(TAXONOMY)


def routing_for(root: Path, contract: dict, taxonomy: dict) -> dict:
    routing_path = root / "routing.json"
    if routing_path.is_file():
        routing = read_json(routing_path)
        if routing.get("schema_version") != 1 or routing.get("skill_id") != contract["skill_id"]:
            raise ValueError("routing.json identity/schema mismatch")
        unknown = set(routing) - {"schema_version", "skill_id", "priority", *ROUTING_FIELDS}
        if unknown:
            raise ValueError(f"routing.json unknown fields: {sorted(unknown)}")
        for field in ROUTING_FIELDS:
            if field in routing and (not isinstance(routing[field], list) or not all(isinstance(x, str) for x in routing[field])):
                raise ValueError(f"routing.json {field} must be a string array")
        priority = routing.get("priority", 50)
        if not isinstance(priority, int) or not 0 <= priority <= 100:
            raise ValueError("routing.json priority must be 0..100")
        return {field: unique_strings(routing.get(field, [])) for field in ROUTING_FIELDS} | {"priority": priority}

    source = f"{contract.get('display_name', '')} {contract.get('description', '')}"
    derived: dict[str, list[str]] = {field: [] for field in ROUTING_FIELDS}
    derived["aliases"] = unique_strings([contract.get("display_name"), contract.get("skill_id")])
    category_map = {
        "intents": "user_intents", "subjects": "subjects", "styles": "styles",
        "narrative_patterns": "narrative_patterns",
    }
    for category, field in category_map.items():
        derived[field] = [term for term in taxonomy["categories"][category] if term.casefold() in source.casefold()]
    return derived | {"priority": 50}


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS registry_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS skills(
          skill_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, description TEXT NOT NULL,
          package_path TEXT NOT NULL, package_hash TEXT NOT NULL, priority INTEGER NOT NULL,
          routing_json TEXT NOT NULL, material_summary_json TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts USING fts5(
          skill_id UNINDEXED, display_name, description, aliases, intentions, subjects, styles, patterns,
          tokenize='trigram'
        );
    """)
    connection.execute("INSERT OR REPLACE INTO registry_meta VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))


def material_summary(contract: dict) -> list[dict]:
    return [
        {key: item.get(key) for key in ("id", "media_type", "description", "required", "min_count", "max_count", "ordered")}
        for item in contract.get("references", []) if isinstance(item, dict)
    ]


def upsert(connection: sqlite3.Connection, root: Path, contract: dict, routing: dict, package_hash: str) -> None:
    skill_id = contract["skill_id"]
    now = datetime.now(timezone.utc).isoformat()
    connection.execute("DELETE FROM skill_fts WHERE skill_id=?", (skill_id,))
    connection.execute(
        "INSERT OR REPLACE INTO skills VALUES(?,?,?,?,?,?,?,?,?)",
        (skill_id, contract["display_name"], contract["description"], str(root.resolve()), package_hash,
         routing["priority"], json.dumps(routing, ensure_ascii=False),
         json.dumps(material_summary(contract), ensure_ascii=False), now),
    )
    values = [" ".join(routing[field]) for field in ROUTING_FIELDS]
    connection.execute(
        "INSERT INTO skill_fts VALUES(?,?,?,?,?,?,?,?)",
        (skill_id, contract["display_name"], contract["description"], *values[:5]),
    )


def build(library: Path, database: Path, *, rebuild: bool = False) -> dict:
    database.parent.mkdir(parents=True, exist_ok=True)
    taxonomy = load_taxonomy()
    target = database
    temp_path: Path | None = None
    if rebuild:
        fd, raw = tempfile.mkstemp(prefix="registry-", suffix=".db", dir=database.parent)
        os.close(fd)
        temp_path = Path(raw)
        target = temp_path
    connection = connect(target)
    indexed: list[str] = []
    unchanged: list[str] = []
    rejected: list[dict] = []
    try:
        create_schema(connection)
        existing = {row["skill_id"]: row["package_hash"] for row in connection.execute("SELECT skill_id, package_hash FROM skills")}
        present: set[str] = set()
        for root in sorted(p for p in library.iterdir() if p.is_dir()) if library.is_dir() else []:
            contract, issues = validate_published_package(root)
            if issues:
                rejected.append({"path": str(root), "issues": issues})
                continue
            assert contract is not None
            skill_id = contract["skill_id"]
            present.add(skill_id)
            digest = package_sha256(root)
            if existing.get(skill_id) == digest:
                unchanged.append(skill_id)
                continue
            try:
                routing = routing_for(root, contract, taxonomy)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                rejected.append({"path": str(root), "issues": [str(exc)]})
                continue
            upsert(connection, root, contract, routing, digest)
            indexed.append(skill_id)
        removed = sorted(set(existing) - present)
        for skill_id in removed:
            connection.execute("DELETE FROM skills WHERE skill_id=?", (skill_id,))
            connection.execute("DELETE FROM skill_fts WHERE skill_id=?", (skill_id,))
        connection.execute("INSERT OR REPLACE INTO registry_meta VALUES('built_at', ?)", (datetime.now(timezone.utc).isoformat(),))
        connection.execute("INSERT OR REPLACE INTO registry_meta VALUES('library_root', ?)", (str(library.resolve()),))
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()
    if temp_path:
        os.replace(temp_path, database)
    return {"database": str(database), "indexed": indexed, "unchanged": unchanged, "removed": removed, "rejected": rejected}


def query_terms(query: str) -> list[str]:
    compact = normalize(query)
    grams = [compact[i:i + 3] for i in range(max(0, len(compact) - 2))]
    words = re.findall(r"[a-z0-9]{3,}", query.casefold())
    return unique_strings([*grams, *words])[:64]


def matched_terms(query: str, routing: dict, taxonomy: dict) -> tuple[list[str], list[str]]:
    query_norm = normalize(query)
    positive: list[str] = []
    negative: list[str] = []
    synonym_hits: set[str] = set()
    for canonical, forms in taxonomy.get("synonyms", {}).items():
        if any(normalize(form) in query_norm for form in forms):
            synonym_hits.add(canonical.casefold())
    for field in ROUTING_FIELDS:
        for term in routing.get(field, []):
            key = term.casefold()
            hit = normalize(term) in query_norm or key in synonym_hits
            if hit:
                (negative if field == "negative_intents" else positive).append(term)
    return unique_strings(positive), unique_strings(negative)


def lookup(database: Path, query: str, limit: int = 5) -> dict:
    connection = connect(database)
    taxonomy = load_taxonomy()
    try:
        terms = query_terms(query)
        rows: list[sqlite3.Row] = []
        if terms:
            expression = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
            rows = list(connection.execute(
                "SELECT s.*, bm25(skill_fts, 0, 8, 3, 6, 5, 5, 5) AS rank "
                "FROM skill_fts JOIN skills s ON s.skill_id=skill_fts.skill_id "
                "WHERE skill_fts MATCH ? ORDER BY rank LIMIT 50", (expression,)))
        query_norm = normalize(query)
        exact = list(connection.execute("SELECT *, -100.0 AS rank FROM skills WHERE lower(skill_id)=lower(?) OR display_name=?", (query.strip(), query.strip())))
        # trigram cannot index one- or two-character requests such as “IP”; at the
        # expected hundreds-of-Skills scale this bounded fallback remains cheap.
        if not rows and len(normalize(query)) < 3:
            rows = list(connection.execute("SELECT *, 0.0 AS rank FROM skills"))
        by_id = {row["skill_id"]: row for row in [*exact, *rows]}
        scored: list[dict] = []
        for row in by_id.values():
            routing = json.loads(row["routing_json"])
            aliases = routing.get("aliases", [])
            exact_alias = any(normalize(alias) == query_norm for alias in aliases)
            positive, negative = matched_terms(query, routing, taxonomy)
            if len(query_norm) < 3 and not exact_alias and not positive and row["skill_id"].casefold() != query.strip().casefold():
                continue
            rank = float(row["rank"])
            retrieval = min(35.0, max(0.0, -rank * 5.0))
            score = retrieval + len(positive) * 12.0 - len(negative) * 20.0 + row["priority"] * 0.1
            if exact_alias or row["skill_id"].casefold() == query.strip().casefold():
                score += 100.0
            reasons = (["名称或别名精确命中"] if exact_alias else []) + [f"意图命中：{term}" for term in positive]
            if not reasons:
                reasons = ["全文意图相似"]
            scored.append({
                "skill_id": row["skill_id"], "display_name": row["display_name"],
                "description": row["description"], "score": round(max(0.0, score), 2),
                "matched_reasons": reasons, "negative_hits": negative,
                "material_guidance": json.loads(row["material_summary_json"]),
                "path": row["package_path"],
            })
        scored.sort(key=lambda item: (-item["score"], item["skill_id"]))
        return {"query": query, "candidates": scored[:limit]}
    finally:
        connection.close()


def list_skills(database: Path) -> dict:
    connection = connect(database)
    try:
        rows = connection.execute("SELECT skill_id, display_name, description, package_path FROM skills ORDER BY skill_id")
        return {"skills": [dict(row) for row in rows]}
    finally:
        connection.close()


def validate_registry(database: Path, library: Path | None = None) -> dict:
    issues: list[str] = []
    if not database.is_file():
        return {"valid": False, "issues": ["database not found"]}
    try:
        connection = connect(database)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            issues.append(f"SQLite integrity: {integrity}")
        version = connection.execute("SELECT value FROM registry_meta WHERE key='schema_version'").fetchone()
        if not version or version[0] != str(SCHEMA_VERSION):
            issues.append("schema version mismatch")
        if library:
            indexed = {row["skill_id"]: row["package_hash"] for row in connection.execute("SELECT skill_id, package_hash FROM skills")}
            valid_ids: set[str] = set()
            for root in sorted(p for p in library.iterdir() if p.is_dir()) if library.is_dir() else []:
                contract, package_issues = validate_published_package(root)
                if package_issues:
                    continue
                assert contract is not None
                valid_ids.add(contract["skill_id"])
                if indexed.get(contract["skill_id"]) != package_sha256(root):
                    issues.append(f"stale or missing index: {contract['skill_id']}")
            for extra in sorted(set(indexed) - valid_ids):
                issues.append(f"index contains unavailable skill: {extra}")
        connection.close()
    except sqlite3.Error as exc:
        issues.append(f"SQLite error: {exc}")
    return {"valid": not issues, "issues": issues}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Codex_CS high-performance video Skill intent registry")
    sub = result.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build")
    build_cmd.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    build_cmd.add_argument("--database", type=Path, default=DEFAULT_DB)
    build_cmd.add_argument("--rebuild", action="store_true")
    lookup_cmd = sub.add_parser("lookup")
    lookup_cmd.add_argument("query")
    lookup_cmd.add_argument("--database", type=Path, default=DEFAULT_DB)
    lookup_cmd.add_argument("--limit", type=int, default=5)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--database", type=Path, default=DEFAULT_DB)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--database", type=Path, default=DEFAULT_DB)
    validate_cmd.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "build":
        output = build(args.library, args.database, rebuild=args.rebuild)
        code = 1 if output["rejected"] else 0
    elif args.command == "lookup":
        output, code = lookup(args.database, args.query, args.limit), 0
    elif args.command == "list":
        output, code = list_skills(args.database), 0
    else:
        output = validate_registry(args.database, args.library)
        code = 0 if output["valid"] else 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
