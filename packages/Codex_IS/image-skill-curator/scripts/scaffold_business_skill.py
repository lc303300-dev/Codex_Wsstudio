from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("skill_id"); parser.add_argument("--output",required=True,type=Path); parser.add_argument("--display-name")
    args=parser.parse_args(); target=args.output.resolve()/args.skill_id
    if target.exists(): raise SystemExit(f"Refusing to overwrite: {target}")
    shutil.copytree(ROOT/"assets"/"business-skill-template",target)
    display=args.display_name or "{{display_name}}"
    for path in target.rglob("*"):
        if path.is_file():
            text=path.read_text(encoding="utf-8").replace("{{skill_id}}",args.skill_id).replace("{{display_name}}",display)
            path.write_text(text,encoding="utf-8",newline="\n")
    print(target.as_posix()); return 0
if __name__=="__main__": raise SystemExit(main())
