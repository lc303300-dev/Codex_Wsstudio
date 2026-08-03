---
name: gemini-api
description: Generate or edit still images independently through the official Google Gemini API using gemini-3.1-flash-image. Use for Google-direct Gemini image generation and multi-reference image editing without Antigravity CLI, Dreamina, Seedance, APIMart, or provider fallback.
---

# Gemini Official API

Use only `../CLI/Gemini-API/gemini_api.py`. Never call another provider as fallback.

## Configure

Read `GEMINI_API_KEY` from `../.codex-image-private/.env`. Environment variables override the file. Optional proxy settings are `HTTP_PROXY` and `HTTPS_PROXY`.

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Gemini-API/run.ps1 --prompt "<prompt>" --image <ref.png> --out ../.codex-image-private/outputs/gemini-api/output.jpg --log ../.codex-image-private/logs/gemini-api/run.json --aspect-ratio 16:9
```

Omit `--image` for text-to-image. Repeat it in semantic reference order for editing or composition. Use `--prompt-file` for long prompts.

## Rules

- Use Google endpoint `https://generativelanguage.googleapis.com/v1beta/interactions`.
- Use `gemini-3.1-flash-image`, JPEG, `1K`, and `16:9` by default.
- Keep the API key and base64 image bodies out of logs.
- Preserve identity, count, composition, and style explicitly when references are supplied.
- Do not call Gemini CLI, Seedance CLI, or GPT API after a failure.

See `references/provider.md` for the extracted request and response contract.

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls `view_image` on any local raster image, create a preview with `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1` and inspect only that preview. The preview's longest edge must be at most 512 px. Keep original image paths only for filesystem operations and provider inputs.
