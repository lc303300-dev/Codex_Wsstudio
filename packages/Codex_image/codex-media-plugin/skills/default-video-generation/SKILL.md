---
name: default-video-generation
description: Execute an already-finalized video prompt through the unified Seedance/Dreamina router. Use as the downstream paid generation layer after Codex_DT has either preserved a complete user prompt or optimized an incomplete one, or when a stronger project pipeline explicitly calls it. Do not independently rewrite prompts.
---

# Default Video Generation

Call `generate_video` with only the user's non-empty `prompt` and ordered local `images`, `videos`, and `audios` paths. Video generation always uses Seedance/Dreamina; never switch providers. Do not expose provider, model, credential, concurrency, timeout, output, or log settings.

Treat the received prompt as finalized after Codex_DT's semantic-preserving normalization. Do not perform another rewrite, translation, reorder, summary, constraint append, or audio append here. Codex_DT owns the complete-vs-incomplete decision and the single permitted normalization/authoring pass.

All supported video commands default to Seedance 2.5. Requests with references use all-around reference / `multimodal2video` mode at `480p`; prompt-only requests use `text2video` and still default to Seedance 2.5. Seedance 2.5 supports 4-30 second output, `480p` or `720p`, up to 30 images, 10 videos, 10 audio files, and 50 total reference inputs.

Use a Seedance 2.0 model only when the user explicitly requests Seedance 2.0 or a specific supported 2.0 variant in the current request. When passing a 2.0 `video_model`, also pass `video_model_selection_source="user_explicit"`. Never select 2.0 because an example, corpus entry, old manifest, provider capacity issue, or failed 2.5 attempt mentions it. Never automatically fall back from 2.5 to 2.0; report the failure instead. Do not pass `video_model` when the user did not choose a model.

When Codex explicitly needs to test whether video submission works, call the same `generate_video` tool with `video_execution_mode="test_submit_only"`. This is a real credit-consuming test channel, so obtain confirmation before submitting. The router must override all ordinary model choices with the non-VIP CLI model `seedance2.0`, force `720p`, and pass `--poll 0`. After receiving both a `submit_id` and provider status `querying` or `success`, return `submitted` immediately. Do not query, wait, or download, and do not claim generation succeeded. Tell the user: `测试任务已发送，请到即梦网站后台查看结果。` Ordinary generation must never use this mode, and ordinary user input `2.0` continues to normalize to `seedance2.0_vip`.

Only the upstream Codex_DT authoring path may add the default audio instruction `不生成音乐，仅生成音效。` while constructing an incomplete prompt. Never append it to an already-finalized prompt in this execution skill.

If prompt authoring is still needed, return control to the global `codex-dt-video-prompt` orchestrator unless a project-specific pipeline is active. For ordered references, keep CLI-facing prompt labels strict: `图片1` means the first `images` path passed to `generate_video`, `图片2` means the second, `视频1` means the first `videos` path, and `音频1` means the first `audios` path. Do not write mention-chip forms such as `@图片1` or `@Image 1`.

Treat every call as an external operation that may consume provider credits. Preserve explicit ratio, resolution, duration, quality, and supported model preferences in the prompt. Audio-only reference input is supported only by the default Seedance 2.5 `multimodal2video` route; reject it when the user explicitly selects another model. The router validates local files, limits, audio duration, current CLI help, submission state, and downloads.

The router normalizes every local image input and proportionally resizes any image whose longest edge exceeds 1920 px before provider submission. This applies to first/last frames, multiframe inputs, and multimodal images without overwriting originals.

For one independent video task, call the tool directly without creating a child agent. For two or more independent media tasks, create a pending queue and keep up to `min(6, runtime_available_child_slots)` child agents active. Give each child exactly one task and forbid further delegation; refill immediately when a child ends, then aggregate task IDs, terminal states, provider/model, attempts, and output paths without returning credentials or full logs.
