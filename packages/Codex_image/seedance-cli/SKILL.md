---
name: seedance-cli
description: Generate images and videos independently through the official Dreamina CLI, including Dreamina image generation with Image 4.0 by default and Image 5.0Pro for explicit maximum-quality requests, plus Seedance 2.5 at 480p by default for supported video workflows. Use for JiMeng/Dreamina/Seedance generation, login, credits, sessions, task queries, and downloads without Gemini or GPT fallback.
---

# Seedance CLI

Use only `../CLI/Seedance-CLI/run.ps1`, which invokes the private binary at `../.codex-image-private/bin/seedance-cli/dreamina.exe`. This is a composite image and video pipeline, but it never calls the other four pipelines.

## Start

Always inspect command help before a real task:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Seedance-CLI/run.ps1 -h
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Seedance-CLI/run.ps1 <subcommand> -h
```

For login, use `../CLI/seedance-login.cmd`. It opens the OAuth page in the Windows system default browser.

## Image Commands

- `text2image`: prompt-only image generation.
- `image2image`: reference-guided image generation/editing.
- `image_upscale`: image upscaling.

## Image Model Routing

- For `text2image` and `image2image`, use `--model_version=4.0` by default. The project wrapper also injects 4.0 when no model flag is supplied.
- Use `--model_version=5.0Pro` only when the user explicitly prioritizes the best possible or maximum image quality. Treat equivalent superlative wording in any language as a strong trigger, including best possible, maximum quality, highest quality, top-tier, or extreme quality.
- Do not switch to 5.0Pro for generic quality language in any language, such as high quality, polished, beautiful, or professional; keep Image 4.0 for those requests.
- When a maximum-quality request does not specify resolution, use `--resolution_type=4k` with 5.0Pro. If the user specifies a resolution, honor it when supported.
- If the user explicitly names another supported image model, honor that choice after checking the current subcommand help.
- 5.0Pro is VIP-only. If it is unavailable, report the provider error and ask before changing models; do not silently fall back to 4.0 or another pipeline.

## Video Commands

- `text2video`: prompt-only video generation.
- `image2video`: animate one main image.
- `frames2video`: first/last-frame control.
- `multimodal2video`: all-around image/video/audio references with Seedance video models.

Treat the CLI's `multiframe2video` command as disabled legacy functionality. Never select, suggest, or submit it; use `multimodal2video` for multiple-image work.

## All-Around Reference / 全能参考

Use `multimodal2video` for Dreamina Web's "全能参考" mode. It uploads local image, video, and audio files and binds them through explicit CLI flags, not through typed prompt labels.

- Use absolute local paths when possible, especially in automated workflows.
- Use `--image` for main/reference images, `--video` for motion or video references, and `--audio` for music/audio references.
- At least one image or video is required.
- Default Seedance 2.5 allows up to 30 images, 10 videos, 10 audio files, and 50 total reference inputs; video/audio inputs must be 2-30 seconds. Explicit non-2.5 models have lower limits from current CLI help.
- Check every local file with `Test-Path -LiteralPath` before submission.
- Keep `submit_id` and query/download later with `query_result`.

PowerShell example:

```powershell
$InputDir = "J:\素材"
$OutputDir = "J:\输出"
$Image = Join-Path $InputDir "主图.png"
$RefVideo = Join-Path $InputDir "运镜参考.mp4"
$Bgm = Join-Path $InputDir "音乐.mp3"
foreach ($Path in @($Image, $RefVideo, $Bgm)) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "Missing local input: $Path" }
}
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Seedance-CLI/run.ps1 multimodal2video `
    --image $Image `
    --video $RefVideo `
    --audio $Bgm `
    --prompt "根据参考视频的运镜方式，配合音乐节奏，将静态图片转为动态视频" `
    --model_version seedance2.5 `
    --duration 8 `
    --ratio 16:9 `
    --video_resolution 480p `
    --poll 180
```

## Video Model Routing

- For video commands that support `--model_version`, use Seedance 2.5 by default: `--model_version=seedance2.5`. The project wrapper also injects this value when no video model flag is supplied.
- This default applies to `text2video`, `image2video`, `frames2video`, and `multimodal2video`.
- Unless the user explicitly requests another supported resolution, use `--video_resolution=480p`. The project wrapper injects this value when no video resolution flag is supplied.
- Seedance 2.5 supports 4-30 second outputs and only `480p` or `720p` resolution.
- Honor an explicitly requested supported video model after checking the current subcommand help.
- Honor an explicitly requested supported video resolution after checking the current subcommand help.
- Do not assume VIP availability from the project configuration alone. If the provider rejects the model or requires web-side authorization, report the provider error and ask before changing models.

## Operational Rules

- Run `<subcommand> -h` to validate current model names, flags, ratios, duration, and resolution.
- Warn before any generation because it consumes credits.
- Use `user_credit` before expensive video generation.
- Use `query_result --submit_id <id> --download_dir <dir>` until async jobs reach a terminal state.
- Keep image and video outputs under `../.codex-image-private/outputs/seedance-cli/` unless the user explicitly requests an external destination.
- Do not call Gemini API, Gemini CLI, or GPT API after failure.

See `references/provider.md` and the bundled official `../CLI/Seedance-CLI/skill/SKILL.md`.

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls `view_image` on any local raster image, create a preview with `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1` and inspect only that preview. The preview's longest edge must be at most 1024 px. Keep original image paths only for filesystem operations and provider inputs.
