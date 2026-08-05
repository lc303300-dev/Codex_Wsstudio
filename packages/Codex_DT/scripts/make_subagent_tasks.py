#!/usr/bin/env python3
"""Create per-image subagent task prompts from manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_paths import PRIVATE_RUNTIME_ROOT, existing_runtime_path, runtime_path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_CONCURRENT_IMAGES = 3
OPEN_JOB_STATUSES = {"dispatched", "recorded"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_existing_jobs(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def run_status(images: list[dict[str, Any]]) -> str:
    if images and all(image.get("status") == "recorded" for image in images):
        return "images_recorded"
    if images and all(image.get("status") in {"dispatched", "recorded"} for image in images):
        return "images_dispatched"
    return "tasks_recorded"


def task_text(manifest_path: Path, manifest: dict[str, Any]) -> str:
    image_id = manifest.get("id", manifest_path.stem)
    preview = manifest.get("preview_image", "")
    source = manifest.get("source_image", "")
    preview_metadata = Path(preview).with_suffix(".json").as_posix() if preview else ""
    prompt_file = manifest.get("prompt", {}).get("file", f"prompts/{image_id}.prompt.txt")
    duration = manifest.get("mqrox_compile", {}).get("duration")
    ratio = manifest.get("mqrox_compile", {}).get("ratio")
    user_motion = manifest.get("user_requirements", {}).get("motion_zh", "").strip()
    user_motion_section = (
        f"\n用户指定动作/镜头要求：\n{user_motion}\n"
        if user_motion
        else "\n用户指定动作/镜头要求：未在 manifest 中记录；如原始用户消息包含每图动作，主 Agent 必须先写入 manifest.user_requirements.motion_zh 再分派。\n"
    )
    workspace_root = Path(__file__).resolve().parents[1].as_posix()
    return f"""你是当前 Codex 图生视频管线的单图处理子 Agent。只处理这一张图片，不要编辑其他图片的 manifest/prompt，不要修改 third_party、scripts、README 或 review 页面。

工作区根目录：
{workspace_root}

必须阅读并遵守：
docs/subagent_image_worker.md
docs/codex_authoring_workflow.md

必须结合这两个 GitHub 项目：
1. third_party/seedance-forge：用于检索相似 Seedance 真实提示词语料，并提炼镜头、动作、环境动效写法。
2. third_party/seedance-2.0-prompt-skill：用于按照 Seedance/Dreamina multimodal reference image-to-video 规则编译中文提示词，并用 validator 校验；本地 CLI 的图片绑定来自 multimodal2video 的有序 `--image` 参数，CLI-facing prompt 应写 `图片1`，不要使用 `@Image 1` 或 `@图片1`。

你的唯一输入：
- image id: {image_id}
- manifest: {manifest_path.as_posix()}
- preview image: {preview}
- preview metadata: {preview_metadata}
- original source image: {source}
- prompt output: {prompt_file}
- user-confirmed duration: {duration} 秒
- user-provided or auto-inferred ratio: {ratio}
{user_motion_section}

任务：
1. 先从 preview 元数据确认最长边不超过 1024px，再只视觉检查 preview image；不要直接检查 original source image。若无法确认预览尺寸，停止并通知主 Agent 重新生成。
2. 填写 manifest 里的 photo_type、visual、motion_plan、forge queries。
3. 使用 seedance-forge 检索相似语料，把 matches 写回 manifest，保留 sourceLink，并提炼 extracted_patterns。
4. 按 mqrox/build-seedance2-prompts 的 multimodal reference 规则，写一份中文即梦 CLI 图生视频提示词到 {prompt_file}。
5. 最终提示词必须是中文，用户确认页看到的也是中文。
6. 更新 mqrox_compile.asset_manifest，确保 source、duration、ratio、resolution 一致；必须使用 manifest 中已有的时长和比例，不要自行改时长或比例。最终写给 CLI 的中文提示词不要包含 `@Image 1` 或 `@图片1`，应使用 `图片1` 指代第一个 `--image` 绑定的参考图。
7. 设置 prompt.status = "ready_for_review"。
8. 可选质量检查：如果时间允许，运行 python scripts/validate_batch.py --manifests {manifest_path.as_posix()}，把结果保留在 mqrox_compile.validator。不要因为 validator warning 阻止输出；本地 Dreamina CLI 通过 multimodal2video 的 `--image` 顺序绑定参考图，prompt 里必须保留对应的 `图片1` 标签。

输出要求：
- 直接修改 manifest 和 prompt 文件。
- 凭据、cookies、provider 响应、缓存和临时文件只能写入 .codex-image-private/，不得写入 outputs/ 或其他用户产物目录。
- 最后只简要汇报：image id、photo type、forge match count、validator 是否通过、需要主 Agent 注意的问题。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create subagent task prompt files.")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--out", type=Path, default=PRIVATE_RUNTIME_ROOT / "subagent-tasks")
    parser.add_argument("--batch", help="Batch/task id. Uses manifests/<batch> and the private runtime directory.")
    parser.add_argument("--status", default=None, help="Only include manifests with prompt.status equal to this value.")
    parser.add_argument("--max-concurrent-images", type=int, default=DEFAULT_MAX_CONCURRENT_IMAGES)
    parser.add_argument("--write-jobs", action="store_true", help="Optional bookkeeping: write private batch image_jobs.json.")
    parser.add_argument("--force", action="store_true", help="Overwrite task files even when optional jobs were already dispatched or recorded.")
    args = parser.parse_args()
    if args.max_concurrent_images < 1:
        raise SystemExit("--max-concurrent-images must be >= 1.")
    if args.batch:
        args.manifests = ROOT / "manifests" / args.batch
        args.out = runtime_path(args.batch, "subagent-tasks")

    args.out.mkdir(parents=True, exist_ok=True)
    paths = sorted(path for path in args.manifests.glob("*.json") if path.is_file())
    created = 0
    jobs: list[dict[str, Any]] = []
    job_file = runtime_path(args.batch, "image_jobs.json") if args.batch and args.write_jobs else None
    existing_by_id = {}
    if job_file:
        existing_job_file = existing_runtime_path(
            args.batch,
            "image_jobs.json",
            legacy_parts=("outputs", args.batch, "image_jobs.json"),
        )
        existing_jobs = read_existing_jobs(existing_job_file)
        existing_images = existing_jobs.get("images", [])
        blocked = [
            item.get("id")
            for item in existing_images
            if isinstance(item, dict) and item.get("status") in OPEN_JOB_STATUSES
        ]
        if blocked and not args.force:
            raise SystemExit(
                "Refusing to rewrite task files for already dispatched/recorded image jobs: "
                + ", ".join(str(item) for item in blocked)
                + ". Use --force only when intentionally regenerating task prompts."
            )
        existing_by_id = {
            item.get("id"): item
            for item in existing_images
            if isinstance(item, dict) and item.get("id")
        }
    for path in paths:
        manifest = read_json(path)
        status = manifest.get("prompt", {}).get("status")
        if args.status is not None and status != args.status:
            continue
        output = args.out / f"{manifest.get('id', path.stem)}.task.txt"
        output.write_text(task_text(path.relative_to(ROOT), manifest), encoding="utf-8")
        existing = existing_by_id.get(manifest.get("id", path.stem), {})
        jobs.append(
            {
                "id": manifest.get("id", path.stem),
                "status": existing.get("status", "pending"),
                "manifest": path.relative_to(ROOT).as_posix(),
                "prompt_file": manifest.get("prompt", {}).get("file", ""),
                "task_file": output.relative_to(ROOT).as_posix(),
                "dispatch": existing.get("dispatch"),
                "result": existing.get("result"),
            }
        )
        created += 1
    if job_file:
        write_json(
            job_file,
            {
                "batch": args.batch,
                "run_status": "tasks_recorded",
                "max_concurrent_images": args.max_concurrent_images,
                "images": jobs,
            },
        )
        if jobs:
            persisted = read_existing_jobs(job_file)
            persisted["run_status"] = run_status(persisted.get("images", []))
            write_json(job_file, persisted)
    print(f"Created {created} subagent task prompt(s) in {args.out}")
    if job_file:
        print(f"Wrote {job_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
