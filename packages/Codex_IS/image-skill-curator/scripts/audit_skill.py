from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from datetime import datetime, timezone

SCRIPT_ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(SCRIPT_ROOT))
from skill_package import core_sha256, file_sha256, read_json, validate_package  # noqa: E402

def write(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); tmp.replace(path)

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("package",type=Path); parser.add_argument("--source",action="append",required=True,type=Path); parser.add_argument("--report",type=Path)
    args=parser.parse_args(); package=args.package.resolve(strict=True); contract=read_json(package/"contract.json")
    issues=validate_package(package); sources=[]
    for item in args.source:
        source=item.resolve(strict=True); sources.append({"name":source.name,"sha256":file_sha256(source)})
    report={"schema_version":1,"status":"needs_review" if issues else "ready_for_approval","skill_id":contract["skill_id"],"display_name":contract["display_name"],"sources":sources,
      "duplicate_check":{"status":"manual_review_required","checked_at":datetime.now(timezone.utc).isoformat()},"extraction_summary":{"contract_facts":"reviewed","workflow_rules":"reviewed","creative_guidance":"reviewed","examples_define_contract":False},
      "reference_summary":[{"id":x["id"],"role":x["role"],"scope":x["scope"],"required":x["required"],"min_count":x["min_count"],"max_count":x["max_count"]} for x in contract["references"]],
      "output_summary":{"supported_ratios":contract["output"]["supported_ratios"],"business_constraints":contract["business_constraints"]},"isolated_content":[],"contract_conflicts":[],"blocking_questions":[],"validation_issues":issues,"experience_preservation":{"creative_guidance":True,"failure_cases":True,"examples":True},"reviewed_core_sha256":core_sha256(package),"user_approval":{"required":True,"approved":False,"approved_by":None,"approved_at":None}}
    destination=args.report.resolve() if args.report else package/"intake-report.json"; write(destination,report)
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if not issues else 2
if __name__=="__main__": raise SystemExit(main())
