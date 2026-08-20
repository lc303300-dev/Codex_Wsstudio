from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path


FLOW_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = FLOW_ROOT / ".codex-flow-private" / "corpora" / "awesome-gpt-image-2"
DEFAULT_CATALOG = CORPUS_ROOT / "style-library.json"
DEFAULT_CASES = CORPUS_ROOT / "gallery-cases.json"
DEFAULT_MANIFEST = CORPUS_ROOT / "manifest.json"
SOURCE_URL = "https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main/data/style-library.json"
GALLERY_URLS = (
    "https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main/docs/gallery-part-1.md",
    "https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main/docs/gallery-part-2.md",
)
SOURCE_REPOSITORY = "https://github.com/freestylefly/awesome-gpt-image-2"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-Flow"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_cases(markdown: str, source_url: str) -> list[dict]:
    pattern = re.compile(
        r'<a name="case-(?P<id>\d+)"></a>\s*\n\s*### 例 \d+：(?P<title>[^\n]+).*?'
        r'\*\*提示词：\*\*\s*\n\s*```text\s*\n(?P<prompt>.*?)\n```',
        re.DOTALL,
    )
    return [{
        "case_id": int(match.group("id")),
        "title": match.group("title").strip(),
        "prompt": match.group("prompt").strip(),
        "source": f"{source_url}#case-{match.group('id')}",
    } for match in pattern.finditer(markdown)]


def sync(destination: Path = DEFAULT_CATALOG) -> dict:
    payload = json.loads(fetch(SOURCE_URL))
    if not isinstance(payload.get("templates"), list):
        raise ValueError("style library source has no templates")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    cases = []
    for gallery_url in GALLERY_URLS:
        cases.extend(parse_cases(fetch(gallery_url), gallery_url))
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("gallery has duplicate case IDs")
    if len(cases) < 500:
        raise ValueError(f"gallery corpus is unexpectedly small: {len(cases)} cases")
    cases_path = destination.with_name(DEFAULT_CASES.name)
    cases_path.write_text(json.dumps({"repository": SOURCE_REPOSITORY, "cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    highest_case_id = max(case_ids, default=0)
    manifest = {
        "schema": "codex-flow-community-image-library/v1",
        "repository": SOURCE_REPOSITORY,
        "template_source": SOURCE_URL,
        "gallery_sources": list(GALLERY_URLS),
        "templates": len(payload["templates"]),
        "cases": len(cases),
        "highest_case_id": highest_case_id,
        "missing_case_ids": [case_id for case_id in range(1, highest_case_id + 1) if case_id not in set(case_ids)],
    }
    manifest_path = destination.with_name(DEFAULT_MANIFEST.name)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"catalog": destination.resolve().as_posix(), "cases": cases_path.resolve().as_posix(), **manifest}


def lookup(query: str, catalog: Path = DEFAULT_CATALOG, limit: int = 3) -> dict:
    if not catalog.is_file():
        raise ValueError("style library is missing; run style-library sync first")
    payload = json.loads(catalog.read_text(encoding="utf-8-sig"))
    query_folded = query.casefold()
    matches = []
    for template in payload.get("templates", []):
        score = score_template(query_folded, template)
        if score:
            matches.append({
                "id": template["id"],
                "title": template.get("title", {}),
                "description": template.get("description", {}),
                "guidance": template.get("guidance", {}),
                "pitfalls": template.get("pitfalls", {}),
                "score": score,
            })
    matches.sort(key=lambda item: (-item["score"], item["id"]))
    return {"query": query, "source": payload.get("repository", SOURCE_URL), "candidates": matches[:limit]}


def archetypes(catalog: Path = DEFAULT_CATALOG) -> list[dict]:
    if not catalog.is_file():
        return []
    payload = json.loads(catalog.read_text(encoding="utf-8-sig"))
    return [{
        "skill_id": f"awesome-gpt-image-2/{template['id']}",
        "source": SOURCE_REPOSITORY,
        "version": payload.get("version", "community-main"),
        "display_name": (template.get("title") or {}).get("zh", template["id"]),
        "description": (template.get("description") or {}).get("zh", ""),
        "category": template.get("category"),
        "styles": template.get("styles", []),
        "scenes": template.get("scenes", []),
        "tags": template.get("tags", []),
        "aliases": [template["id"], *template.get("styles", []), *template.get("scenes", []), *template.get("tags", [])],
        "use_when": template.get("useWhen", {}).get("zh", ""),
        "guidance": template.get("guidance", {}).get("zh", []),
        "pitfalls": template.get("pitfalls", {}).get("zh", []),
        "example_cases": template.get("exampleCases", []),
        "capabilities": ["image.generate"],
        "release_tier": "community",
        "record_type": "skill",
        "template_id": template["id"],
    } for template in payload.get("templates", [])]


def case_lookup(query: str, cases_path: Path = DEFAULT_CASES, limit: int = 5) -> dict:
    if not cases_path.is_file():
        raise ValueError("gallery corpus is missing; run style-library sync first")
    payload = json.loads(cases_path.read_text(encoding="utf-8-sig"))
    matches = []
    for case in payload.get("cases", []):
        score = score_text(query, f"{case.get('title', '')}\n{case.get('prompt', '')}")
        if score:
            matches.append({
                "case_id": case["case_id"],
                "title": case["title"],
                "source": case["source"],
                "score": score,
                "prompt_excerpt": case["prompt"][:240],
            })
    matches.sort(key=lambda item: (-item["score"], item["case_id"]))
    return {"query": query, "source": payload.get("repository", SOURCE_REPOSITORY), "candidates": matches[:limit]}


def score_template(query: str, template: dict) -> int:
    fields = [template.get("id", ""), template.get("category", "")]
    for name in ("title", "description", "useWhen"):
        fields.extend((template.get(name) or {}).values())
    fields.extend(template.get("styles", []))
    fields.extend(template.get("scenes", []))
    fields.extend(template.get("tags", []))
    score = 0
    for field in fields:
        phrase = str(field).casefold().strip()
        if len(phrase) >= 2 and phrase in query:
            score += 30
        for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", phrase):
            if len(token) > 1 and token in query:
                score += 4
    return score


def score_text(query: str, value: str) -> int:
    query = re.sub(r"\s+", "", query.casefold())
    value = re.sub(r"\s+", "", value.casefold())
    if not query or not value:
        return 0
    score = 40 if query in value else 0
    grams = {query[index:index + 2] for index in range(len(query) - 1)}
    score += sum(5 for gram in grams if gram in value)
    return score


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync")
    lookup_parser = commands.add_parser("lookup")
    lookup_parser.add_argument("query")
    lookup_parser.add_argument("--limit", type=int, default=3)
    cases_parser = commands.add_parser("cases")
    cases_parser.add_argument("query")
    cases_parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        if args.command == "sync":
            result = sync(args.catalog)
        elif args.command == "lookup":
            result = lookup(args.query, args.catalog, args.limit)
        else:
            result = case_lookup(args.query, args.catalog.with_name(DEFAULT_CASES.name), args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
