---
name: default-image-generation
description: Generate images, draw from text, and edit, composite, or transform one or more local reference images through the unified Codex media router. Uses the default route order unless the user explicitly names a supported image route.
---

# Default Image Generation

Before any generation or edit, require the user to explicitly choose one supported image ratio: `21:9`, `16:9`, `3:2`, `4:3`, `1:1`, `3:4`, `2:3`, or `9:16`. If the user has not explicitly supplied a ratio, stop and ask for it; never infer it from reference images, prompt content, orientation, prior turns, filenames, or provider defaults. Do not call the paid tool until the ratio is explicit.

Call `generate_image` with the user's non-empty `prompt`, ordered local `images` paths, required structured `image_ratio`, and structured `image_resolution` only when explicitly selected (`1K`, `2K`, or `4K`). When omitted, GPT image routes default to `4K` and Gemini image routes default to `2K`; Dreamina retains its `1K` default. Do not proactively ask the user to choose a provider. When the current user explicitly names one supported, unambiguous route, also pass its exact ID through `image_provider`; this skips the default order and uses only that route, without fallback to another route. Supported IDs are `comfly-gemini-lite`, `comfly-gpt-image-2`, `apimart-gpt-image-2`, `google-gemini-image`, and `dreamina-image`. Ask a minimal clarification for ambiguous names such as plain `Gemini`. Do not expose or request arbitrary provider, model, API URL, credential, concurrency, timeout, output, or log settings, and never invoke a provider-specific skill directly.

On success, use the image and original-file resource returned by the tool. Do not reconstruct image Markdown or file links from the raw `output_path`; on Windows, a backslash path is not a portable image URI.

Treat every call as an external operation that may consume provider credits. Do not run speculative generations. Pass ratio through `image_ratio` and resolution through `image_resolution`; preserve only other explicit quality or model preferences in the prompt.

The router normalizes local reference-image orientation and proportionally resizes any image whose longest edge exceeds 1920 px before provider submission. It never overwrites the original image.

For one independent image task, call the tool directly without creating a child agent. For two or more independent media tasks, create a pending queue and keep up to `min(6, runtime_available_child_slots)` child agents active. Give each child exactly one task and forbid further delegation; refill a freed slot immediately and aggregate each private `result.json` without returning credentials or full logs.

In the default route mode, the router allows each image backend at most 120 seconds, then records `provider_timeout` and tries the next backend serially. With an explicit `image_provider`, the selected backend is the only attempt. The complete image task has a 300-second deadline. If the tool returns `task_timeout`, the child agent must report that failure and exit immediately so its queue slot can be refilled; do not wait, retry, or invoke another provider yourself.

Never inspect a local raster original directly. Resolve the preview converter from `CODEX_HOME`, falling back to the current user's `.codex/tools/Convert-CodexImagePreview.ps1`, create a preview with `-MaxLongEdge 1024`, and inspect only that preview.
