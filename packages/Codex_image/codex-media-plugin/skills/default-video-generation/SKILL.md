---
name: default-video-generation
description: Generate videos from text, one or more images, explicit first and last frames, reference videos, or reference audio through the default Seedance/Dreamina video tool. Use for text-to-video, image-to-video, multi-image storytelling, or all-around mixed-media reference generation.
---

# Default Video Generation

Call `generate_video` with only the user's non-empty `prompt` and ordered local `images`, `videos`, and `audios` paths. Video generation always uses Seedance/Dreamina; never switch providers. Do not expose provider, model, credential, concurrency, timeout, output, or log settings.

The default route is Seedance 2.5 in all-around reference / `multimodal2video` mode at `480p` whenever the request includes any image, video, or audio reference and no user setting overrides it. Prompt-only requests still use `text2video`. Seedance 2.5 supports 4-30 second output, `480p` or `720p`, up to 30 images, 10 videos, 10 audio files, and 50 total reference inputs. Preserve explicit user choices only when they are supported by the selected command/model.

When the user does not specify an audio preference, append the default audio instruction `不生成音乐，仅生成音效。` to the final video prompt. If the user explicitly requests music or another audio treatment, follow that request instead.

If the agent needs to newly write, expand, repair, or rewrite a video prompt before generation, first use the global `codex-dt-video-prompt` prompt optimization layer unless a project-specific video pipeline is active. For ordered references, keep CLI-facing prompt labels strict: `图片1` means the first `images` path passed to `generate_video`, `图片2` means the second, `视频1` means the first `videos` path, and `音频1` means the first `audios` path. Do not write mention-chip forms such as `@图片1` or `@Image 1`.

Treat every call as an external operation that may consume provider credits. Preserve explicit ratio, resolution, duration, quality, and supported model preferences in the prompt. Audio-only reference input is supported only by the default Seedance 2.5 `multimodal2video` route; reject it when the user explicitly selects another model. The router validates local files, limits, audio duration, current CLI help, submission state, and downloads.

The router normalizes every local image input and proportionally resizes any image whose longest edge exceeds 1920 px before provider submission. This applies to first/last frames, multiframe inputs, and multimodal images without overwriting originals.

For one independent video task, call the tool directly without creating a child agent. For two or more independent media tasks, create a pending queue and keep up to `min(6, runtime_available_child_slots)` child agents active. Give each child exactly one task and forbid further delegation; refill immediately when a child ends, then aggregate task IDs, terminal states, provider/model, attempts, and output paths without returning credentials or full logs.
