---
name: codex-dt-video-prompt
description: Optimize Chinese Dreamina/Seedance video prompts before generation. Use when the user provides images and a short prompt and wants to generate a video, animate an image, create image-to-video output, or asks for video generation without a stronger project-specific pipeline. Do not use inside a repository or package that has its own active image-to-video/video pipeline guidance; local project AGENTS.md and explicitly named project skills take priority. After prompt optimization, ask the user to choose whether to call default-video-generation.
---

# Codex DT Video Prompt

Use this skill as a default prompt optimization layer, not as the paid generation submitter.

## Priority

- Follow the current workspace or project `AGENTS.md` first.
- Do not trigger this skill when a project-specific video pipeline applies, for example a Codex_CS project skill or another package-level image-to-video workflow.
- Use this skill for general workspaces where the user wants video generation from images, a short text idea, or both.
- Use this skill first whenever the agent needs to supplement, newly write, repair, optimize, or rewrite a video prompt before generation, unless stronger project-specific video pipeline guidance applies.
- If the user explicitly asks to bypass optimization and generate directly, use `default-video-generation` instead.

## Workflow

1. Read the user's prompt, ordered images, requested duration, ratio, style, camera motion, audio preference, and any constraints.
2. If images are local raster files and visual understanding is needed, create previews with the configured Codex preview tool first; inspect only previews whose longest edge is at most 1024 px.
3. Write one concise Chinese video prompt suitable for Dreamina/Seedance. Preserve the user's subject, identity, composition, duration, ratio, and motion preferences.
4. For ordered references, use bare Chinese labels tied strictly to input order: `图片1`, `图片2`, `视频1`, `音频1`, and so on. Do not write mention-chip forms such as `@图片1`, `@Image 1`, `@视频1`, or `@Video 1`.
5. Never reorder references by filename, visual layout, natural-language alias, or inferred importance. The ordered media list that will be passed to `default-video-generation` is authoritative.
6. Include camera movement, subject action, scene change, style, temporal progression, and negative constraints only when useful.
7. When the user did not specify audio, add `不生成音乐，仅生成音效。`
8. Present the optimized prompt and ask the user to choose: revise the prompt, or use `default-video-generation` with the optimized prompt and the original ordered media.

## Optional References

For complex image-to-video prompt authoring, read these files from the Codex_DT checkout:

- `docs/codex_authoring_workflow.md`
- `docs/subagent_image_worker.md`
- `third_party/seedance-forge/references/structure-guide.md`

Do not submit paid Dreamina/Seedance jobs from this skill. Generation is performed only after the user chooses to continue with `default-video-generation`.
