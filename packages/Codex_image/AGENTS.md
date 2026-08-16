# Unified Codex Media Tools

## Default Tools

Expose and use only these default media tools for ordinary requests:

- `generate_image` through `$default-image-generation` for text-to-image and one-or-more-image editing.
- `generate_video` through `$default-video-generation` for text, image, video, or audio referenced video generation.

Do not proactively ask ordinary users to select a provider. Provider skills remain source-maintenance and explicit-diagnostic assets only; their `agents/openai.yaml` files must keep `allow_implicit_invocation: false`. If the current user explicitly names one supported, unambiguous image route, honor it through the unified `generate_image.image_provider` field; never invoke the provider-specific skill or adapter directly.

Both tools are external open-world operations that may consume provider credits. Offline validation, status checks, request construction, help commands, and dry runs are allowed. Before any real generation or edit, confirm the user's requested generation is intentional. Before a new network acceptance suite or failure/concurrency test that may consume extra credits, list the maximum paid requests and obtain explicit confirmation.

## Image Routing

Every image generation or edit requires an explicit user-selected ratio before any paid submission. Supported ratios are `21:9`, `16:9`, `3:2`, `4:3`, `1:1`, `3:4`, `2:3`, and `9:16`. Never infer a ratio from reference images, image orientation, prompt context, earlier tasks, filenames, or provider defaults. The public `generate_image` contract requires structured `image_ratio`; missing or unsupported values fail as `input_error` before any provider is called.

When the user does not explicitly select a route, route each image task strictly serially in this default order and stop after the first validated non-empty local image:

1. `comfly-gemini-lite` -> the model declared in `config/media-router.defaults.json` (currently `gemini-3.1-flash-image-preview`)
2. `comfly-gpt-image-2-all` -> `gpt-image-2-all`
3. `comfly-gpt-image-2` -> `gpt-image-2`
4. `apimart-gpt-image-2` -> APIMart `gpt-image-2`
5. `google-gemini-image` -> official Gemini image API
6. `dreamina-image` -> Dreamina Image 4.0 by default

The list above is a default order, not a mandatory path. When the current user explicitly requests one supported route, pass its exact adapter ID through `generate_image.image_provider`, skip every other route, and do not fall back elsewhere if it fails. Supported public route IDs are the six IDs listed above. Do not guess ambiguous names: for example, plain `Gemini` is ambiguous between the Comfly Gemini and official Google Gemini routes. Unsupported, non-image, or config-disabled routes fail as `input_error` before any paid provider call.

Never race, hedge, or parallelize adapters within one image task. Comfly models are separate logical adapters with independent concurrency, health, metrics, logs, and circuit state. The Comfly common layer performs exactly one fixed-model request and never loops over models.

Fallback only for `auth_unavailable`, `quota_unavailable`, `definite_provider_failure`, `download_failure`, `timeout_before_submit`, and `provider_timeout`. A provider has at most 120 seconds from capacity wait through delivery of a validated local image; on expiry, terminate its active process/request, record `provider_timeout`, and continue to the next provider. Stop on `input_error`, `policy_rejection`, `indeterminate_submission`, or `cancelled`. Mark indeterminate submission as `needs_review`; never retry it or continue to another paid provider automatically.

An image task has a 300-second overall deadline starting when routing begins. Cap each provider budget by the remaining task time. On expiry, stop routing, persist terminal `failed` state with `task_timeout`, return immediately, and do not invoke another provider.

For Dreamina images, use Image 4.0 by default. Use Image 5.0Pro at 4K only when the user explicitly asks for best possible, highest, maximum, top-tier, or extreme image quality, unless another supported setting is explicit.

## Video Routing

Use only Dreamina/Seedance for video. Select the CLI subcommand from inputs:

| Input | Command |
| --- | --- |
| prompt only | `text2video` |
| one image | `multimodal2video` |
| exactly two images with explicit first/last-frame semantics | `frames2video` |
| multiple images without first/last semantics | `multimodal2video` |
| any video, or audio plus an image/video | `multimodal2video` |
| prompt plus audio only | reject as `input_error` |

Validate local files before submit. For the default Seedance 2.5 `multimodal2video` path, allow at most 30 images, 10 videos, 10 audio files, and 50 total reference inputs; audio-only is allowed by Seedance 2.5, and every video/audio input must be 2-30 seconds. For explicit non-2.5 models, keep their current CLI limits. Run the chosen subcommand `-h` before every real submit.

For supported video commands, default to Seedance 2.5 (`seedance2.5`) and `480p`. Seedance 2.5 supports 4-30 second outputs and only `480p` or `720p` resolution. Honor supported model, ratio, resolution, and duration preferences that the user explicitly includes. Treat `multiframe2video` as a disabled legacy CLI command: never select, suggest, expose, or submit it. Route ordinary multiple-image work through `multimodal2video`.

Save `submit_id`. Query and download successful tasks with `query_result --submit_id <id> --download_dir <private-output-dir>`. If a submission may have happened but its outcome is unknown, mark `needs_review` and do not submit again.

For an explicit Codex video-function test, use the existing `generate_video` tool with `video_execution_mode=test_submit_only`; do not add or expose a provider-specific test tool. This real paid channel must force the non-VIP CLI model `seedance2.0`, `720p`, and `--poll 0`, regardless of ordinary model inputs. Treat `submit_id` plus `gen_status=querying|success` as terminal `submitted`, persist the ID, and never call `query_result`, wait, or download. Report only `测试任务已发送，请到即梦网站后台查看结果。` Ordinary generation remains Seedance 2.5 by default, while ordinary explicit `2.0` continues to normalize to `seedance2.0_vip`.

## Concurrency and Multi-Task Scheduling

Every adapter defaults to `max_concurrency: 6`. `dreamina-image` and `dreamina-video` share the `seedance-cli` capacity key, so their combined concurrency never exceeds 6. Use project-private cross-process slot leases under `.codex-image-private/locks/providers/<capacity-key>/`.

Explicit `batch-image-generation` workflows use the deterministic Codex_Batch_Image scheduler, not child Agents. Its 10 task slots do not raise adapter capacity; provider leases and limits remain authoritative. For other work, one media task uses the default tool directly and two or more independent tasks follow this child-Agent protocol:

1. Build a pending queue and stable private task manifests.
2. Keep at most `min(6, runtime_available_child_slots)` child Agents active.
3. Give each child one bounded task and explicitly prohibit creating child Agents.
4. Refill a freed slot immediately until the queue is empty.
5. Read validated `result.json` files and summarize task ID, terminal state, provider/model, attempts, and output path without credentials or full logs.

Every image child Agent must stop and return its failed result immediately when the router reports `task_timeout` at 300 seconds so its queue slot is released and can be refilled.

Python scheduler tests may simulate this rolling protocol, but Python must not pretend to spawn Codex Agents.

## Setup and Status

At the beginning of a new task in this checkout, run the safe update wrapper before editing:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-task.ps1
```

It fetches remote state and only performs a fast-forward pull when the worktree is clean and the local branch has not diverged. It never stashes, resets, merges, rebases, or overwrites local changes.

On the first interaction with this checkout, run the read-only status helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\get-pipeline-setup-status.ps1 -CheckLogin
```

When the user says `帮我部署这个项目`, deploy the checkout automatically with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy-project.ps1
```

This is the default new-computer deployment entry. It registers only the unified global tools and plugin, checks live provider readiness, and marks ready tools complete. Do not install provider skills globally during ordinary deployment; only `default-image-generation`, `default-video-generation`, and `codex-media-plugin` should become globally available for normal use.

The returned schema separates `tools` from `providers`. A tool is `ready` when registered and all expected adapters are ready, `degraded` when registered with at least one usable adapter, and `unavailable` when unregistered or without a usable backend. Video has one backend, so Dreamina unavailable means the video tool is unavailable.

Register unified project-managed artifacts with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\register-default-media-tools.ps1
```

Default registration installs only `default-image-generation`, `default-video-generation`, and `codex-media-plugin`. Use `-ProviderSkills` only for explicit provider development. Never delete an existing skill without `.codex-image-registration.json` whose `source_root` matches this checkout.

Credentials remain in `.codex-image-private/.env`: `COMFLY_API_KEY`, `APIMART_API_KEY`, and `GEMINI_API_KEY`. If a required key is missing, warn that chat may retain content and recommend a dedicated revocable key before using the hidden-prompt `configure-api-key.ps1` helper. Never place keys in command arguments, source, logs, state, or registration metadata. CLI logins remain project-private binaries plus provider-managed sessions.

State uses schema v2 with `registered_tools`, `setup_completed_tools`, and `provider_readiness`. Before migrating an owned v1 state, save a sanitized backup under `.codex-image-private/validation/state-migration/`, then write v2 atomically. Keep v1 field reading compatible for at least one version cycle.

## Image Reading Guardrail

Never inspect a local raster original directly. First create a preview with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:CODEX_HOME\tools\Convert-CodexImagePreview.ps1" -InputPath <image-path> -MaxLongEdge 1024
```

Inspect only the generated preview whose longest edge is at most 1024 px. Use original paths only for file operations and provider inputs. Put video frames and visual validation artifacts under `.codex-image-private/validation/`.

## Private Runtime and Safe Logs

Treat `.codex-image-private/` as the only project-local private/disposable runtime root. Store credentials, downloaded CLIs, jobs, outputs, logs, locks, caches, validation artifacts, provider health, metrics, and circuit state only there. Use stable jobs under `.codex-image-private/jobs/<batch-id>/<task-id>/`.

Log prompts as `<redacted>`, character count, and SHA-256 only. Never log API keys, Authorization, Bearer tokens, cookies, original media bytes, Base64, multipart bodies, full provider error bodies, or unfiltered Dreamina transcripts. Provider logs may retain only safe identifiers, adapter/model, endpoint, status code, remote URL, media counts, output path/bytes, duration, and normalized failure class.

Successful output must be non-empty and match an accepted media signature. Stage output in the destination directory and atomically replace only after validation; preserve existing outputs on failure. `success` never repeats, `failed` retries only on explicit user request, `needs_review` never retries automatically, and stale `running` tasks resume query only when a provider task ID exists.

## Provider Image Inputs

Before sending any local image to an API or CLI provider, normalize EXIF orientation and inspect its dimensions. If its longest edge exceeds 1920 px, resize it proportionally so the longest edge is exactly 1920 px. Images at or below 1920 px remain unchanged. Never overwrite the user's original; store resized provider inputs only under the task's `.codex-image-private/jobs/<batch-id>/<task-id>/inputs/` directory. Apply this rule to image generation/editing references and every image used by video commands, including first/last frames, multiframe, and multimodal inputs.

Keep public source free of `__pycache__`, `.pyc`, logs, test outputs, and media. Set `PYTHONDONTWRITEBYTECODE=1` or use Python `-B` on every entry. Before packaging, remove `.codex-image-private/` and run `test-share-ready.ps1`; do not claim sanitation until it passes. Never modify or delete any external backup directory supplied by the user.
