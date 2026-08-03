import csv
import argparse
import json
import random
import sys
from pathlib import Path

csv.field_size_limit(10_000_000)

CSV_PATH = Path(__file__).parent.parent / "references" / "seedance-prompts.csv"


def load_rows(csv_path):
    rows = []
    try:
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        print(f"Error: CSV not found at {csv_path}", file=sys.stderr)
        sys.exit(1)
    return rows


def parse_author(raw):
    try:
        data = json.loads(raw) if raw else {}
        return data.get("name", ""), data.get("link", "")
    except Exception:
        return raw, ""


def score_row(row, keywords):
    title = row["title"].lower()
    desc = (row.get("description") or "").lower()
    content = row["content"].lower()
    score = 0
    for kw in keywords:
        kw = kw.lower()
        score += title.count(kw) * 3
        score += desc.count(kw) * 2
        score += content.count(kw) * 1
    return score


def apply_filters(rows, args):
    result = []
    for row in rows:
        length = len(row["content"])
        if args.min_length and length < args.min_length:
            continue
        if args.max_length and length > args.max_length:
            continue
        if args.author:
            name, _ = parse_author(row.get("author", ""))
            if args.author.lower() not in name.lower():
                continue
        result.append(row)
    return result


def format_human(rank, row):
    name, link = parse_author(row.get("author", ""))
    length = len(row["content"])
    title = row["title"]
    preview = row["content"].replace("\n", " ").replace("\r", " ")
    if len(preview) > 300:
        preview = preview[:300] + "..."
    author_line = f"    by {name}"
    if link:
        author_line += f" — {link}"
    lines = [
        f"[{rank}] id={row['id']} | len={length} | \"{title}\"",
        author_line,
        f"    {preview}",
    ]
    return "\n".join(lines)


def format_json_obj(row):
    name, _ = parse_author(row.get("author", ""))
    preview = row["content"].replace("\n", " ").replace("\r", " ")[:300]
    return {
        "id": row["id"],
        "title": row["title"],
        "length": len(row["content"]),
        "author": name,
        "sourceLink": row.get("sourceLink", ""),
        "content_preview": preview,
    }


def main():
    parser = argparse.ArgumentParser(description="Search Seedance 2.0 prompt corpus")
    parser.add_argument("query", nargs="?", help="Keywords to search for")
    parser.add_argument("--top", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--author", type=str, default=None, help="Filter by author name")
    parser.add_argument("--min-length", type=int, default=None, dest="min_length")
    parser.add_argument("--max-length", type=int, default=None, dest="max_length")
    parser.add_argument("--random", type=int, default=None, metavar="N", dest="random_n")
    parser.add_argument("--json", action="store_true", dest="json_out")
    args = parser.parse_args()

    rows = load_rows(CSV_PATH)
    filtered = apply_filters(rows, args)

    if args.random_n is not None:
        n = args.random_n
        if n > len(filtered):
            print(f"Warning: requested {n} but only {len(filtered)} rows after filters. Returning all.", file=sys.stderr)
            results = filtered
        else:
            results = random.sample(filtered, n)
    elif args.query:
        keywords = args.query.split()
        scored = [(score_row(row, keywords), len(row["content"]), row) for row in filtered]
        scored = [(s, l, r) for s, l, r in scored if s > 0]
        scored.sort(key=lambda x: (-x[0], x[1]))
        results = [r for _, _, r in scored[: args.top]]
    elif args.author:
        results = filtered[: args.top]
    else:
        parser.print_help()
        sys.exit(0)

    if not results:
        if args.json_out:
            print("[]")
        else:
            print("No results found.")
        return

    if args.json_out:
        print(json.dumps([format_json_obj(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for i, row in enumerate(results, 1):
            print(format_human(i, row))
            if i < len(results):
                print()


if __name__ == "__main__":
    main()
