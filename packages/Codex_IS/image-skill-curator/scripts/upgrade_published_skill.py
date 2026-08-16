from __future__ import annotations
import argparse, json, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(SCRIPT_ROOT))
from skill_package import HASH_ALGORITHM, VALIDATOR_VERSION, core_sha256, file_sha256, package_sha256, read_json, validate_package  # noqa: E402

def write(path:Path,value:dict)->None: path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("package",type=Path); parser.add_argument("--source",action="append",required=True,type=Path); parser.add_argument("--approved-by",choices=["user"],required=True)
    args=parser.parse_args(); package=args.package.resolve(strict=True); report=read_json(package/"intake-report.json")
    issues=validate_package(package,require_report=True)
    if issues: print(json.dumps({"status":"invalid","issues":issues},ensure_ascii=False,indent=2)); return 2
    if report["status"]!="approved" or not report["user_approval"]["approved"] or report["reviewed_core_sha256"]!=core_sha256(package): raise SystemExit("Package is not bound to current user approval")
    sources=[{"name":p.resolve(strict=True).name,"sha256":file_sha256(p.resolve(strict=True))} for p in args.source]
    parent=package.parent
    with tempfile.TemporaryDirectory(prefix="codex-is-upgrade-",dir=parent) as raw:
        staging=Path(raw)/package.name; shutil.copytree(package,staging); (staging/"intake-receipt.json").unlink(missing_ok=True)
        staged_report=read_json(staging/"intake-report.json"); staged_report["status"]="published"; write(staging/"intake-report.json",staged_report)
        receipt={"schema_version":2,"hash_algorithm":HASH_ALGORITHM,"skill_id":package.name,"status":"published","validator_version":VALIDATOR_VERSION,"approved_by":"user","validated_at":datetime.now(timezone.utc).isoformat(),"sources":sources,"intake_report_sha256":file_sha256(staging/"intake-report.json"),"reviewed_core_sha256":report["reviewed_core_sha256"],"package_sha256":package_sha256(staging)}
        write(staging/"intake-receipt.json",receipt); post=validate_package(staging,require_report=True,require_receipt=True)
        if post: print(json.dumps({"status":"invalid_after_receipt","issues":post},ensure_ascii=False,indent=2)); return 2
        backup=parent/(package.name+".upgrade-backup")
        if backup.exists(): raise SystemExit(f"Backup path already exists: {backup}")
        package.replace(backup)
        try: staging.replace(package)
        except Exception:
            if not package.exists(): backup.replace(package)
            raise
        shutil.rmtree(backup)
    print(json.dumps({"status":"upgraded","package":package.as_posix(),"package_sha256":receipt["package_sha256"]},ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
