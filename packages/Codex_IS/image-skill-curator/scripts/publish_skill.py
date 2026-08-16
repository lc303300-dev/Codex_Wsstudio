from __future__ import annotations
import argparse, json, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent; IS_ROOT=SCRIPT_ROOT.parents[1]; sys.path.insert(0,str(SCRIPT_ROOT))
from skill_package import HASH_ALGORITHM, VALIDATOR_VERSION, core_sha256, file_sha256, package_sha256, read_json, validate_package  # noqa: E402

def write(path:Path,value:dict)->None: path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("package",type=Path); parser.add_argument("--source",action="append",required=True,type=Path); parser.add_argument("--approved-by",choices=["user"],required=True); parser.add_argument("--library-root",type=Path,default=IS_ROOT/"business-skills")
    args=parser.parse_args(); package=args.package.resolve(strict=True); report=read_json(package/"intake-report.json")
    issues=validate_package(package,require_report=True)
    if issues: print(json.dumps({"status":"invalid","issues":issues},ensure_ascii=False,indent=2)); return 2
    if report["status"]!="approved" or not report["user_approval"]["approved"] or report["reviewed_core_sha256"]!=core_sha256(package): raise SystemExit("Package is not bound to a current user approval")
    destination=args.library_root.resolve()/report["skill_id"]
    if destination.exists(): raise SystemExit(f"Refusing to overwrite published Skill: {destination}")
    sources=[{"name":p.resolve(strict=True).name,"sha256":file_sha256(p.resolve(strict=True))} for p in args.source]
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codex-is-publish-",dir=destination.parent) as raw:
        staging=Path(raw)/report["skill_id"]; shutil.copytree(package,staging); (staging/"intake-receipt.json").unlink(missing_ok=True)
        staged_report=read_json(staging/"intake-report.json"); staged_report["status"]="published"; write(staging/"intake-report.json",staged_report)
        receipt={"schema_version":2,"hash_algorithm":HASH_ALGORITHM,"skill_id":report["skill_id"],"status":"published","validator_version":VALIDATOR_VERSION,"approved_by":"user","validated_at":datetime.now(timezone.utc).isoformat(),"sources":sources,"intake_report_sha256":file_sha256(staging/"intake-report.json"),"reviewed_core_sha256":report["reviewed_core_sha256"],"package_sha256":package_sha256(staging)}
        write(staging/"intake-receipt.json",receipt); post=validate_package(staging,require_report=True,require_receipt=True)
        if post: print(json.dumps({"status":"invalid_after_receipt","issues":post},ensure_ascii=False,indent=2)); return 2
        staging.replace(destination)
    if args.library_root.resolve()==(IS_ROOT/"business-skills").resolve():
        run=subprocess.run([sys.executable,str(IS_ROOT/"skill-registry"/"scripts"/"registry.py"),"build"],text=True,capture_output=True,encoding="utf-8")
        if run.returncode: shutil.rmtree(destination); print(json.dumps({"status":"registry_failed","stderr":run.stderr},ensure_ascii=False)); return 2
    print(json.dumps({"status":"published","destination":destination.as_posix(),"package_sha256":receipt["package_sha256"]},ensure_ascii=False,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
