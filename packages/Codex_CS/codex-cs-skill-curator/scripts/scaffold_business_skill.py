from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = SCRIPT_ROOT.parent / "assets" / "business-skill-template"
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def render_tree(source: Path, destination: Path, replacements: dict[str, str]) -> None:
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    shutil.copytree(source, destination)
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for key, value in replacements.items():
            text = text.replace("{{" + key + "}}", value)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a staging Codex_CS video business Skill package.")
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--short-description")
    parser.add_argument("--output", required=True, type=Path, help="Staging root; the skill-id directory is created below it.")
    args = parser.parse_args()

    if not SKILL_ID_PATTERN.fullmatch(args.skill_id) or len(args.skill_id) > 64:
        raise SystemExit("skill-id must be lowercase hyphen-case and at most 64 characters")
    if len(args.description.strip()) < 20:
        raise SystemExit("description must contain at least 20 characters")
    short = (args.short_description or f"根据已确认素材与专业规则生成{args.display_name}视频提示词").strip()
    if not 25 <= len(short) <= 64:
        raise SystemExit("short-description must contain 25-64 characters")

    destination = args.output.resolve() / args.skill_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    render_tree(
        TEMPLATE_ROOT,
        destination,
        {
            "skill_id": args.skill_id,
            "display_name": args.display_name.strip(),
            "description": args.description.strip(),
            "short_description": short,
        },
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

