---
name: default-video-generation
description: Generate videos from text, one or more images, explicit first and last frames, reference videos, or reference audio through the default Seedance/Dreamina video tool. Use for text-to-video, image-to-video, multi-image storytelling, or all-around mixed-media reference generation.
---

# Default Video Generation

Call `generate_video` with only the user's non-empty `prompt` and ordered local `images`, `videos`, and `audios` paths. Video generation always uses Seedance/Dreamina; never switch providers. Do not expose provider, model, credential, concurrency, timeout, output, or log settings.

Treat every call as an external operation that may consume provider credits. Preserve explicit ratio, resolution, duration, quality, and supported model preferences in the prompt. Reject audio without any image or video. The router validates local files, limits, audio duration, current CLI help, submission state, and downloads.

The router normalizes every local image input and proportionally resizes any image whose longest edge exceeds 1920 px before provider submission. This applies to first/last frames, multiframe inputs, and multimodal images without overwriting originals.

For one independent video task, call the tool directly without creating a child agent. For two or more independent media tasks, create a pending queue and keep up to `min(6, runtime_available_child_slots)` child agents active. Give each child exactly one task and forbid further delegation; refill immediately when a child ends, then aggregate task IDs, terminal states, provider/model, attempts, and output paths without returning credentials or full logs.
