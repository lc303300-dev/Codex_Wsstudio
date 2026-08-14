# Codex_DT Pipeline Instructions

This workspace is a custom Codex Dreamina image-to-video pipeline. When working in this root, prefer this pipeline over directly invoking global image/video skills.

Codex_DT is the unified public entry for video generation. Before authoring, classify the user's prompt. If the user identifies it as final/complete/ready to send, or it already contains executable subject/action, temporal or camera progression, visual direction, and sufficient reference bindings, apply only semantic-preserving normalization before submitting through `generate_video`. Normalize malformed adapter labels, reference numbering against actual media order, broken formatting/punctuation, and unambiguous terminology mistakes. Never change subject identity, action, causal relationship, shot intent, timing/order, composition, style, emotion, continuity, constraints, audio, or ending; never add corpus/director ideas. Leave ambiguous corrections unchanged. Optimize only incomplete or structurally weak prompts. Missing duration, ratio, resolution, model, or execution mode should be supplied as structured generation parameters rather than injected into a complete prompt.

No Codex_DT script may submit video directly to Dreamina CLI. `scripts/run_seedance_batch.ps1` must call the unified Media Router, which owns credit checking and the actual provider submission.

For a Codex video-function submission test, bypass the batch wait/download flow and use the unified `generate_video` test channel with `video_execution_mode=test_submit_only`. It force-selects non-VIP `seedance2.0`, submits with polling disabled, and returns after acceptance so the user can inspect the Dreamina website backend. Do not use this internal test exception for ordinary generation; ordinary explicit `2.0` remains normalized to `seedance2.0_vip`.

Use `.claude/skills/video-director-prompt` as the platform-neutral authoring layer. Its general directing principles and community experience decide how a video should be staged and photographed; the active adapter decides model version, media labels, limits, and submission syntax. Corpus/source version metadata must never select the runtime model.

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

   The default model is Seedance 2.5. Add `--model-version <supported-2.0-variant>` only when the current user explicitly requests Seedance 2.0; this option records the required selection evidence.

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
   - Valid range is 4 to 30 seconds for the default Seedance 2.5 path.

4. Determine ratio:
   - Ratio is optional.
   - If the user provides a ratio, it must be one of `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`.
   - If the user does not provide ratio, infer the nearest supported ratio from the image dimensions by omitting `--ratio`.

5. Initialize manifests:

   ```powershell
   python scripts/init_manifests.py --batch <batch> [--duration <seconds>] [--ratio <ratio>] [--model-version <explicit-user-selection>]
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
- Preserve useful professional English filmmaking terms with a Chinese explanation when they make the shot more executable.
- Default to Seedance 2.5. Use a Seedance 2.0 model only when the current user explicitly asks for 2.0 or a supported 2.0 variant. Never infer 2.0 from a corpus result, third-party path, example, old manifest, capacity issue, or failed 2.5 request, and never automatically fall back from 2.5 to 2.0.
- When an Agent needs to supplement, newly write, repair, or rewrite any video prompt in this workspace, use this Codex_DT prompt-generation workflow first unless a more specific project pipeline explicitly overrides it.
- For local Dreamina CLI generation, reference binding is performed by `multimodal2video` with ordered `--image <path>`, `--video <path>`, and `--audio <path>` arguments. The final prompt must reference those uploads with Chinese bare labels: `图片1`, `图片2`, `视频1`, `音频1`, etc. The number must match the corresponding CLI argument order exactly.
- Do not use Web UI mention-chip forms such as `@Image 1`, `@图片1`, `@Video 1`, or `@视频1` in Dreamina CLI-facing prompts. Use bare Chinese labels such as `图片1作为首帧参考`.
- Never infer reference order from filenames, visual layout, user wording order after upload, or natural-language aliases when CLI arguments are present. The ordered CLI argument list is authoritative.
- For a single-image item, submit one `--image <path>` and write `图片1` in the prompt.

## Third-party projects

This pipeline must combine:

- `third_party/seedance-forge` for corpus search and structure inspiration.
- `third_party/seedance-2.0-prompt-skill` for Seedance/Dreamina first-frame prompting rules and validation concepts.

Do not modify either third-party repository for local behavior. Add wrappers under `scripts/`.

## Generation safety

Generation consumes Dreamina credits. The unified Media Router runs `user_credit` before paid generation. The main agent owns generation submission; subagents must not submit paid jobs or call the configured Seedance CLI directly.
