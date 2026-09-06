# Codex authoring workflow

This step is performed by Codex, not by a local script, because image recognition is exposed as an agent visual tool.

For each manifest:

1. Inspect `preview_image` with Codex visual tools only, after verifying its longest edge is at most 1024px from the preview metadata. Never open `source_image` with a visual inspection tool.
2. Read `.claude/skills/video-director-prompt/SKILL.md` and its routed references. Build a platform-neutral directing plan covering the first frame, blocking, visible action, camera, performance, physical interaction, lighting, sound, and continuity. Use community or experimental techniques only when the shot benefits from them.
3. Fill `photo_type`, `visual`, and the director-owned portions of `motion_plan`.
4. Run `scripts/compile_environment_motion.py` after visual recognition. If plants, water surfaces, or reflections are detected, it appends only environmental motion guidance and environmental-only corpus queries. It must not add camera, lens, exposure, style, or generic subject-action advice.
5. Fill or refine `forge.queries_zh` / `forge.queries_en`, keeping environment-motion queries separate in intent from camera/directing queries.
6. Run `scripts/update_forge_matches.py` for every shot/video unit. Corpus search is mandatory whenever the search returns one or more matches. For manifests with `environment_motion.detected=true`, the updater applies the environment-motion sanitizer: camera/style/general-action records are discarded and mixed records are reduced to environmental-motion sentences. Skipping corpus is allowed only after the search for that unit returns no matches, and the manifest must record that no-hit result and the queries used. A complete brief is not a reason to skip search.
7. For multi-shot or multi-segment videos, create a separate corpus query and result record for each shot/segment; never reuse one global match set as a substitute for unit-level retrieval. Extract portable directing and structural patterns from matches as inspiration, not copied text. Treat source model/version as provenance metadata only; it must never select the generation model.
8. Compile the directing plan into a Chinese Dreamina CLI prompt using the local multimodal reference rules. Insert the environment-motion section only when the compiler detected a matching visual element.
9. Keep the source image in the asset manifest as the first ordered image reference. In this local CLI pipeline, the actual binding is `multimodal2video` with ordered `--image`, `--video`, and `--audio` arguments. The prompt references those uploads as bare Chinese labels such as `图片1`, `视频1`, and `音频1`. Do not type Web UI mention-chip forms such as `@Image 1`, `@图片1`, `@Video 1`, or `@视频1` into the CLI-facing prompt.
10. Default to Seedance 2.5. Seedance 2.0 is allowed only when request metadata records a current explicit user selection; never choose it from examples, corpus metadata, old manifests, or fallback behavior.
11. Set `prompt.status` to `ready_for_review`.
10. Optional: run `scripts/validate_batch.py` and fix material errors. Validation is a quality check, not a prerequisite for building the user review page.

Duration is mandatory. If no duration has been provided by the user, stop before manifest initialization and ask for it. Ratio is optional: if the user does not provide it, infer the nearest allowed ratio from the image dimensions during manifest initialization. Valid duration range for the default Seedance 2.5 path is 4 to 30 seconds. Supported ratio values are `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`.

Chinese prompt requirements:

- The prompt shown to the user must be Chinese.
- The final prompt sent to Dreamina CLI must be Chinese.
- Internal search keywords may be English, Chinese, or mixed.

Recommended prompt shape:

```text
图片1作为首帧参考和唯一视觉参考。从原始构图开始，让画面在保持主体、空间结构、材质、色彩和光线关系不变的前提下自然动起来。

镜头运动：...

动态元素：...

保持不变：...

画面约束：...
```

## Revising a complete Codex Flow Skill prompt

When a Codex Flow Skill has already produced the complete first draft, do not run the normal incomplete-prompt authoring path. If the user confirms it, submit it unchanged through the owning Flow project. If the user requests any change, follow [prompt_revision_workflow.md](prompt_revision_workflow.md): build a constrained request with `scripts/classify_revision.py`, preserve the Flow workflow context and material order, and return the revised prompt for user confirmation.

Explicit local changes skip the corpus. Ambiguous creative feedback and structural rewrites may search at most three corpus matches. DT never submits media from this revision step.
