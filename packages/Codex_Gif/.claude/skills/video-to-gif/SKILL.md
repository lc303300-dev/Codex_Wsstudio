---
name: video-to-gif
description: Convert local videos to GIF files with a quality-first, staged fallback pipeline under a size cap. Use for video-to-GIF conversion, batch GIF generation from local files, GIFs under a size limit, and Windows PowerShell GIF workflows.
---

# Video to GIF

Use this skill when the user wants to convert one or more local videos into GIF files, especially when the request mentions a maximum size, batch conversion, an output folder, or preserving aspect ratio.

## Entry Point

Run `run-video-to-gif.ps1` from the `packages/Codex_Gif` checkout. The wrapper prepares the private runtime and invokes the conversion pipeline.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-video-to-gif.ps1 -InputDir .\input -OutputDir .\output -MaxSizeMB 10
```

## Behavior

- Use `ffmpeg` and `ffprobe` from `PATH`.
- Use `gifsicle` when installed for optional optimization and lossy compression.
- Preserve the source aspect ratio.
- Try staged quality settings and stop at the first candidate within the requested size cap.
- Keep temporary files and reports under `.codex-image-private/`.
- Report the pipeline failure reason if no candidate fits the requested cap.
