# Subagent image worker protocol

Use this protocol when the main Codex agent delegates one image to a subagent.

## Scope

One subagent handles exactly one manifest and writes only:

- `manifests/<id>.json`
- `prompts/<id>.prompt.txt`

For batch-isolated tasks these paths are:

- `manifests/<batch>/<id>.json`
- `prompts/<batch>/<id>.prompt.txt`

The subagent must not edit shared scripts, third-party repositories, review pages, or other image manifests.

## Required inputs

- Manifest path.
- Preview image path.
- Original source image path.
- Repository root.
- User-confirmed duration in the assigned manifest.
- User-provided or auto-inferred ratio in the assigned manifest.
- Per-image user motion/camera brief from `manifest.user_requirements.motion_zh` when present.

## Required tools and projects

The subagent must use:

- Codex visual inspection on the 1024px preview image.
- `.claude/skills/video-director-prompt` for platform-neutral directing, including first-frame blocking, visible performance, camera, physics, lighting, sound, continuity, and optional community techniques.
- `third_party/seedance-forge` for similar prompt corpus search.
- `third_party/seedance-2.0-prompt-skill` rules for Dreamina/Seedance prompt compilation and validation.

The subagent must not modify either `third_party` project.

## Image inspection rules

- Inspect only the preview image.
- Do not inspect the original raster image directly.
- Before inspection, verify the assigned preview metadata reports `preview_width`, `preview_height`, and `max_long_edge` no greater than 1024. Stop and ask the main agent to regenerate the preview if this cannot be verified.
- Use the original image path only in the manifest and final generation metadata.
- Do not write credentials, cookies, provider responses, caches, or temporary files outside `.codex-image-private/`.

## Worker steps

1. Read `docs/codex_authoring_workflow.md`.
2. Read the assigned manifest.
3. Inspect the assigned preview image.
4. Fill the manifest's Chinese visual description:
   - `photo_type`
   - `visual.description_zh`
   - `visual.main_subjects`
   - `visual.fixed_elements`
   - `visual.movable_elements`
   - `visual.lighting`
   - `visual.composition`
   - `visual.risks`
5. Fill `motion_plan` in Chinese.
   - Preserve every concrete user motion/camera requirement from `manifest.user_requirements.motion_zh`.
   - If that field is empty but the task prompt says the original user request included per-image actions, stop and ask the main agent to populate it.
6. Build a platform-neutral directing plan before writing platform syntax. Preserve useful professional English terms with Chinese explanations.
7. Add Chinese and English forge search queries. Treat corpus version fields as source metadata, never as a model-selection signal.
8. Run corpus search only when the brief needs structural inspiration or a comparable example:

   ```powershell
   python scripts/update_forge_matches.py --manifests <temp-dir-or-single-manifest-workaround>
   ```

   If using the batch updater is inconvenient for a single manifest, run:

   ```powershell
   python scripts/search_forge.py --manifest manifests/<id>.json --top 5 --preview-chars 900
   ```

   Then write the returned matches into `forge.matches`.

9. Extract patterns from the matches as inspiration. Do not copy full corpus prompts.
10. Write a Chinese Dreamina CLI image-to-video prompt to `prompts/<id>.prompt.txt`.
11. Compile using the local multimodal reference rules:
    - `surface = "dreamina-cli"` for this local pipeline
    - `mode = "multimodal"`
    - references are bound by ordered `multimodal2video --image`, `--video`, and `--audio` arguments
    - the CLI-facing prompt must refer to ordered uploads with bare Chinese labels such as `图片1`, `图片2`, `视频1`, and `音频1`
    - do not type Web UI mention-chip forms such as `@Image 1`, `@图片1`, `@Video 1`, or `@视频1`
    - never infer reference order from filenames or prompt prose when ordered CLI arguments are present
    - `transport_role = "reference_image"`
    - use the existing `duration` and `ratio`; do not invent or change them
    - final prompt is Chinese
12. Keep the request's model policy unchanged: Seedance 2.5 by default; Seedance 2.0 only with recorded current-user explicit selection. Never infer or fall back to 2.0.
13. Set `prompt.status = "ready_for_review"`.
14. Optional quality check: run the repository CLI-aware validator for the assigned manifest:

    ```powershell
    python scripts/validate_batch.py --manifests manifests/<batch>/<id>.json
    ```

    Do not use the upstream mqrox validator result as the final status for `dreamina-cli`; this pipeline binds ordered references with `multimodal2video --image <path>`, and prompt labels such as `图片1` must match that upload order.

15. If validation is run, ensure the validator result is written to `mqrox_compile.validator`. Do not block review-page output on warnings.

## Prompt requirements

The prompt must be Chinese and copy-ready for Dreamina CLI. It should use this shape unless the image requires a simpler variant:

```text
图片1作为首帧参考和唯一视觉参考。从原始构图开始，让画面在保持主体、空间结构、材质、色彩和光线关系不变的前提下自然动起来。

镜头运动：...

动态元素：...

保持不变：...

画面约束：...
```

## Final response to main agent

Return a concise summary:

- image id
- manifest path
- prompt path
- photo type
- forge match count
- validator status
- any issue needing main-agent attention
