from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


FLOW_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FLOW_ROOT.parents[1]
DEFAULT_MIGRATION_REPORT = FLOW_ROOT / ".codex-flow-private" / "migration" / "legacy-migration-report.json"
DOCUMENTED_MIGRATION_REPORT = REPO_ROOT / "docs" / "CODEX_FLOW_MIGRATION_REPORT.md"
LEGACY_EXECUTABLE_PATTERNS = [
    "video-skill-router",
    "image-skill-router",
    "codex-cs-skill-curator",
    "image-skill-curator",
    "project-pipeline",
    "material-collection",
    "skill-registry",
    "contract.json",
    "routing.json",
    "intake-report.json",
    "intake-receipt.json",
    "dt-request.json",
]
DEFAULT_SCAN_DIRS = ["AGENTS.md", "README.md", "config", "docs", "scripts", "packages/Codex_Flow"]
ALLOWED_AUDIT_FILES = {
    "docs/CODEX_FLOW_MIGRATION_REPORT.md",
    "docs/CODEX_FLOW_PHASE0_INVENTORY.md",
    "docs/CODEX_FLOW_CUTOVER.md",
    "packages/Codex_Flow/platform/cutover_check.py",
    "scripts/maintenance/verify-deployment.ps1",
    "scripts/codex/remove-legacy-global-skills.ps1",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(report_path: Path, scan_root: Path = REPO_ROOT) -> dict:
    issues: list[dict] = []
    if not report_path.is_file():
        if not DOCUMENTED_MIGRATION_REPORT.is_file():
            issues.append({"code": "MISSING_MIGRATION_REPORT", "path": report_path.resolve().as_posix()})
        report = {}
    else:
        report = read_json(report_path)
        for item in report.get("blocked", []):
            issues.append({"code": "BLOCKED_SKILL", "skill_id": item.get("skill_id"), "reason": item.get("reason")})
    for finding in scan_residuals(scan_root):
        issues.append({"code": "RESIDUAL_LEGACY_REFERENCE", **finding})
    return {"ready": not issues, "issues": issues}


def scan_residuals(scan_root: Path) -> list[dict]:
    findings = []
    pattern = re.compile("|".join(re.escape(item) for item in LEGACY_EXECUTABLE_PATTERNS), re.IGNORECASE)
    for relative in DEFAULT_SCAN_DIRS:
        path = scan_root / relative
        if not path.exists():
            continue
        files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
        for file_path in files:
            if any(part in {".git", ".codex-flow-private", "__pycache__"} for part in file_path.parts):
                continue
            relative_path = file_path.relative_to(scan_root).as_posix()
            if relative_path in ALLOWED_AUDIT_FILES:
                continue
            try:
                text = file_path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line) and "CODEX_FLOW_CUTOVER" not in file_path.name:
                    findings.append({"path": relative_path, "line": line_number})
                    break
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_MIGRATION_REPORT)
    parser.add_argument("--scan-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    result = check(args.report, args.scan_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
