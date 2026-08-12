# Codex authoring workflow

This step is performed by Codex, not by a local script, because image recognition is exposed as an agent visual tool.

For each manifest:

1. Inspect `preview_image` with Codex visual tools only, after verifying its longest edge is at most 1024px from the preview metadata. Never open `source_image` with a visual inspection tool.
2. Fill `photo_type`, `visual`, `motion_plan`, and `forge.queries_zh` / `forge.queries_en`.
3. Run `scripts/update_forge_matches.py` so `seedance-forge` matches are stored in the manifest.
4. Extract structure from matches as inspiration, not copied text.
5. Write a Chinese Dreamina CLI prompt to `prompt.file` using the mqrox multimodal reference image-to-video pattern.
6. Keep the source image in the mqrox asset manifest as the first ordered image reference. In this local CLI pipeline, the actual binding is `multimodal2video` with ordered `--image`, `--video`, and `--audio` arguments. The prompt references those uploads as bare Chinese labels such as `图片1`, `视频1`, and `音频1`. Do not type Web UI mention-chip forms such as `@Image 1`, `@图片1`, `@Video 1`, or `@视频1` into the CLI-facing prompt.
7. Set `prompt.status` to `ready_for_review`.
8. Optional: run `scripts/validate_batch.py` and fix material errors. Validation is a quality check, not a prerequisite for building the user review page.

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
