from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(SCRIPT_ROOT))
from skill_package import core_sha256  # noqa: E402

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("package",type=Path); parser.add_argument("--approved-by",choices=["user"],required=True)
    args=parser.parse_args(); root=args.package.resolve(strict=True); path=root/"intake-report.json"; report=json.loads(path.read_text(encoding="utf-8-sig"))
    if report["status"]!="ready_for_approval" or report["blocking_questions"] or report["contract_conflicts"] or report["validation_issues"]: raise SystemExit("Report is not ready for approval")
    if report["reviewed_core_sha256"]!=core_sha256(root): raise SystemExit("Core package changed after review")
    report["status"]="approved"; report["user_approval"]={"required":True,"approved":True,"approved_by":"user","approved_at":datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
