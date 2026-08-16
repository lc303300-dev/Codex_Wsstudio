from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


CS_ROOT = Path(__file__).resolve().parents[2]
INTEGRITY_ROOT = CS_ROOT / "codex-cs-skill-curator" / "scripts"
if str(INTEGRITY_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRITY_ROOT))

from package_integrity import package_sha256, validate_receipt  # noqa: E402
DEFAULT_SKILLS_ROOT = CS_ROOT / "business-skills"
DEFAULT_PROJECTS_ROOT = CS_ROOT / ".codex-cs-private" / "projects"
PROJECT_FILE = "project.json"
MEDIA_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"},
    "video": {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"},
}
RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}


class PipelineError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_project_id(value: str | None) -> str:
    if value is None:
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in value):
        raise PipelineError("project_id may contain only letters, numbers, hyphens, and underscores")
    return value


def project_path(projects_root: Path, project_id: str) -> Path:
    return projects_root.resolve() / safe_project_id(project_id)


def load_project(projects_root: Path, project_id: str) -> tuple[Path, dict]:
    root = project_path(projects_root, project_id)
    manifest = root / PROJECT_FILE
    if not manifest.is_file():
        raise PipelineError(f"project not found: {root}")
    return root, read_json(manifest)


def save_project(root: Path, project: dict) -> None:
    project["updated_at"] = utc_now()
    write_json(root / PROJECT_FILE, project)


def markdown_link_target(path: Path | str) -> str:
    """Return an absolute local target that Markdown renderers can recognize."""
    return Path(path).resolve().as_posix()


def require_state(project: dict, allowed: set[str]) -> None:
    if project["state"] not in allowed:
        raise PipelineError(f"state {project['state']} does not allow this action; expected one of {sorted(allowed)}")


def load_contract(skills_root: Path, skill_id: str, display_name: str) -> tuple[Path, dict, dict]:
    package_root = skills_root.resolve() / skill_id
    contract_path = package_root / "contract.json"
    if not contract_path.is_file():
        raise PipelineError(f"published Skill contract not found: {contract_path}")
    contract = read_json(contract_path)
    if contract.get("skill_id") != skill_id:
        raise PipelineError("skill_id does not match contract.json")
    if contract.get("display_name") != display_name:
        raise PipelineError("display_name does not match the published Skill contract")
    references = contract.get("references")
    if not isinstance(references, list) or not references:
        raise PipelineError("contract must define at least one reference slot")
    receipt, receipt_issues = validate_receipt(package_root, skill_id)
    if receipt_issues:
        raise PipelineError("published Skill receipt is missing or invalid: " + ", ".join(receipt_issues))
    assert receipt is not None
    return contract_path, contract, receipt


def verify_project_skill(project: dict) -> None:
    skill = project.get("skill", {})
    contract_path = Path(str(skill.get("contract_path", "")))
    package_root = contract_path.parent
    receipt, receipt_issues = validate_receipt(package_root, skill.get("skill_id"))
    if receipt_issues:
        raise PipelineError("published Skill receipt is missing or invalid: " + ", ".join(receipt_issues))
    assert receipt is not None
    if not skill.get("package_hash"):
        if not contract_path.is_file() or file_sha256(contract_path) != skill.get("contract_hash"):
            raise PipelineError("published Skill contract changed after legacy project creation")
        return
    current_hash = package_sha256(package_root)
    if current_hash != skill.get("package_hash") or receipt.get("package_sha256") != skill.get("package_hash"):
        raise PipelineError("published Skill package changed after project creation")


def clamp_count(value: int, minimum: int, maximum: int | None) -> int:
    value = max(value, minimum)
    return min(value, maximum) if maximum is not None else value


def planned_count(reference: dict, duration: int) -> tuple[int, str]:
    rule = reference.get("count_rule")
    if not isinstance(rule, dict):
        raise PipelineError(f"slot {reference.get('id')} is missing count_rule")
    rule_type = rule.get("type")
    minimum = int(reference.get("min_count", 0))
    maximum = reference.get("max_count")
    if rule_type == "fixed":
        count = int(rule["fixed_count"])
    elif rule_type in {"duration_formula", "bounded_recommendation"}:
        raw = duration * float(rule.get("duration_share", 1)) / float(rule["seconds_per_item"])
        rounding = rule["rounding"]
        count = math.ceil(raw) if rounding == "ceil" else math.floor(raw) if rounding == "floor" else math.floor(raw + 0.5)
    elif rule_type == "duration_lookup":
        anchors = rule.get("duration_to_count", [])
        if not anchors:
            raise PipelineError(f"slot {reference.get('id')} has an empty duration lookup")
        selected = min(anchors, key=lambda item: (abs(int(item["duration_seconds"]) - duration), int(item["duration_seconds"])))
        count = int(selected["count"])
    else:
        raise PipelineError(f"slot {reference.get('id')} has unsupported count_rule type: {rule_type}")
    return clamp_count(count, minimum, maximum), str(rule.get("enforcement"))


def create_project(
    projects_root: Path,
    skills_root: Path,
    project_id: str | None,
    skill_id: str,
    display_name: str,
    ratio: str,
    duration: int,
    skill_confirmed: bool,
) -> dict:
    if not skill_confirmed:
        raise PipelineError("Skill name must be explicitly confirmed before project creation")
    if ratio not in RATIOS:
        raise PipelineError(f"unsupported ratio {ratio}; choose one of {sorted(RATIOS)}")
    if duration < 4 or duration > 30:
        raise PipelineError("duration must be between 4 and 30 seconds")
    contract_path, contract, receipt = load_contract(skills_root, skill_id, display_name)
    identifier = safe_project_id(project_id)
    root = project_path(projects_root, identifier)
    if root.exists():
        raise PipelineError(f"project already exists: {root}")
    root.mkdir(parents=True)
    slots = []
    for position, reference in enumerate(contract["references"]):
        slot_id = reference["id"]
        source = root / "materials" / slot_id / "source"
        final = root / "materials" / slot_id / "final"
        source.mkdir(parents=True)
        final.mkdir(parents=True)
        target_count, count_enforcement = planned_count(reference, duration)
        slots.append({
            "id": slot_id,
            "position": position,
            "media_type": reference["media_type"],
            "role": reference.get("role"),
            "description": reference.get("description", ""),
            "required": bool(reference.get("required")),
            "min_count": int(reference.get("min_count", 0)),
            "max_count": reference.get("max_count"),
            "planned_count": target_count,
            "count_enforcement": count_enforcement,
            "count_rule": reference["count_rule"],
            "ordered": bool(reference.get("ordered")),
            "source_dir": str(source.resolve()),
            "final_dir": str(final.resolve()),
            "source_files": [],
            "final_files": [],
        })
    now = utc_now()
    project = {
        "schema_version": 1,
        "project_id": identifier,
        "state": "awaiting_image_stage_choice",
        "state_history": [
            {"state": "awaiting_skill_confirmation", "at": now},
            {"state": "awaiting_video_settings", "at": now},
            {"state": "project_initialized", "at": now},
            {"state": "awaiting_image_stage_choice", "at": now},
        ],
        "created_at": now,
        "updated_at": now,
        "skill": {
            "skill_id": skill_id,
            "display_name": display_name,
            "confirmed": True,
            "contract_path": str(contract_path.resolve()),
            "contract_hash": file_sha256(contract_path),
            "package_hash": receipt["package_sha256"],
            "receipt_schema_version": receipt["schema_version"],
            "receipt_validated_at": receipt["validated_at"],
        },
        "video_settings": {"ratio": ratio, "duration_seconds": duration},
        "image_stage": None,
        "material_slots": slots,
        "final_images": [],
        "material_hash": None,
        "prompts": [],
        "archived_prompts": [],
        "active_prompt_version": None,
        "generation": None,
    }
    save_project(root, project)
    return public_result(root, project)


def transition(project: dict, state: str) -> None:
    project["state"] = state
    project["state_history"].append({"state": state, "at": utc_now()})


def choose_image_stage(projects_root: Path, project_id: str, mode: str) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"awaiting_image_stage_choice"})
    project["image_stage"] = mode
    transition(project, "collecting_user_materials" if mode == "user_supplied" else "generating_images")
    save_project(root, project)
    return public_result(root, project)


def media_files(directory: Path, media_type: str) -> list[Path]:
    allowed = MEDIA_EXTENSIONS.get(media_type)
    files = [item for item in directory.iterdir() if item.is_file() and (allowed is None or item.suffix.lower() in allowed)]
    return sorted(files, key=lambda item: (item.name.casefold(), item.name))


def scan_materials(projects_root: Path, project_id: str) -> dict:
    root, project = load_project(projects_root, project_id)
    for slot in project["material_slots"]:
        slot["source_files"] = [str(path.resolve()) for path in media_files(Path(slot["source_dir"]), slot["media_type"])]
        slot["final_files"] = [str(path.resolve()) for path in media_files(Path(slot["final_dir"]), slot["media_type"])]
    save_project(root, project)
    return public_result(root, project)


def copy_source_to_final(slot: dict) -> None:
    for source in media_files(Path(slot["source_dir"]), slot["media_type"]):
        target = Path(slot["final_dir"]) / source.name
        if target.exists():
            if file_sha256(source) != file_sha256(target):
                raise PipelineError(f"refusing to overwrite different final file: {target}")
        else:
            shutil.copy2(source, target)


def material_snapshot(project: dict) -> tuple[list[dict], str]:
    ordered = []
    for slot in sorted(project["material_slots"], key=lambda item: item["position"]):
        final_paths = media_files(Path(slot["final_dir"]), slot["media_type"])
        count = len(final_paths)
        if slot["required"] and count < slot["min_count"]:
            raise PipelineError(f"slot {slot['id']} requires at least {slot['min_count']} final file(s); found {count}")
        if slot["max_count"] is not None and count > slot["max_count"]:
            raise PipelineError(f"slot {slot['id']} allows at most {slot['max_count']} final file(s); found {count}")
        if slot.get("count_enforcement") == "required" and count != slot.get("planned_count"):
            raise PipelineError(
                f"slot {slot['id']} requires exactly {slot['planned_count']} final file(s) for "
                f"{project['video_settings']['duration_seconds']} seconds; found {count}"
            )
        slot["final_files"] = [str(path.resolve()) for path in final_paths]
        for file_position, path in enumerate(final_paths):
            ordered.append({
                "slot_id": slot["id"],
                "slot_position": slot["position"],
                "file_position": file_position,
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
            })
    if not ordered:
        raise PipelineError("no final materials found")
    canonical = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ordered, text_sha256(canonical)


def lock_final(projects_root: Path, project_id: str, use_source: bool) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"collecting_user_materials", "generating_images", "final_images_ready", "awaiting_prompt_confirmation", "prompt_confirmed"})
    if use_source and project.get("image_stage") != "user_supplied":
        raise PipelineError("--use-source is allowed only in user_supplied image mode")
    if use_source:
        for slot in project["material_slots"]:
            copy_source_to_final(slot)
    images, material_hash = material_snapshot(project)
    changed = project.get("material_hash") not in (None, material_hash)
    project["final_images"] = images
    project["material_hash"] = material_hash
    if changed and project.get("prompts"):
        for prompt in project["prompts"]:
            prompt["status"] = "superseded_by_material_change"
        project.setdefault("archived_prompts", []).extend(project["prompts"])
        project["prompts"] = []
        project["active_prompt_version"] = None
        project.pop("confirmation", None)
    transition(project, "final_images_ready")
    save_project(root, project)
    return public_result(root, project)


def load_prompt_text(text: str | None, prompt_file: Path | None) -> str:
    value = prompt_file.read_text(encoding="utf-8-sig") if prompt_file else text
    if not value or not value.strip():
        raise PipelineError("prompt text must not be empty")
    return value.strip()


def material_prompt_aliases(project: dict) -> list[str]:
    aliases = []
    for item in project.get("final_images", []):
        stem = Path(str(item.get("path", ""))).stem
        if len(stem) >= 3 and not stem.isdecimal():
            aliases.append(stem)
    return sorted(set(aliases), key=str.casefold)


def validate_prompt_content(project: dict, content: str) -> None:
    leaked = [alias for alias in material_prompt_aliases(project) if alias and alias in content]
    if leaked:
        raise PipelineError(
            "prompt leaks internal material filename or alias: "
            + ", ".join(leaked[:5])
            + "; use only ordered labels such as 图片1, 图片2"
        )
    if re.search(r"(?m)^\s*\d+(?:\.\d+)?\s*[–-]\s*\d+(?:\.\d+)?\s*秒\s*｜[^｜\n]+｜\s*图片\d+\s*$", content):
        raise PipelineError("prompt contains an invalid storyboard heading; write natural headings such as '0.0-4.0 秒，第一段，参考图片2。'")


def set_cs_prompt(projects_root: Path, project_id: str, content: str) -> dict:
    root, project = load_project(projects_root, project_id)
    verify_project_skill(project)
    require_state(project, {"final_images_ready"})
    if project["prompts"]:
        raise PipelineError("CS may create only prompt V1; all revisions must use the DT revision command")
    validate_prompt_content(project, content)
    transition(project, "authoring_prompt")
    prompt = {
        "version": 1,
        "author": "cs_skill",
        "content": content,
        "prompt_hash": text_sha256(content),
        "material_hash": project["material_hash"],
        "feedback": None,
        "status": "draft",
        "created_at": utc_now(),
    }
    project["prompts"].append(prompt)
    project["active_prompt_version"] = 1
    transition(project, "awaiting_prompt_confirmation")
    save_project(root, project)
    return public_result(root, project)


def request_revision(projects_root: Path, project_id: str, feedback: str) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"awaiting_prompt_confirmation"})
    if not feedback.strip():
        raise PipelineError("revision feedback must not be empty")
    active = project["prompts"][project["active_prompt_version"] - 1]
    active["status"] = "revision_requested"
    active["feedback"] = feedback.strip()
    transition(project, "revision_requested")
    transition(project, "dt_revision")
    save_project(root, project)
    return public_result(root, project)


def set_dt_revision(projects_root: Path, project_id: str, content: str) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"dt_revision"})
    validate_prompt_content(project, content)
    previous = project["prompts"][-1]
    version = len(project["prompts"]) + 1
    prompt = {
        "version": version,
        "author": "dt",
        "content": content,
        "prompt_hash": text_sha256(content),
        "material_hash": project["material_hash"],
        "feedback": previous.get("feedback"),
        "status": "draft",
        "created_at": utc_now(),
    }
    project["prompts"].append(prompt)
    project["active_prompt_version"] = version
    transition(project, "awaiting_prompt_confirmation")
    save_project(root, project)
    return public_result(root, project)


def confirm_prompt(projects_root: Path, project_id: str) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"awaiting_prompt_confirmation"})
    _, current_material_hash = material_snapshot(project)
    active = project["prompts"][project["active_prompt_version"] - 1]
    if current_material_hash != project["material_hash"] or active["material_hash"] != current_material_hash:
        raise PipelineError("final materials changed after prompt authoring; lock materials and author a new prompt")
    validate_prompt_content(project, active["content"])
    active["prompt_hash"] = text_sha256(active["content"])
    active["status"] = "confirmed"
    active["confirmed_at"] = utc_now()
    project["confirmation"] = {
        "prompt_version": active["version"],
        "prompt_hash": active["prompt_hash"],
        "material_hash": current_material_hash,
        "confirmed_at": active["confirmed_at"],
    }
    transition(project, "prompt_confirmed")
    save_project(root, project)
    return public_result(root, project)


def start_generation(projects_root: Path, project_id: str) -> dict:
    root, project = load_project(projects_root, project_id)
    verify_project_skill(project)
    require_state(project, {"prompt_confirmed"})
    _, current_material_hash = material_snapshot(project)
    active = project["prompts"][project["active_prompt_version"] - 1]
    confirmation = project.get("confirmation", {})
    if current_material_hash != confirmation.get("material_hash"):
        raise PipelineError("final materials changed after confirmation; video submission is blocked")
    if text_sha256(active["content"]) != confirmation.get("prompt_hash"):
        raise PipelineError("prompt changed after confirmation; video submission is blocked")
    validate_prompt_content(project, active["content"])
    project["generation"] = {
        "status": "ready_for_external_submission",
        "prompt_version": active["version"],
        "prompt_hash": confirmation["prompt_hash"],
        "material_hash": confirmation["material_hash"],
        "started_at": utc_now(),
    }
    project["generation"]["submission_payload"] = build_video_submission_payload(project, active)
    transition(project, "generating_video")
    save_project(root, project)
    return public_result(root, project)


def complete_project(projects_root: Path, project_id: str, external_result: str | None) -> dict:
    root, project = load_project(projects_root, project_id)
    require_state(project, {"generating_video"})
    project["generation"]["status"] = "completed"
    project["generation"]["external_result"] = external_result
    project["generation"]["completed_at"] = utc_now()
    transition(project, "completed")
    save_project(root, project)
    return public_result(root, project)


def public_result(root: Path, project: dict) -> dict:
    result = {
        "project_id": project["project_id"],
        "state": project["state"],
        "project_dir": str(root.resolve()),
        "project_dir_link_target": markdown_link_target(root),
        "project_file": str((root / PROJECT_FILE).resolve()),
        "project_file_link_target": markdown_link_target(root / PROJECT_FILE),
        "material_directories": [
            {
                "slot_id": slot["id"],
                "source_dir": slot["source_dir"],
                "source_dir_link_target": markdown_link_target(slot["source_dir"]),
                "final_dir": slot["final_dir"],
                "final_dir_link_target": markdown_link_target(slot["final_dir"]),
                "planned_count": slot["planned_count"],
                "count_enforcement": slot["count_enforcement"],
                "count_rationale": slot["count_rule"]["rationale"],
            }
            for slot in project["material_slots"]
        ],
        "image_stage": project.get("image_stage"),
        "final_images": project.get("final_images", []),
        "material_hash": project.get("material_hash"),
        "active_prompt_version": project.get("active_prompt_version"),
        "generation": project.get("generation"),
    }
    if project.get("image_stage") == "generate":
        result["image_generation_tasks"] = [
            {
                "slot_id": slot["id"],
                "media_type": slot["media_type"],
                "source_files": slot.get("source_files", []),
                "target_dir": slot["final_dir"],
                "required_count": slot["min_count"],
                "planned_count": slot["planned_count"],
                "count_enforcement": slot["count_enforcement"],
                "max_count": slot["max_count"],
            }
            for slot in project["material_slots"]
            if slot["media_type"] == "image"
        ]
    return result


def build_video_submission_payload(project: dict, active_prompt: dict) -> dict:
    media = {"images": [], "videos": [], "audios": []}
    plural = {"image": "images", "video": "videos", "audio": "audios"}
    slot_types = {slot["id"]: slot["media_type"] for slot in project["material_slots"]}
    for item in project.get("final_images", []):
        media_type = slot_types[item["slot_id"]]
        media[plural[media_type]].append(item["path"])
    return {
        "tool": "generate_video",
        "prompt": active_prompt["content"],
        "ordered_media": media,
        "video_ratio": project["video_settings"]["ratio"],
        "video_duration": project["video_settings"]["duration_seconds"],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Codex_CS business Skill video project state bridge")
    result.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    result.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--project-id")
    create.add_argument("--skill-id", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--ratio", required=True)
    create.add_argument("--duration", required=True, type=int)
    create.add_argument("--skill-confirmed", action="store_true")
    stage = commands.add_parser("choose-image-stage")
    stage.add_argument("project_id")
    stage.add_argument("--mode", choices=("user_supplied", "generate"), required=True)
    for name in ("scan", "show", "confirm-prompt", "start-generation"):
        command = commands.add_parser(name)
        command.add_argument("project_id")
    lock = commands.add_parser("lock-final")
    lock.add_argument("project_id")
    lock.add_argument("--use-source", action="store_true")
    cs = commands.add_parser("set-cs-prompt")
    cs.add_argument("project_id")
    cs.add_argument("--text")
    cs.add_argument("--file", type=Path)
    revision = commands.add_parser("request-revision")
    revision.add_argument("project_id")
    revision.add_argument("--feedback", required=True)
    dt = commands.add_parser("set-dt-revision")
    dt.add_argument("project_id")
    dt.add_argument("--text")
    dt.add_argument("--file", type=Path)
    complete = commands.add_parser("complete")
    complete.add_argument("project_id")
    complete.add_argument("--external-result")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "create":
            result = create_project(args.projects_root, args.skills_root, args.project_id, args.skill_id, args.display_name, args.ratio, args.duration, args.skill_confirmed)
        elif args.command == "choose-image-stage":
            result = choose_image_stage(args.projects_root, args.project_id, args.mode)
        elif args.command == "scan":
            result = scan_materials(args.projects_root, args.project_id)
        elif args.command == "lock-final":
            result = lock_final(args.projects_root, args.project_id, args.use_source)
        elif args.command == "set-cs-prompt":
            result = set_cs_prompt(args.projects_root, args.project_id, load_prompt_text(args.text, args.file))
        elif args.command == "request-revision":
            result = request_revision(args.projects_root, args.project_id, args.feedback)
        elif args.command == "set-dt-revision":
            result = set_dt_revision(args.projects_root, args.project_id, load_prompt_text(args.text, args.file))
        elif args.command == "confirm-prompt":
            result = confirm_prompt(args.projects_root, args.project_id)
        elif args.command == "start-generation":
            result = start_generation(args.projects_root, args.project_id)
        elif args.command == "complete":
            result = complete_project(args.projects_root, args.project_id, args.external_result)
        else:
            root, project = load_project(args.projects_root, args.project_id)
            result = public_result(root, project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PipelineError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
