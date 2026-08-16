---
name: comfly-api
description: Generate or edit still images independently through Comfly's OpenAI-compatible image API. Use for Comfly text-to-image or local-image editing with explicit Gemini 1K/2K/4K models or gpt-image-2, without Google, APIMart, Dreamina, or any other provider fallback.
---

# Comfly API

Use only `../CLI/Comfly-API/comfly_api.py`. Never call another provider as fallback.

## Configure

Read `COMFLY_API_KEY` from `../.codex-image-private/.env`. Environment variables override the file. Optional proxy settings are `HTTP_PROXY` and `HTTPS_PROXY`.

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Comfly-API/run.ps1 --prompt "<prompt>" --image <ref.png> --out ../.codex-image-private/outputs/comfly-api/output.png --log ../.codex-image-private/logs/comfly-api/run.json --size 1024x1024
```

Omit `--image` for text-to-image. Supply one or more local images for editing and repeat `--image` in semantic order. Use `--prompt-file` for long prompts. Run `--dry-run` before the first potentially billable request.

## Rules

- Submit prompt-only requests to `POST https://ai.comfly.org/v1/images/generations` as UTF-8 JSON with `Content-Type: application/json; charset=utf-8`.
- Submit image edits to `POST https://ai.comfly.org/v1/images/edits` as multipart form data with repeated `image` fields.
- Gemini resolution models are `gemini-3.1-flash-image-preview` (1K), `gemini-3.1-flash-image-preview-2k` (2K), and `gemini-3.1-flash-image-preview-4k` (4K).
- GPT uses only `gpt-image-2`; `gpt-image-2-all` is retired.
- For GPT Image 2, convert the selected ratio and 1K/2K/4K class to a concrete pixel `size`; do not send the unsupported `resolution` field.
- Make exactly one explicit-model request. This diagnostic adapter does not perform model fallback.
- Read the result from `data[0].url`; do not depend on `b64_json`.
- Download result URLs with the required browser `User-Agent`, image `Accept`, and `Referer: https://ai.comfly.org/` headers.
- Keep the API key, Authorization header, original image bytes, Base64 content, and full prompt out of logs.
- Do not call Gemini API, Gemini CLI, Seedance CLI, GPT API, or any provider outside Comfly after failure.

Read `references/provider.md` for the request, response, fallback, and logging contract.

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls `view_image` on any local raster image, create a preview with `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1` and inspect only that preview. The preview's longest edge must be at most 1024 px. Keep original image paths only for filesystem operations and provider inputs.
