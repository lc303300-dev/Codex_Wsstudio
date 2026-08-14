from __future__ import annotations

import argparse
import json
from pathlib import Path

from skill_package import load_contract, validate_package


def discover(library_root: Path) -> tuple[list[dict], list[dict]]:
    root = library_root.resolve()
    if not root.is_dir():
        return [], [{"path": str(root), "issues": [{"code": "LIBRARY_NOT_FOUND", "message": "Skill library directory does not exist"}]}]
    published: list[dict] = []
    rejected: list[dict] = []
    for package in sorted(path for path in root.iterdir() if path.is_dir()):
        issues = validate_package(package, require_receipt=True)
        if issues:
            rejected.append({"path": str(package), "issues": [issue.to_dict() for issue in issues]})
            continue
        contract = load_contract(package)
        published.append({
            "skill_id": contract["skill_id"],
            "display_name": contract["display_name"],
            "description": contract["description"],
            "path": str(package),
        })
    return published, rejected


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover only valid, published Codex_CS video business Skills.")
    parser.add_argument("library_root", type=Path)
    parser.add_argument("--strict", action="store_true", help="Return a failure exit code when invalid directories are present.")
    args = parser.parse_args()
    published, rejected = discover(args.library_root)
    print(json.dumps({"published": published, "rejected": rejected}, ensure_ascii=False, indent=2))
    return 1 if args.strict and rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())

