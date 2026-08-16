from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HASH_ALGORITHM = "codex-is-package-sha256-v1"
TEXT_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def canonical_file_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def package_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "intake-receipt.json"):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = canonical_file_bytes(path)
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_receipt(root: Path, expected_skill_id: str | None = None) -> tuple[dict | None, list[str]]:
    path = root / "intake-receipt.json"
    if not path.is_file():
        return None, ["MISSING_RECEIPT"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None, ["INVALID_RECEIPT"]
    expected = {"schema_version", "hash_algorithm", "skill_id", "status", "approved_by", "validated_at", "package_sha256"}
    issues: list[str] = []
    if set(receipt) != expected:
        issues.append("INVALID_RECEIPT_FIELDS")
    if receipt.get("schema_version") != 1 or receipt.get("hash_algorithm") != HASH_ALGORITHM:
        issues.append("UNSUPPORTED_RECEIPT_SCHEMA")
    if receipt.get("status") != "published" or receipt.get("approved_by") != "user":
        issues.append("INVALID_RECEIPT_IDENTITY")
    if expected_skill_id and receipt.get("skill_id") != expected_skill_id:
        issues.append("INVALID_RECEIPT_IDENTITY")
    if not SHA256_PATTERN.fullmatch(str(receipt.get("package_sha256", ""))):
        issues.append("INVALID_RECEIPT_FIELDS")
    elif receipt["package_sha256"] != package_sha256(root):
        issues.append("STALE_RECEIPT")
    return receipt, list(dict.fromkeys(issues))

