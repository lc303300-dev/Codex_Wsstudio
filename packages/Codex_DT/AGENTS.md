# Codex_DT Pipeline Instructions

This workspace is a custom Codex Dreamina image-to-video pipeline. When working in this root, prefer this pipeline over directly invoking global image/video skills.

Before editing at the beginning of a new task, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-task.ps1
```

The wrapper only fast-forwards a clean, non-diverged checkout. It never overwrites, stashes, resets, merges, or rebases local work.

The global `$CODEX_HOME/AGENTS.md` media-safety rules still apply. In particular:

- All local raster visual inspection must use a generated preview whose longest edge is at most 1024px. Original raster files are file/generation inputs only and must never be opened with a visual inspection tool.
- Credentials, cookies, authorization data, provider logs, caches, temporary manifests, task state, and other generated runtime files belong under `.codex-image-private/`.
- This repository pipeline is the configured workspace wrapper for image-to-video requests. Outside this custom workflow, ordinary media requests use only the unified `generate_image` / `generate_video` router selected by the active workspace.

## Default trigger

If the user asks `帮我部署这个项目`, `部署这个项目`, `初始化部署`, or an equivalent deployment request, run the repository deployment wrapper from the workspace root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_project.ps1
```

If the new machine stores the Codex preview converter or Dreamina/Seedance CLI in non-default paths, pass them explicitly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_project.ps1 -PreviewTool <Convert-CodexImagePreview.ps1> -SeedanceCli <Seedance-CLI/run.ps1>
```

The deployment wrapper must create the runtime directory skeleton, write `config/pipeline.local.json` for machine-local paths, check Python/PowerShell, check third-party prompt resources, check the Codex preview tool, and run a non-paid Dreamina `user_credit` check unless explicitly skipped. Do not copy credentials or provider runtime state into the repository; login/cookie state remains owned by the configured external CLI.

If the user asks for image-to-video generation in text first, for example `帮我生成视频，5秒，镜头运动幅度不要太大`, start a text-first batch before asking for images:

```powershell
python scripts/start_text_batch.py --name <short-description> --duration <seconds> --request "<original-user-request>"
```

Then show the created `inputs/<batch>/` folder as a clickable local path and ask the user to put source images there. Stop until the user confirms the images are in that folder. After that, run preview preparation, manifest initialization, subagent task creation, delegation, and review finalization for the same batch. `init_manifests.py --batch <batch>` automatically reads `.codex-image-private/batches/<batch>/request.json`, so the original Chinese request, duration, optional ratio, and auto-generation flag stay attached to every image manifest.

If the user provides one or more images and asks for any of the following:

- 让图片动起来
- 图生视频
- 即梦测试
- 开始视频生成测试
- 生成 5 秒视频
- 使用当前管线完成视频
- 自动生成视频
- 全自动生成视频
- 自动生成
- 全自动生成
- batch image-to-video / Dreamina / Jimeng / Seedance generation

then use this repository pipeline first. Do not jump directly to the global `seedance-cli` skill unless the current manifest is already `confirmed` and the user is explicitly asking to submit generation.

If the user uses explicit auto-generation wording such as `自动生成视频`, `全自动生成视频`, `自动生成`, or `全自动生成`, skip the user confirmation wait after the review page is built. In that mode, run `scripts/finalize_review.py --batch <batch> --auto-generate`; it auto-confirms reviewable prompts and immediately submits confirmed items to Dreamina CLI.

## Opening-dialog multi-image bootstrap

When a brand-new Codex task starts with multiple image attachments in the user's opening message, do not visually inspect those attachments in the main Agent and do not immediately spawn subagents or submit Dreamina generation in the same first response. The first response must be a lightweight bootstrap:

1. Treat attachment paths as files only.
2. Import them with:

   ```powershell
   python scripts/import_dialog_images.py --name <short-description> --images <image1> [<image2> ...]
   ```

3. Run preview preparation and manifest initialization only if duration is already known:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
   python scripts/init_manifests.py --batch <batch> --duration <seconds> [--ratio <ratio>]
   ```

4. Stop and report the batch id plus the next command. Ask the user to send a follow-up such as `继续生成 <batch>` or `继续全自动生成 <batch>`.

This bootstrap rule applies even when the opening message says `全自动生成视频` or `自动生成`. It avoids the desktop app connecting to a new task while also uploading multiple images, running visual understanding, creating multiple child agents, and submitting paid generation in one initial turn. After the user sends the follow-up, continue from the existing `inputs/<batch>/`, `previews/<batch>/`, and `manifests/<batch>/` folders and then follow the normal pipeline.

## Required pipeline

1. Create a new task/batch id and put source images in `inputs/<batch>/`. The batch id must include the current hour and minute to avoid same-day folder collisions. For text-first requests without images, use:

   ```powershell
   python scripts/start_text_batch.py --name <short-description> --duration <seconds> --request "<original-user-request>"
   ```

   Show the printed `image_drop_dir` to the user as a hyperlink and wait for them to place images there before continuing. If the request uses explicit auto-generation wording, add `--auto-generate`.

   For requests where image paths are already available, prefer `--name <short-description>` so `new_batch.py` creates `YYYYMMDD-HHMM-<name>` automatically.
   If the images were dropped directly into the opening Codex dialog, first import them with the dialog-safe wrapper. This waits for each attachment path to become readable and size-stable before copying, which avoids starting preview/subagent work while the desktop app is still landing multiple files:

   ```powershell
   python scripts/import_dialog_images.py --name <short-description> --images <image1> [<image2> ...]
   ```

   For already-stable local files, prefer:

   ```powershell
   python scripts/new_batch.py --name <short-description> --images <image1> [<image2> ...]
   ```
2. Run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_previews.ps1 -Batch <batch>
   ```

   `prepare_previews.ps1` hard-rejects `-MaxLongEdge` values above 1024. Agents must inspect only the generated `previews/<batch>/` image paths, never `inputs/<batch>/` originals.

3. Determine duration:
   - Duration is mandatory.
   - If the user did not provide duration, ask for it before manifest initialization.
   - Valid range is 4 to 15 seconds.

4. Determine ratio:
   - Ratio is optional.
   - If the user provides a ratio, it must be one of `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`.
   - If the user does not provide ratio, infer the nearest supported ratio from the image dimensions by omitting `--ratio`.

5. Initialize manifests:

   ```powershell
   python scripts/init_manifests.py --batch <batch> [--duration <seconds>] [--ratio <ratio>]
   ```

   For text-first batches, omit `--duration` and `--ratio` unless overriding `.codex-image-private/batches/<batch>/request.json`.

6. Generate subagent task prompts:

   ```powershell
   python scripts/make_subagent_tasks.py --batch <batch> --status draft
   ```

7. Actually delegate one image per subagent when available; generating task prompt files is not sufficient. Spawn one subagent per `.codex-image-private/batches/<batch>/subagent-tasks/*.task.txt`, wait for completion, then build the review page directly from the modified manifests and prompts. The main Agent should not inspect the images or re-review every prompt by default; the user judges correctness from the review page. Each subagent must follow:
   - `docs/subagent_image_worker.md`
   - `docs/codex_authoring_workflow.md`
   Optional: for large batches that need progress tracking, record dispatches with:
   ```powershell
   python scripts/make_subagent_tasks.py --batch <batch> --status draft --write-jobs
   python scripts/record_image_dispatch.py --batch <batch> --image-id <id> --agent-id <codex-task-id>
   ```

8. After subagents complete, run:

   ```powershell
   python scripts/finalize_review.py --batch <batch>
   ```
   `finalize_review.py` builds `review/<batch>/index.html` by default. Validation, subagent-output review, and result recording are optional diagnostic/bookkeeping steps, not required for the normal review-page path.
   For explicit auto-generation requests, run instead:
   ```powershell
   python scripts/finalize_review.py --batch <batch> --auto-generate
   ```

9. Show the user `review/<batch>/index.html` and wait for confirmation, unless this is an explicit auto-generation request.

10. Only after confirmation, set `prompt.status = "confirmed"` and run:

    ```powershell
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_seedance_batch.ps1 -Batch <batch> -Yes
    ```
    In auto-generation mode, `finalize_review.py --auto-generate` performs this confirmation/status update and submission step.

## Prompt rules

- User-visible prompts and final Dreamina CLI prompts must be Chinese.
- For local Dreamina CLI generation, image binding is performed by `multimodal2video` with one or more ordered `--image <path>` arguments. The final prompt must reference those uploads with Chinese labels `图片1`, `图片2`, `图片3`, etc. The number must match the `--image` order exactly.
- Do not use Web UI mention-chip forms such as `@Image 1` or `@图片1` in Dreamina CLI-facing prompts. Use bare Chinese labels such as `图片1作为首帧参考`.
- For a single-image item, submit one `--image <path>` and write `图片1` in the prompt.

## Third-party projects

This pipeline must combine:

- `third_party/seedance-forge` for corpus search and structure inspiration.
- `third_party/seedance-2.0-prompt-skill` for Seedance/Dreamina first-frame prompting rules and validation concepts.

Do not modify either third-party repository for local behavior. Add wrappers under `scripts/`.

## Generation safety

Generation consumes Dreamina credits. Always run `user_credit` through `scripts/run_seedance_batch.ps1` or the configured Seedance CLI before paid generation. The main agent owns generation submission; subagents must not submit paid jobs.
