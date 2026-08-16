from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


IS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(IS_ROOT / "shared"))
from package_integrity import package_sha256, validate_receipt  # noqa: E402

DEFAULT_SKILLS = IS_ROOT / "business-skills"
DEFAULT_PROJECTS = IS_ROOT / ".codex-is-private" / "projects"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
RATIOS = {"21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"}


class PipelineError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_id(value: str | None) -> str:
    result = value or f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in result):
        raise PipelineError("project_id may contain only letters, numbers, hyphens, and underscores")
    return result


def project_root(projects: Path, project_id: str) -> Path:
    return projects.resolve() / safe_id(project_id)


def load(projects: Path, project_id: str) -> tuple[Path, dict]:
    root = project_root(projects, project_id)
    path = root / "project.json"
    if not path.is_file():
        raise PipelineError(f"project not found: {root}")
    return root, read_json(path)


def save(root: Path, project: dict) -> None:
    project["updated_at"] = utc_now()
    write_json(root / "project.json", project)


def transition(project: dict, state: str) -> None:
    project["state"] = state
    project["state_history"].append({"state": state, "at": utc_now()})


def require_state(project: dict, allowed: set[str]) -> None:
    if project["state"] not in allowed:
        raise PipelineError(f"state {project['state']} does not allow this action")


def image_files(directory: Path) -> list[Path]:
    return sorted((item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS), key=lambda item: item.name.casefold())


def verify_skill(project: dict) -> None:
    skill = project["skill"]
    root = Path(skill["package_root"])
    receipt, issues = validate_receipt(root, skill["skill_id"])
    if issues or receipt is None or package_sha256(root) != skill["package_hash"]:
        raise PipelineError("published Skill package changed or its receipt is invalid")


def create(projects: Path, skills: Path, project_id: str | None, skill_id: str, display_name: str, ratio: str, candidate_count: int, scene_count: int, confirmed: bool) -> dict:
    if not confirmed:
        raise PipelineError("Skill name must be explicitly confirmed")
    root_skill = skills.resolve() / skill_id
    contract_path = root_skill / "contract.json"
    if not contract_path.is_file():
        raise PipelineError("published Skill contract not found")
    contract = read_json(contract_path)
    receipt, issues = validate_receipt(root_skill, skill_id)
    if issues or receipt is None:
        raise PipelineError("published Skill receipt is missing or invalid: " + ", ".join(issues))
    if contract.get("display_name") != display_name:
        raise PipelineError("display_name does not match contract")
    if ratio not in RATIOS or ratio not in contract["output"]["supported_ratios"]:
        raise PipelineError("unsupported or unconfirmed image ratio")
    if candidate_count < 1 or scene_count < 1:
        raise PipelineError("candidate_count and scene_count must be positive")
    identifier = safe_id(project_id)
    root = project_root(projects, identifier)
    if root.exists():
        raise PipelineError(f"project already exists: {root}")
    root.mkdir(parents=True)
    slots = []
    for position, reference in enumerate(contract["references"]):
        source = root / "materials" / reference["id"] / "source"
        final = root / "materials" / reference["id"] / "final"
        source.mkdir(parents=True)
        final.mkdir(parents=True)
        slots.append({**reference, "position": position, "source_dir": str(source.resolve()), "final_dir": str(final.resolve()), "files": []})
    (root / "prompts").mkdir()
    (root / "execution").mkdir()
    (root / "results" / "images").mkdir(parents=True)
    (root / "results" / "review").mkdir()
    now = utc_now()
    project = {
        "schema_version": 1, "project_id": identifier, "state": "awaiting_materials", "state_history": [{"state": "awaiting_skill_confirmation", "at": now}, {"state": "awaiting_ratio_and_count", "at": now}, {"state": "awaiting_materials", "at": now}],
        "created_at": now, "updated_at": now,
        "skill": {"skill_id": skill_id, "display_name": display_name, "package_root": str(root_skill.resolve()), "package_hash": receipt["package_sha256"], "contract_hash": sha256_file(contract_path)},
        "image_settings": {"ratio": ratio, "candidate_count": candidate_count, "scene_count": scene_count},
        "material_slots": slots, "material_hash": None, "prompts": [], "archived_prompts": [], "active_prompt_version": None, "confirmation": None, "paid_batch_confirmation": None, "generation": None,
    }
    save(root, project)
    return public(root, project)


def snapshot(project: dict) -> tuple[list[dict], str]:
    ordered = []
    for slot in sorted(project["material_slots"], key=lambda item: item["position"]):
        files = image_files(Path(slot["final_dir"]))
        count = len(files)
        if count < slot["min_count"] or (slot["max_count"] is not None and count > slot["max_count"]):
            raise PipelineError(f"slot {slot['id']} contains {count} image(s); allowed {slot['min_count']}..{slot['max_count']}")
        slot["files"] = [str(path.resolve()) for path in files]
        for index, path in enumerate(files):
            ordered.append({"slot_id": slot["id"], "slot_position": slot["position"], "file_position": index, "path": str(path.resolve()), "sha256": sha256_file(path)})
    canonical = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ordered, sha256_text(canonical)


def lock_materials(projects: Path, project_id: str, use_source: bool) -> dict:
    root, project = load(projects, project_id)
    require_state(project, {"awaiting_materials", "materials_ready", "awaiting_prompt_confirmation", "ready_for_generation", "awaiting_paid_batch_confirmation", "ready_for_batch_generation"})
    verify_skill(project)
    if use_source:
        for slot in project["material_slots"]:
            for source in image_files(Path(slot["source_dir"])):
                target = Path(slot["final_dir"]) / source.name
                if target.exists() and sha256_file(source) != sha256_file(target):
                    raise PipelineError(f"refusing to overwrite different final image: {target}")
                if not target.exists():
                    shutil.copy2(source, target)
    materials, digest = snapshot(project)
    changed = project["material_hash"] not in (None, digest)
    project["materials"] = materials
    project["material_hash"] = digest
    if changed:
        project["archived_prompts"].extend(project["prompts"])
        project["prompts"] = []
        project["active_prompt_version"] = None
        project["confirmation"] = None
        project["paid_batch_confirmation"] = None
    transition(project, "materials_ready")
    save(root, project)
    return public(root, project)


def set_prompt(projects: Path, project_id: str, content: str, author: str) -> dict:
    root, project = load(projects, project_id)
    require_state(project, {"materials_ready", "awaiting_prompt_confirmation"})
    verify_skill(project)
    if not content.strip():
        raise PipelineError("prompt must not be empty")
    for prompt in project["prompts"]:
        prompt["status"] = "superseded"
    version = len(project["prompts"]) + 1
    prompt = {"version": version, "author": author, "content": content.strip(), "length": len(content.strip()), "prompt_hash": sha256_text(content.strip()), "material_hash": project["material_hash"], "status": "draft", "created_at": utc_now()}
    project["prompts"].append(prompt)
    project["active_prompt_version"] = version
    project["confirmation"] = None
    project["paid_batch_confirmation"] = None
    write_json(root / "prompts" / f"v{version}.json", prompt)
    transition(project, "awaiting_prompt_confirmation")
    save(root, project)
    return public(root, project)


def confirm_prompt(projects: Path, project_id: str) -> dict:
    root, project = load(projects, project_id)
    require_state(project, {"awaiting_prompt_confirmation"})
    _, current_material_hash = snapshot(project)
    prompt = project["prompts"][project["active_prompt_version"] - 1]
    if current_material_hash != project["material_hash"] or prompt["material_hash"] != current_material_hash:
        raise PipelineError("materials changed after prompt authoring")
    prompt["status"] = "confirmed"
    prompt["confirmed_at"] = utc_now()
    project["confirmation"] = {"prompt_version": prompt["version"], "prompt_hash": prompt["prompt_hash"], "material_hash": current_material_hash, "confirmed_at": prompt["confirmed_at"]}
    write_json(root / "prompts" / "confirmed.json", prompt)
    batch = project["image_settings"]["candidate_count"] * project["image_settings"]["scene_count"] > 1
    transition(project, "awaiting_paid_batch_confirmation" if batch else "ready_for_generation")
    save(root, project)
    return public(root, project)


def confirm_paid_batch(projects: Path, project_id: str) -> dict:
    root, project = load(projects, project_id)
    require_state(project, {"awaiting_paid_batch_confirmation"})
    project["paid_batch_confirmation"] = {"confirmed": True, "at": utc_now()}
    transition(project, "ready_for_batch_generation")
    save(root, project)
    return public(root, project)


def start_generation(projects: Path, project_id: str, dry_run: bool) -> dict:
    root, project = load(projects, project_id)
    require_state(project, {"ready_for_generation", "ready_for_batch_generation"})
    verify_skill(project)
    materials, current_material_hash = snapshot(project)
    prompt = project["prompts"][project["active_prompt_version"] - 1]
    confirmation = project["confirmation"] or {}
    if current_material_hash != confirmation.get("material_hash") or sha256_text(prompt["content"]) != confirmation.get("prompt_hash"):
        raise PipelineError("prompt or materials changed after confirmation")
    total = project["image_settings"]["candidate_count"] * project["image_settings"]["scene_count"]
    entry = "generate_image" if total == 1 else "batch-image-generation"
    manifest = {"dry_run": dry_run, "entry": entry, "image_ratio": project["image_settings"]["ratio"], "reference_images": [item["path"] for item in materials], "prompt_version": prompt["version"], "prompt_hash": prompt["prompt_hash"], "material_hash": current_material_hash, "scene_count": project["image_settings"]["scene_count"], "candidate_count": project["image_settings"]["candidate_count"], "automatic_retry": False, "automatic_visual_ranking": False}
    project["generation"] = {"status": "dry_run_ready" if dry_run else "ready_for_external_submission", "manifest": manifest, "started_at": utc_now()}
    write_json(root / "execution" / "manifest.json", manifest)
    transition(project, "generating")
    save(root, project)
    return public(root, project)


def public(root: Path, project: dict) -> dict:
    return {"project_id": project["project_id"], "state": project["state"], "project_dir": str(root.resolve()), "project_dir_link_target": root.resolve().as_posix(), "material_directories": [{"id": slot["id"], "required": slot["required"], "source_dir": slot["source_dir"], "source_dir_link_target": Path(slot["source_dir"]).as_posix(), "final_dir": slot["final_dir"], "final_dir_link_target": Path(slot["final_dir"]).as_posix()} for slot in project["material_slots"]], "image_settings": project["image_settings"], "active_prompt_version": project["active_prompt_version"], "generation": project["generation"]}


def prompt_value(args: argparse.Namespace) -> str:
    return args.file.read_text(encoding="utf-8-sig") if args.file else args.text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS)
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS)
    sub = parser.add_subparsers(dest="command", required=True)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("--project-id")
    create_parser.add_argument("--skill-id", required=True)
    create_parser.add_argument("--display-name", required=True)
    create_parser.add_argument("--ratio", required=True)
    create_parser.add_argument("--candidate-count", type=int, required=True)
    create_parser.add_argument("--scene-count", type=int, required=True)
    create_parser.add_argument("--skill-confirmed", action="store_true")
    for name in ("lock-materials", "confirm-prompt", "confirm-paid-batch", "show"):
        command = sub.add_parser(name)
        command.add_argument("project_id")
        if name == "lock-materials": command.add_argument("--use-source", action="store_true")
    prompt_parser = sub.add_parser("set-prompt")
    prompt_parser.add_argument("project_id")
    prompt_parser.add_argument("--text")
    prompt_parser.add_argument("--file", type=Path)
    prompt_parser.add_argument("--author", default="business_skill")
    start_parser = sub.add_parser("start-generation")
    start_parser.add_argument("project_id")
    start_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create": result = create(args.projects_root, args.skills_root, args.project_id, args.skill_id, args.display_name, args.ratio, args.candidate_count, args.scene_count, args.skill_confirmed)
        elif args.command == "lock-materials": result = lock_materials(args.projects_root, args.project_id, args.use_source)
        elif args.command == "set-prompt": result = set_prompt(args.projects_root, args.project_id, prompt_value(args), args.author)
        elif args.command == "confirm-prompt": result = confirm_prompt(args.projects_root, args.project_id)
        elif args.command == "confirm-paid-batch": result = confirm_paid_batch(args.projects_root, args.project_id)
        elif args.command == "start-generation": result = start_generation(args.projects_root, args.project_id, args.dry_run)
        else:
            root, project = load(args.projects_root, args.project_id); result = public(root, project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, PipelineError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

