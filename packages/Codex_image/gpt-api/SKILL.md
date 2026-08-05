---
name: gpt-api
description: Generate or edit still images independently with APIMart GPT Image 2. Use for APIMart gpt-image-2 text-to-image or multi-reference image generation without Google Gemini API, Antigravity CLI, Dreamina, Seedance, or provider fallback.
---

# GPT APIMart API

Use only `../CLI/Gpt-API/gpt_api.py`. Never call another pipeline as fallback.

## Configure

Read `APIMART_API_KEY` from `../.codex-image-private/.env`. Environment variables override the file. Optional proxy settings are `HTTP_PROXY` and `HTTPS_PROXY`.

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Gpt-API/run.ps1 --prompt "<prompt>" --image <ref.png> --out ../.codex-image-private/outputs/gpt-api/output.png --log ../.codex-image-private/logs/gpt-api/run.json --size 16:9 --resolution 1k
```

Omit `--image` for text-to-image. Repeat `--image` or `--image-url` in reference order.

## Rules

- Submit to APIMart `/v1/images/generations`, then poll `/v1/tasks/{task_id}`.
- Use `gpt-image-2`, `n=1`, `16:9`, and `1k` by default.
- Keep `official_fallback=false` to prevent provider-side channel switching.
- Accept at most 16 references; local images must be at most 20 MB each.
- Download the temporary result URL immediately and retain the task metadata in the log.
- Do not call Gemini API, Gemini CLI, or Seedance CLI after failure.

See `references/provider.md` for the APIMart contract.

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls `view_image` on any local raster image, create a preview with `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1` and inspect only that preview. The preview's longest edge must be at most 1024 px. Keep original image paths only for filesystem operations and provider inputs.
