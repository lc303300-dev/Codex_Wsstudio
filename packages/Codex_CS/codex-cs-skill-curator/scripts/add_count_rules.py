from __future__ import annotations

import argparse
import json
from pathlib import Path

from count_rules import add_missing_count_rules


def main() -> int:
    parser = argparse.ArgumentParser(description="Add auditable default pacing rules to reference slots that lack count_rule.")
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    contract_path = args.package.resolve() / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    updated, additions = add_missing_count_rules(contract)
    contract_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "contract": str(contract_path), "added_rules": additions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
