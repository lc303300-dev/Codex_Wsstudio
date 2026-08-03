---
name: gemini-cli
description: Generate still images independently through Google Antigravity CLI and its Gemini vision/image capabilities. Use for Antigravity/agy image generation with optional local references, without Google Gemini API, Dreamina, Seedance, APIMart, GPT API, or provider fallback.
---

# Gemini Antigravity CLI

Use only `../CLI/Gemini-CLI/agy_image.py`. Never call another provider as fallback.

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ../CLI/Gemini-CLI/run-image.ps1 --prompt "<prompt>" --image <ref.png> --out ../.codex-image-private/outputs/gemini-cli/output.png --log ../.codex-image-private/logs/gemini-cli/run.json
```

For first-time authentication, use `../CLI/gemini-cli-login.cmd`. Antigravity opens the Windows system default browser and stores the session in Windows Credential Manager.

Repeat `--image` in reference order. Use `--prompt-file` for long prompts.

## Rules

- Invoke the installed `agy.exe` through `agy-proxy.ps1`; never invoke it directly from automation.
- Set `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` from `../.codex-image-private/.env` or the local defaults.
- Give Antigravity an exact absolute output path and require a real local image file.
- Automated headless generation uses `--dangerously-skip-permissions` so the image tool can write to the explicitly allowed output directory; review prompts and output paths before running.
- Keep the Antigravity transcript, exit status, prompt, references, and output path in the log.
- Do not call Gemini API, Seedance CLI, or GPT API after failure.

See `references/provider.md` for installation and authentication details.

## Image Reading Guardrail

Before Codex visually reads, inspects, previews, or calls `view_image` on any local raster image, create a preview with `$CODEX_HOME/tools/Convert-CodexImagePreview.ps1` and inspect only that preview. The preview's longest edge must be at most 512 px. Keep original image paths only for filesystem operations and provider inputs.
