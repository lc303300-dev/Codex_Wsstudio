from __future__ import annotations
import json, re, sys
from pathlib import Path
IS_ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(IS_ROOT/"image-skill-curator"/"scripts"))
from skill_package import HASH_ALGORITHM, package_sha256  # noqa: E402,F401
SHA256_PATTERN=re.compile(r"^[a-f0-9]{64}$")
def validate_receipt(root:Path,expected_skill_id:str|None=None)->tuple[dict|None,list[str]]:
    path=root/"intake-receipt.json"
    if not path.is_file(): return None,["MISSING_RECEIPT"]
    try: receipt=json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError,json.JSONDecodeError): return None,["INVALID_RECEIPT"]
    issues=[]
    if receipt.get("schema_version")!=2 or receipt.get("hash_algorithm")!=HASH_ALGORITHM: issues.append("UNSUPPORTED_RECEIPT_SCHEMA")
    if receipt.get("status")!="published" or receipt.get("approved_by")!="user" or (expected_skill_id and receipt.get("skill_id")!=expected_skill_id): issues.append("INVALID_RECEIPT_IDENTITY")
    if not SHA256_PATTERN.fullmatch(str(receipt.get("package_sha256",""))): issues.append("INVALID_RECEIPT_FIELDS")
    elif receipt["package_sha256"]!=package_sha256(root): issues.append("STALE_RECEIPT")
    return receipt,list(dict.fromkeys(issues))

