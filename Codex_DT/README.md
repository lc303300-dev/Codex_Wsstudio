# Codex Dreamina I2V Pipeline

This workspace builds a Codex-orchestrated pipeline for turning one or more still images into Chinese Dreamina/Jimeng image-to-video prompts, then generating videos after user confirmation.

`AGENTS.md` defines the default trigger rules for this workspace. When images are submitted here, Codex should use this pipeline first instead of directly invoking the global Seedance CLI.

## Third-party projects used

- `third_party/seedance-forge`: real Seedance prompt corpus and structural examples.
- `third_party/seedance-2.0-prompt-skill`: Seedance/Dreamina prompt rules, platform adapters, asset manifest schema, and validator.

## Deploy on a New Machine

When `Codex_DT` and `Codex_image` are checked out together under the shared `Copy` root, use the one-command deployment entry from that root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap-new-machine.ps1
```

This installs the portable Codex configuration, the bundled preview converter, unified media skills/plugin, the Dreamina CLI when missing, and both project-local configurations. API keys remain machine-private and are configured separately with hidden input.

After copying this repository to a new machine, ask Codex:

```text
帮我部署这个项目
```

Codex should run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_project.ps1
```

If the preview converter or Dreamina/Seedance CLI lives in a different location on the new machine, provide the paths:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_project.ps1 -PreviewTool C:\path\Convert-CodexImagePreview.ps1 -SeedanceCli C:\path\Seedance-CLI\run.ps1
```

The script creates the runtime directory skeleton, writes machine-local settings to `config/pipeline.local.json`, validates Python/PowerShell and bundled third-party resources, checks the Codex preview tool, and verifies Dreamina CLI login/credit with `user_credit` without submitting paid generation.

## Workflow

For the normal text-first flow, start by recording the user's Chinese video brief and creating an empty image drop folder:

```powershell
python scripts/start_text_batch.py --name window --duration 5 --request "帮我生成视频，5秒，镜头运动幅度不要太大。"
```

Show the printed `image_drop_dir` to the user as a clickable local path and ask them to put source images into that folder. After the user confirms the files are there, continue with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
python scripts/init_manifests.py --batch <batch>
python scripts/make_subagent_tasks.py --batch <batch> --status draft
```

`init_manifests.py --batch <batch>` reads `.codex-image-private/batches/<batch>/request.json` when present, so the saved duration, optional ratio, and user motion/camera brief are copied into every manifest.

For a brand-new Codex task where the opening message contains multiple image attachments, use the lightweight bootstrap first and stop before visual inspection, subagent dispatch, or paid generation:

```powershell
python scripts/bootstrap_dialog_batch.py --name window --duration 5 --images C:\path\image1.png C:\path\image2.png C:\path\image3.png
```

Then continue from the printed `bootstrap_batch=...` value in a follow-up turn. This also applies to opening messages that say `全自动生成视频`; the first turn should only import/initialize, because doing multi-image upload handling, vision, subagent creation, and Dreamina submission in one newly-created task can leave the desktop app stuck on connecting/thinking.

1. Create one isolated batch/task directory set. In the normal text-first flow, use `scripts/start_text_batch.py` and wait for the user to place images in `inputs/<batch>/`. If image files are already available, copy them into `inputs/<batch>/`. Batch ids should include the current hour and minute, for example `20260730-1534-window`; `scripts/new_batch.py --name window` generates that shape automatically. If the user dropped multiple images directly into the opening Codex dialog, use `scripts/import_dialog_images.py` so the pipeline waits for attachment files to become readable and size-stable before copying them. Duration is required for every batch. Ratio is optional; if omitted, the pipeline chooses the nearest allowed ratio from the image dimensions.
2. Run `scripts/prepare_previews.ps1 -Batch <batch>` to create 512px previews in `previews/<batch>/`.
3. Run `scripts/init_manifests.py --batch <batch> [--duration <seconds>] [--ratio <ratio>]` to create draft manifests from `previews/<batch>/_previews.json`. Text-first batches can omit duration/ratio because they are read from private batch request metadata.
4. Generate subagent task prompts with `scripts/make_subagent_tasks.py --batch <batch> --status draft`.
5. The main Codex agent must actually spawn one subagent per task prompt. Task prompt files are only dispatch inputs; they do not execute work by themselves.
6. After subagents finish, run `scripts/finalize_review.py --batch <batch>` to build the review page and print final status. This default path does not require main-agent image inspection, subagent-output review, validator gating, or result recording.
7. Show `review/<batch>/index.html` for user confirmation. The page only shows each image and its Chinese Dreamina/Jimeng prompt.
8. After user confirmation, run `scripts/run_seedance_batch.ps1 -Batch <batch> -Yes` to submit confirmed items to Dreamina CLI. If the user explicitly asks for auto-generation, for example `自动生成视频` or `全自动生成视频`, skip the confirmation wait and use `scripts/finalize_review.py --batch <batch> --auto-generate`.

For parallel processing, the main Codex agent can delegate each manifest to a subagent. Generate per-image task prompts with:

```powershell
 # First-turn bootstrap for multiple images dropped into a new task
python scripts/bootstrap_dialog_batch.py --name window --duration 5 --images C:\path\image1.png C:\path\image2.png

 # Dialog-safe import for images dropped into the opening Codex message
python scripts/import_dialog_images.py --name window --images C:\path\image1.png C:\path\image2.png

 # Text-first user request; then ask the user to place images in the printed folder
python scripts/start_text_batch.py --name window --duration 5 --request "帮我生成视频，5秒，镜头运动幅度不要太大。"

 # For already-stable local files, create an isolated batch and copy images
python scripts/new_batch.py --name window --images C:\path\image1.png C:\path\image2.png

 # Use the printed batch=YYYYMMDD-HHMM-window value in the next commands.
 # 5-second videos with ratio inferred from each image
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch 20260730-1534-window
python scripts/init_manifests.py --batch 20260730-1534-window
python scripts/make_subagent_tasks.py --batch 20260730-1534-window --status draft
```

Each subagent follows `docs/subagent_image_worker.md` and writes only its assigned manifest and prompt file. The main agent should not inspect source images or re-review every prompt by default; it should build the user confirmation page:

```powershell
python scripts/finalize_review.py --batch 20260730-1534-window
```

For explicit auto-generation requests, build the review record and submit directly:

```powershell
python scripts/finalize_review.py --batch 20260730-1534-window --auto-generate
```

Optional diagnostics and bookkeeping remain available:

```powershell
python scripts/make_subagent_tasks.py --batch 20260730-1534-window --status draft --write-jobs
python scripts/record_image_dispatch.py --batch 20260730-1534-window --image-id 001-image1 --agent-id <codex-task-id>
python scripts/finalize_review.py --batch 20260730-1534-window --validate --check-subagent-outputs --record-results
```

## Directory layout

```text
inputs/<batch>/      Original images supplied by the user for one task.
previews/<batch>/    512px Codex-readable previews.
manifests/<batch>/   Per-image structured descriptions, prompt metadata, and confirmation state.
prompts/<batch>/     Chinese Dreamina/Jimeng prompt text files.
review/<batch>/      HTML confirmation page with only images and Chinese prompts.
outputs/<batch>/videos/  Downloaded user video artifacts.
.codex-image-private/batches/<batch>/  Request metadata, subagent tasks, task state, temporary manifests, provider logs, and submission records.
scripts/     Pipeline helper scripts.
third_party/ Selected GitHub projects.
docs/        Codex authoring instructions.
```

## Important constraints

- User-visible prompts and final Dreamina CLI prompts are Chinese.
- Allowed ratios are `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`. `adaptive` is not used in this pipeline.
- For local Dreamina CLI generation, source images are bound by ordered `multimodal2video --image <path>` arguments. The final CLI prompt uses bare labels such as `图片1`, never Web UI mention syntax such as `@图片1`.
- Codex image inspection must use previews generated by `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1`; the longest edge must be at most 512px, and original images are only used for file operations and Dreamina CLI inputs.
- Credentials, cookies, authorization data, provider logs, caches, temporary manifests, submission records, and other runtime state stay under `.codex-image-private/`.
- Generation consumes Dreamina credits. Check `user_credit` before a paid batch.
- Do not modify `third_party` projects for local pipeline behavior; add wrappers in `scripts/`.
