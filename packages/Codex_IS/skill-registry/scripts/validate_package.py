from __future__ import annotations
import argparse, json, sys
from pathlib import Path
IS_ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(IS_ROOT/"image-skill-curator"/"scripts"))
from skill_package import validate_package  # noqa: E402
def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("package",type=Path); parser.add_argument("--require-report",action="store_true"); parser.add_argument("--require-receipt",action="store_true"); args=parser.parse_args()
    root=args.package.resolve(); issues=validate_package(root,require_report=args.require_report,require_receipt=args.require_receipt)
    print(json.dumps({"package":root.as_posix(),"valid":not issues,"issues":issues},ensure_ascii=False,indent=2)); return 0 if not issues else 2
if __name__=="__main__": raise SystemExit(main())

