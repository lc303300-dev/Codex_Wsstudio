#!/usr/bin/env python3
"""Dependency-free smoke tests for the public skill repository."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "build-seedance2-prompts"


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def check_required_files() -> None:
    required = (
        ROOT / "README.md",
        ROOT / "README.ja.md",
        ROOT / "LICENSE",
        SKILL / "SKILL.md",
        SKILL / "agents" / "openai.yaml",
        SKILL / "references" / "official-rules.md",
        SKILL / "references" / "prompt-patterns.md",
        SKILL / "references" / "platform-adapters.md",
        SKILL / "references" / "evidence-ledger.md",
        SKILL / "references" / "asset-manifest.schema.json",
        SKILL / "scripts" / "validate_prompt.py",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")


def check_skill_metadata() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not frontmatter:
        fail("SKILL.md has no valid YAML frontmatter block")
    block = frontmatter.group(1)
    if not re.search(r"(?m)^name:\s*build-seedance2-prompts\s*$", block):
        fail("SKILL.md name does not match its directory")
    description = re.search(r"(?m)^description:\s*(.+)$", block)
    if not description or len(description.group(1).strip()) < 80:
        fail("SKILL.md description is missing or too short for reliable triggering")
    if len(text.splitlines()) > 500:
        fail("SKILL.md exceeds the 500-line progressive-disclosure budget")

    interface = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for field in ("display_name:", "short_description:", "default_prompt:"):
        if field not in interface:
            fail(f"agents/openai.yaml is missing {field}")
    if "$build-seedance2-prompts" not in interface:
        fail("default_prompt does not explicitly invoke the skill")


def check_json_schema() -> None:
    path = SKILL / "references" / "asset-manifest.schema.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("asset manifest does not declare JSON Schema 2020-12")
    if data.get("title") != "Seedance prompt asset manifest":
        fail("asset manifest title changed unexpectedly")


def check_relative_links() -> None:
    pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for markdown in (ROOT / "README.md", ROOT / "README.ja.md", ROOT / "CONTRIBUTING.md"):
        text = markdown.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            target = target.strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (markdown.parent / file_part).resolve().exists():
                fail(f"broken relative link in {markdown.name}: {target}")


def run_validator() -> None:
    validator = SKILL / "scripts" / "validate_prompt.py"
    good = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--text",
            (
                "Use @Image 1 (Hana) for identity only and @Video 1 (camera reference) "
                "for the slow dolly path only; do not transfer its person, palette, or audio. "
                "Hana walks forward in one continuous shot with stable identity and no subtitles."
            ),
            "--images",
            "1",
            "--videos",
            "1",
            "--audios",
            "0",
            "--duration",
            "8",
            "--mode",
            "multimodal",
            "--surface",
            "dreamina",
            "--strict",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if good.returncode != 0 or "PASS:" not in good.stdout:
        fail(f"known-good prompt did not pass:\n{good.stdout}{good.stderr}")

    bad = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--text",
            "A simple clip. seed=123",
            "--duration",
            "31",
            "--mode",
            "text",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if bad.returncode == 0 or not {"O003", "O201"}.issubset(set(re.findall(r"O\d{3}", bad.stdout))):
        fail(f"known-bad prompt did not trigger expected errors:\n{bad.stdout}{bad.stderr}")


def check_repository_hygiene() -> None:
    unwanted = [
        path.relative_to(ROOT)
        for path in ROOT.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
    ]
    if unwanted:
        fail(f"generated Python artifacts are present: {', '.join(map(str, unwanted))}")


def main() -> int:
    check_required_files()
    check_skill_metadata()
    check_json_schema()
    check_relative_links()
    run_validator()
    check_repository_hygiene()
    print("PASS: repository structure, metadata, links, schema, and prompt validator are healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
