from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


VALIDATOR_VERSION = "1.0.0"
SKILL_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REFERENCE_IDS = {"image", "video", "audio"}
REFERENCE_ROLES = {
    "identity", "scene", "style", "start_frame", "end_frame",
    "footage", "music", "sound", "other",
}
ALLOWED_VIDEO_MODES = {"image2video", "frames2video", "multimodal2video"}
REQUIRED_KNOWLEDGE = {
    "creative_guidance": "references/creative-guidance.md",
    "community_experience": "references/community-experience.md",
    "failure_cases": "references/failure-cases.md",
    "examples": "references/examples.md",
}
REQUIRED_FILES = {
    "SKILL.md",
    "contract.json",
    "agents/openai.yaml",
    *REQUIRED_KNOWLEDGE.values(),
}
PLACEHOLDER_MARKERS = ("CURATOR-REQUIRED", "{{", "}}", "[TODO", "TODO:")
TERMINAL_METADATA = re.compile(
    r"(?im)^\s*(?:Exit code|Wall time|Output|Script completed|Script error)\s*:"
)
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?:^|[\s'\"`(])(?:[a-z]:\\|\\\\)[^\r\n]*")
SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_ -]?key|authorization|bearer|cookie|secret|token)\s*[:=]\s*[^\s<>{}\[\]]+"
)
FORBIDDEN_EXECUTION = re.compile(
    r"(?i)(?:seedance-cli|dreamina\.exe|agy\.exe|media_router\.service|"
    r"--model_version|--poll\b|query_result|user_credit)"
)
ROUTING_LIST_FIELDS = {"aliases", "user_intents", "subjects", "styles", "narrative_patterns", "negative_intents"}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict:
        value = {"code": self.code, "message": self.message}
        if self.path:
            value["path"] = self.path
        return value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\A---\s*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    metadata: dict[str, str] = {}
    for raw in match.group(1).splitlines():
        if not raw.strip():
            continue
        field = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.+)", raw)
        if not field:
            raise ValueError(f"Unsupported frontmatter line: {raw}")
        key, value = field.groups()
        metadata[key] = value.strip().strip("\"'")
    return metadata, match.group(2).strip()


def parse_openai_yaml(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in ("display_name", "short_description", "default_prompt"):
        match = re.search(rf"(?m)^\s+{key}:\s*[\"'](.*?)[\"']\s*$", text)
        if match:
            values[key] = match.group(1)
    return values


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_sha256(root: Path, *, include_receipt: bool = False) -> str:
    digest = hashlib.sha256()
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and (include_receipt or path.name != "intake-receipt.json")
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def load_contract(root: Path) -> dict:
    return json.loads((root / "contract.json").read_text(encoding="utf-8-sig"))


def _add(issues: list[Issue], code: str, message: str, path: Path | str | None = None) -> None:
    issues.append(Issue(code, message, str(path) if path else None))


def validate_package(root: Path, *, require_receipt: bool = False) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []
    if not root.is_dir():
        return [Issue("PACKAGE_NOT_FOUND", "Skill package directory does not exist", str(root))]

    missing = sorted(path for path in REQUIRED_FILES if not (root / path).is_file())
    for path in missing:
        _add(issues, "MISSING_FILE", f"Required file is missing: {path}", path)
    if missing:
        return issues

    skill_id = root.name
    if not SKILL_ID_PATTERN.fullmatch(skill_id) or len(skill_id) > 64:
        _add(issues, "INVALID_SKILL_ID", "Directory name must be lowercase hyphen-case and at most 64 characters", root.name)

    try:
        metadata, body = parse_frontmatter(read_text(root / "SKILL.md"))
    except (OSError, ValueError) as exc:
        _add(issues, "INVALID_SKILL_FRONTMATTER", str(exc), "SKILL.md")
        metadata, body = {}, ""
    if set(metadata) != {"name", "description"}:
        _add(issues, "INVALID_SKILL_FRONTMATTER", "Frontmatter must contain only name and description", "SKILL.md")
    if metadata.get("name") != skill_id:
        _add(issues, "SKILL_ID_MISMATCH", "SKILL.md name must equal the package directory name", "SKILL.md")
    if len(metadata.get("description", "")) < 20:
        _add(issues, "DESCRIPTION_TOO_SHORT", "Skill description must explain capability and trigger conditions", "SKILL.md")
    if not body:
        _add(issues, "EMPTY_SKILL_BODY", "SKILL.md body must not be empty", "SKILL.md")

    try:
        contract = load_contract(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add(issues, "INVALID_CONTRACT_JSON", str(exc), "contract.json")
        contract = {}
    allowed_top = {"schema_version", "skill_id", "display_name", "description", "references", "video", "authoring", "knowledge"}
    required_top = allowed_top
    if set(contract) != allowed_top:
        _add(issues, "INVALID_CONTRACT_FIELDS", f"contract.json fields must be exactly: {sorted(required_top)}", "contract.json")
    if contract.get("schema_version") != 1:
        _add(issues, "INVALID_SCHEMA_VERSION", "contract schema_version must be 1", "contract.json")
    if contract.get("skill_id") != skill_id:
        _add(issues, "CONTRACT_ID_MISMATCH", "contract skill_id must equal the package directory name", "contract.json")
    if len(str(contract.get("display_name") or "")) < 2:
        _add(issues, "INVALID_DISPLAY_NAME", "display_name must not be empty", "contract.json")
    if len(str(contract.get("description") or "")) < 20:
        _add(issues, "CONTRACT_DESCRIPTION_TOO_SHORT", "contract description must be at least 20 characters", "contract.json")

    references = contract.get("references")
    if not isinstance(references, list) or not references:
        _add(issues, "MISSING_REFERENCES", "At least one image, video, or audio reference slot is required", "contract.json")
        references = []
    seen_ids: set[str] = set()
    minimum_total = 0
    for index, item in enumerate(references, 1):
        path = f"contract.json:references[{index}]"
        required_fields = {"id", "media_type", "role", "description", "required", "min_count", "max_count", "ordered", "observation_required"}
        if not isinstance(item, dict) or set(item) != required_fields:
            _add(issues, "INVALID_REFERENCE_FIELDS", f"Reference fields must be exactly: {sorted(required_fields)}", path)
            continue
        ref_id = item.get("id")
        if not isinstance(ref_id, str) or not SKILL_ID_PATTERN.fullmatch(ref_id):
            _add(issues, "INVALID_REFERENCE_ID", "Reference id must use lowercase hyphen-case", path)
        elif ref_id in seen_ids:
            _add(issues, "DUPLICATE_REFERENCE_ID", f"Duplicate reference id: {ref_id}", path)
        else:
            seen_ids.add(ref_id)
        if item.get("media_type") not in REFERENCE_IDS:
            _add(issues, "INVALID_MEDIA_TYPE", "media_type must be image, video, or audio", path)
        if item.get("role") not in REFERENCE_ROLES:
            _add(issues, "INVALID_REFERENCE_ROLE", f"Unsupported role: {item.get('role')}", path)
        if len(str(item.get("description") or "")) < 4:
            _add(issues, "REFERENCE_DESCRIPTION_TOO_SHORT", "Reference description must explain its purpose", path)
        for field in ("required", "ordered", "observation_required"):
            if not isinstance(item.get(field), bool):
                _add(issues, "INVALID_REFERENCE_BOOLEAN", f"{field} must be boolean", path)
        minimum = item.get("min_count")
        maximum = item.get("max_count")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
            _add(issues, "INVALID_MIN_COUNT", "min_count must be a non-negative integer", path)
        else:
            minimum_total += minimum
        if maximum is not None and (not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1):
            _add(issues, "INVALID_MAX_COUNT", "max_count must be null or a positive integer", path)
        if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
            _add(issues, "INVALID_REFERENCE_RANGE", "min_count must not exceed max_count", path)
        if item.get("required") is True and minimum == 0:
            _add(issues, "REQUIRED_REFERENCE_WITH_ZERO_MIN", "A required reference must have min_count >= 1", path)
    if minimum_total < 1:
        _add(issues, "ZERO_MINIMUM_REFERENCES", "The contract must require at least one reference asset", "contract.json")

    video = contract.get("video")
    if not isinstance(video, dict) or set(video) != {"reference_required", "allowed_modes"}:
        _add(issues, "INVALID_VIDEO_CONTRACT", "video must contain only reference_required and allowed_modes", "contract.json")
    else:
        if video.get("reference_required") is not True:
            _add(issues, "REFERENCE_NOT_REQUIRED", "video.reference_required must be true", "contract.json")
        modes = video.get("allowed_modes")
        if not isinstance(modes, list) or not modes:
            _add(issues, "MISSING_VIDEO_MODE", "At least one reference-based video mode is required", "contract.json")
        elif len(modes) != len(set(modes)) or any(mode not in ALLOWED_VIDEO_MODES for mode in modes):
            _add(issues, "INVALID_VIDEO_MODE", f"Allowed modes are: {sorted(ALLOWED_VIDEO_MODES)}", "contract.json")

    authoring = contract.get("authoring")
    authoring_fields = {"primary_language", "preserve_professional_english", "user_instruction_priority", "timing_strategy", "transition_strategy", "requires_prompt_confirmation", "requires_reference_binding"}
    if not isinstance(authoring, dict) or set(authoring) != authoring_fields:
        _add(issues, "INVALID_AUTHORING_CONTRACT", f"authoring fields must be exactly: {sorted(authoring_fields)}", "contract.json")
    else:
        expected = {
            "primary_language": "zh-CN",
            "preserve_professional_english": True,
            "user_instruction_priority": "highest",
            "requires_prompt_confirmation": True,
            "requires_reference_binding": True,
        }
        for key, value in expected.items():
            if authoring.get(key) != value:
                _add(issues, "INVALID_AUTHORING_POLICY", f"authoring.{key} must equal {value!r}", "contract.json")
        if authoring.get("timing_strategy") not in {"user_defined", "skill_defined", "adaptive", "even_fallback"}:
            _add(issues, "INVALID_TIMING_STRATEGY", "Unsupported timing_strategy", "contract.json")
        if authoring.get("transition_strategy") not in {"user_defined", "skill_defined", "adaptive", "unspecified"}:
            _add(issues, "INVALID_TRANSITION_STRATEGY", "Unsupported transition_strategy", "contract.json")

    knowledge = contract.get("knowledge")
    if knowledge != REQUIRED_KNOWLEDGE:
        _add(issues, "INVALID_KNOWLEDGE_PATHS", f"knowledge must equal {REQUIRED_KNOWLEDGE}", "contract.json")

    routing_path = root / "routing.json"
    if routing_path.is_file():
        try:
            routing = json.loads(routing_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _add(issues, "INVALID_ROUTING_JSON", str(exc), "routing.json")
            routing = {}
        allowed_routing = {"schema_version", "skill_id", "priority", *ROUTING_LIST_FIELDS}
        if set(routing) - allowed_routing:
            _add(issues, "INVALID_ROUTING_FIELDS", f"routing.json contains unsupported fields: {sorted(set(routing) - allowed_routing)}", "routing.json")
        if routing.get("schema_version") != 1 or routing.get("skill_id") != skill_id:
            _add(issues, "INVALID_ROUTING_IDENTITY", "routing schema_version must be 1 and skill_id must match the package", "routing.json")
        priority = routing.get("priority", 50)
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 100:
            _add(issues, "INVALID_ROUTING_PRIORITY", "routing priority must be an integer from 0 to 100", "routing.json")
        for field in ROUTING_LIST_FIELDS:
            values = routing.get(field, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                _add(issues, "INVALID_ROUTING_TERMS", f"routing {field} must be an array of non-empty strings", "routing.json")

    ui = parse_openai_yaml(read_text(root / "agents/openai.yaml"))
    if ui.get("display_name") != contract.get("display_name"):
        _add(issues, "UI_DISPLAY_NAME_MISMATCH", "agents/openai.yaml display_name must match contract display_name", "agents/openai.yaml")
    short = ui.get("short_description", "")
    if not 25 <= len(short) <= 64:
        _add(issues, "INVALID_UI_SHORT_DESCRIPTION", "short_description must contain 25-64 characters", "agents/openai.yaml")
    if f"${skill_id}" not in ui.get("default_prompt", ""):
        _add(issues, "INVALID_UI_DEFAULT_PROMPT", "default_prompt must explicitly mention the Skill as $skill-id", "agents/openai.yaml")

    scan_files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in scan_files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".txt"}:
            continue
        text = read_text(path)
        if any(marker in text for marker in PLACEHOLDER_MARKERS):
            _add(issues, "UNRESOLVED_PLACEHOLDER", "Template placeholder remains in the package", relative)
        if TERMINAL_METADATA.search(text):
            _add(issues, "TERMINAL_METADATA", "Terminal output is not allowed in a business Skill package", relative)
        if WINDOWS_ABSOLUTE_PATH.search(text):
            _add(issues, "ABSOLUTE_PATH", "Machine-local absolute paths are not allowed", relative)
        if SECRET_PATTERN.search(text):
            _add(issues, "POSSIBLE_SECRET", "Possible credential or authorization value detected", relative)
        if relative in {"SKILL.md", "contract.json"} and FORBIDDEN_EXECUTION.search(text):
            _add(issues, "EXECUTION_LAYER_LEAK", "Provider, model, CLI, polling, or router internals are not allowed in the execution contract", relative)
        if relative in {"SKILL.md", "contract.json"} and re.search(r"(?i)\btext2video\b", text):
            _add(issues, "TEXT2VIDEO_FORBIDDEN", "Video business Skills must require reference media", relative)

    receipt_path = root / "intake-receipt.json"
    if require_receipt or receipt_path.exists():
        if not receipt_path.is_file():
            _add(issues, "MISSING_RECEIPT", "Published packages require intake-receipt.json", "intake-receipt.json")
        else:
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                _add(issues, "INVALID_RECEIPT", str(exc), "intake-receipt.json")
                receipt = {}
            receipt_fields = {"schema_version", "skill_id", "status", "validator_version", "approved_by", "validated_at", "sources", "package_sha256"}
            if set(receipt) != receipt_fields:
                _add(issues, "INVALID_RECEIPT_FIELDS", f"Receipt fields must be exactly: {sorted(receipt_fields)}", "intake-receipt.json")
            if receipt.get("schema_version") != 1 or receipt.get("skill_id") != skill_id or receipt.get("status") != "published" or receipt.get("approved_by") != "user":
                _add(issues, "INVALID_RECEIPT_IDENTITY", "Receipt identity or approval fields are invalid", "intake-receipt.json")
            sources = receipt.get("sources")
            if not isinstance(sources, list) or not sources:
                _add(issues, "MISSING_RECEIPT_SOURCES", "Receipt must contain at least one source hash", "intake-receipt.json")
            elif any(not isinstance(item, dict) or set(item) != {"name", "sha256"} or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))) for item in sources):
                _add(issues, "INVALID_RECEIPT_SOURCES", "Every receipt source requires name and SHA-256", "intake-receipt.json")
            actual_hash = package_sha256(root)
            if receipt.get("package_sha256") != actual_hash:
                _add(issues, "STALE_RECEIPT", "Package content changed after publication receipt generation", "intake-receipt.json")

    return issues
