from __future__ import annotations

import argparse
import json
from pathlib import Path

from skill_package import VALIDATOR_VERSION, package_sha256, validate_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Codex_CS video business Skill package.")
    parser.add_argument("package", type=Path)
    parser.add_argument("--published", action="store_true", help="Require and verify intake-receipt.json.")
    args = parser.parse_args()

    root = args.package.resolve()
    issues = validate_package(root, require_receipt=args.published)
    payload = {
        "status": "valid" if not issues else "invalid",
        "validator_version": VALIDATOR_VERSION,
        "package": str(root),
        "package_sha256": package_sha256(root) if root.is_dir() else None,
        "issues": [issue.to_dict() for issue in issues],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

