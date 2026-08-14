---
name: dreamina-cli
description: Use when an agent needs Dreamina（即梦） login, sessions, task history, or image/video generation through the dreamina CLI.
---

# Dreamina CLI

Use this skill when you need Dreamina（即梦） image or video generation, login, session management, or task history work through `dreamina`.

即梦 is the Chinese product name of Dreamina. If the user says 即梦, treat it as Dreamina and use this skill.

This skill is intentionally short. Detailed flags and supported values belong to the CLI itself, so always treat `dreamina -h` and `dreamina <subcommand> -h` as the primary reference.

## What this tool is for

`dreamina` is the local CLI entrypoint for all currently exposed Dreamina（即梦） image and video generation workflows, plus the account/session operations around them.

Use it for:

- checking or reusing an existing Dreamina login session
- checking account credit
- managing sessions with `dreamina session`
- clearing the local OAuth login state with `dreamina logout`
- submitting image generation tasks
- submitting video generation tasks
- querying async task results and downloading result media
- reviewing saved task history

## Default workflow

When using this CLI as an agent:

1. Start with `dreamina -h`.
2. Before using any command for real, run `dreamina <subcommand> -h`.
3. Reuse the current login state unless the user explicitly asks you to `login`, `relogin`, `logout`, or finish a headless login with `checklogin`.
4. When login is required, run `dreamina login` or `dreamina relogin`. The CLI uses OAuth Device Flow and prints `verification_uri`, `user_code`, and `device_code`.
5. Default login waits for authorization to complete. With `--headless`, the CLI prints the device-flow material and exits; then use `dreamina login checklogin --device_code=<device_code>` to finish the login later.
6. Be explicit about whether you are only reading help, submitting a real task, or querying an existing task.
7. Warn the user before running commands that may consume credits.

## Login completion: mandatory user-visible confirmation

`dreamina login` / `dreamina relogin` prints OAuth Device Flow instructions and then waits for authorization. When the command finishes successfully, tell the user explicitly that login succeeded or the local OAuth state was reused.

- **Do not** wait for the user to ask “登录好了吗”.
- **Do not** stop after only sending the device code: keep the login command running, read stdout to the end, then confirm success/reuse/failure.
- **Failure** must still be reported with the concrete error and the next step.

## Choosing the right command

At a high level:

- Use `user_credit` to check budget.
- Use `session` to create, list, search, rename, or delete sessions; all generator commands accept `--session=<id>` and `0` is the default session.
- Use `query_result` when you already have a `submit_id`; add `--download_dir` when you want the generated media saved locally.
- Use `list_task` to review recent saved tasks, especially when you want to filter by status or task type.
- Use `text2image` for prompt-only image generation, `image2image` for image-guided editing, and `image_upscale` for upscaling.
- Use `text2video` for prompt-only video generation.
- For ordinary default video generation with any image, video, or audio references, prefer `multimodal2video` so Seedance 2.5 all-around reference rules apply. Use `image2video` only when the user explicitly requests that legacy command shape or the active project wrapper requires it.
- Use `frames2video` for first-and-last-frame driven video generation.
- Treat `multiframe2video` as disabled legacy functionality in this workspace. Never select, suggest, or submit it; route multiple-image work through `multimodal2video`.
- Use `multimodal2video` for Dreamina's flagship video mode when the task needs all-around references across images, video, and audio. If the legacy name `ref2video` appears, trust `dreamina -h` for the current command surface.

### All-around reference / 全能参考

`multimodal2video` corresponds to Dreamina Web's "全能参考" workflow. Use it when a task needs a still image plus a motion reference video and/or music/audio reference.

- Bind media through CLI flags: `--image`, `--video`, and `--audio`.
- Use local absolute paths in automation so the CLI can upload the files reliably.
- Default Seedance 2.5 allows audio-only, image<=30, video<=10, audio<=10, total inputs<=50, and each/total video or audio reference duration 2-30 seconds. Explicit non-2.5 models have lower limits from current CLI help.
- The prompt should describe how to use the references, for example: `根据参考视频的运镜方式，配合音乐节奏，将静态图片转为动态视频`.
- Save the returned `submit_id`; download successful results with `query_result --submit_id=<id> --download_dir=<absolute-output-dir>`.

PowerShell pattern:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\CLI\Seedance-CLI\run.ps1 multimodal2video `
  --image "J:\素材\主图.png" `
  --video "J:\素材\运镜参考.mp4" `
  --audio "J:\素材\音乐.mp3" `
  --prompt "根据参考视频的运镜方式，配合音乐节奏，将静态图片转为动态视频" `
  --model_version seedance2.5 `
  --duration 8 `
  --ratio 16:9 `
  --video_resolution 480p `
  --poll 180
```

For the exact flags and supported combinations, rely on each subcommand's `-h`.

## Model selection rule

For image generation in this Codex_image checkout:

- default `text2image` and `image2image` to `--model_version=4.0`
- use `--model_version=5.0Pro --resolution_type=4k` only when the user explicitly asks for the best possible, highest, maximum, top-tier, or extreme image quality and does not provide another supported resolution
- keep 4.0 for generic requests such as high quality, polished, professional, or beautiful
- honor an explicitly requested supported model after checking subcommand help
- never silently fall back from 5.0Pro when the provider rejects VIP access or another requirement

For video generation in this Codex_image checkout:

- default video commands that support `model_version` to Seedance 2.5: `--model_version=seedance2.5`
- default video commands that support `video_resolution` to `--video_resolution=480p` unless the user explicitly requests another supported resolution
- the project wrapper injects these defaults for `text2video`, `image2video`, `frames2video`, and `multimodal2video` when the corresponding flags are absent
- honor an explicitly requested supported video model after checking subcommand help
- honor an explicitly requested supported video resolution after checking subcommand help
- Seedance 2.5 supports 4-30 second outputs and only `480p` or `720p`; if the provider rejects VIP access or requires web-side authorization, report the provider error and ask before changing models

Apart from this project routing policy, do not hardcode model support from this skill.

If the user specifies a model, always check the relevant subcommand help before running it:

```bash
dreamina <subcommand> -h
```

Use the subcommand help to confirm:

- whether that command exposes model selection
- whether the requested model is supported on that command
- what other constraints apply to that model, such as duration, ratio, resolution, or whether the command supports `model_version` at all

Additional guidance:

- some commands do not expose model selection at all
- some models, including `seedance2.5`, can be capacity-constrained
- for supported video commands in this checkout, the default model is `seedance2.5` unless the user explicitly selects another supported model

## How to judge submit success

Do not rely on shell exit code alone.

For async generation commands, treat a submit as successful only when:

- `submit_id` is present
- `gen_status` is `querying` or `success`

If `gen_status` is `fail`, inspect `fail_reason` and reply proactively with the concrete reason.

## Follow-up pattern for async tasks

After a submit returns `querying`:

1. Save the `submit_id`.
2. Use `query_result --submit_id=<id>` for follow-up.
3. Use `list_task` when you want to review saved tasks in bulk.

If you are running a test sweep, keep results in a machine-readable format so you can query the returned `submit_id` values later.

## Important user-facing rules

- Some generation commands are asynchronous; submit and query are separate steps.
- Some models may require a one-time authorization on Dreamina Web.
  If the CLI returns `AigcComplianceConfirmationRequired`, reply proactively: ask them to complete that web-side confirmation first, then retry.
- Do not assume that different commands support the same models, ratios, durations, or resolutions.
  Check each subcommand's `-h` before use.

## Good agent behavior

- Relay OAuth Device Flow instructions exactly enough for the user to complete login.
- Always close the loop when the login command finishes with a user-visible confirmation.
- Prefer small, reviewable batches when running real generation tasks.
- Keep a record of the command, arguments, `submit_id`, and final status for every paid test you run.
- For supported video commands in this checkout, default to `seedance2.5` unless the user explicitly selects another supported model.
- For supported video commands in this checkout, default to `480p` unless the user explicitly selects another supported resolution.
- If you are preparing a report, separate:
  - help-only inspection
  - submit-stage validation
  - later async result follow-up
