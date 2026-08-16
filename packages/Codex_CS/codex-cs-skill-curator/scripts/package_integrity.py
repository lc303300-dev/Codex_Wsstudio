from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


LEGACY_HASH_ALGORITHM = "codex-cs-package-sha256-v1-raw"
CANONICAL_HASH_ALGORITHM = "codex-cs-package-sha256-v2"
TEXT_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt"}
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_file_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def package_sha256(
    root: Path,
    *,
    include_receipt: bool = False,
    algorithm: str = CANONICAL_HASH_ALGORITHM,
) -> str:
    if algorithm not in {LEGACY_HASH_ALGORITHM, CANONICAL_HASH_ALGORITHM}:
        raise ValueError(f"Unsupported package hash algorithm: {algorithm}")
    digest = hashlib.sha256()
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and (include_receipt or path.name != "intake-receipt.json")
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes() if algorithm == LEGACY_HASH_ALGORITHM else canonical_file_bytes(path)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def receipt_algorithm(receipt: dict) -> str | None:
    schema = receipt.get("schema_version")
    if schema == 1:
        return LEGACY_HASH_ALGORITHM
    if schema == 2 and receipt.get("hash_algorithm") == CANONICAL_HASH_ALGORITHM:
        return CANONICAL_HASH_ALGORITHM
    return None


def validate_receipt(root: Path, expected_skill_id: str | None = None) -> tuple[dict | None, list[str]]:
    path = root / "intake-receipt.json"
    if not path.is_file():
        return None, ["MISSING_RECEIPT"]
    try:
        receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None, ["INVALID_RECEIPT"]
    if not isinstance(receipt, dict):
        return None, ["INVALID_RECEIPT"]

    issues: list[str] = []
    schema = receipt.get("schema_version")
    v1_fields = {
        "schema_version", "skill_id", "status", "validator_version", "approved_by",
        "validated_at", "sources", "package_sha256",
    }
    expected_fields = v1_fields if schema == 1 else v1_fields | {"hash_algorithm"} if schema == 2 else set()
    if not expected_fields or set(receipt) != expected_fields:
        issues.append("INVALID_RECEIPT_FIELDS")
    if (
        receipt.get("status") != "published"
        or receipt.get("approved_by") != "user"
        or (expected_skill_id is not None and receipt.get("skill_id") != expected_skill_id)
    ):
        issues.append("INVALID_RECEIPT_IDENTITY")
    if not isinstance(receipt.get("validator_version"), str) or not receipt.get("validator_version"):
        issues.append("INVALID_RECEIPT_FIELDS")
    if not isinstance(receipt.get("validated_at"), str) or not receipt.get("validated_at"):
        issues.append("INVALID_RECEIPT_FIELDS")
    sources = receipt.get("sources")
    if not isinstance(sources, list) or not sources:
        issues.append("MISSING_RECEIPT_SOURCES")
    elif any(
        not isinstance(item, dict)
        or set(item) != {"name", "sha256"}
        or not isinstance(item.get("name"), str)
        or not item.get("name")
        or not SHA256_PATTERN.fullmatch(str(item.get("sha256", "")))
        for item in sources
    ):
        issues.append("INVALID_RECEIPT_SOURCES")
    if not SHA256_PATTERN.fullmatch(str(receipt.get("package_sha256", ""))):
        issues.append("INVALID_RECEIPT_FIELDS")

    algorithm = receipt_algorithm(receipt)
    if algorithm is None:
        issues.append("UNSUPPORTED_RECEIPT_SCHEMA")
    elif receipt.get("package_sha256") != package_sha256(root, algorithm=algorithm):
        issues.append("STALE_RECEIPT")
    return receipt, list(dict.fromkeys(issues))
