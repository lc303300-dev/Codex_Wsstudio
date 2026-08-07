# Codex GIF Pipeline

This package provides the default GIF conversion workflow for this workspace.

When the user asks to generate a GIF from a local video, convert videos to GIF, batch convert clips to GIF, or reduce a video to a GIF under a size cap, prefer this package pipeline first.

Use `run-video-to-gif.ps1` as the normal entry point. The wrapper prepares private runtime folders, clears prior loose GIF outputs in the package output root, checks `ffmpeg`/`ffprobe`, and then runs the conversion pipeline.

## Rules

- Keep all private runtime data under `.codex-image-private/`.
- Do not write generated outputs into the repository root.
- If a conversion request cannot fit under the configured size limit, report the failure reason from the pipeline rather than inventing a fallback.
- This package is for video-to-GIF conversion only. It is not a general media router.

## Global registration

Run `register-global-skill.ps1` to install the package as the global `video-to-gif` Codex skill under the active `CODEX_HOME`.
The repository deployment and global sync scripts call it automatically, so the skill is re-registered on other computers after updates.
