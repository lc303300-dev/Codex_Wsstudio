#!/usr/bin/env python3
"""Build a minimal image + Chinese Dreamina prompt review page."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_prompt(manifest: dict[str, Any]) -> str:
    prompt_file = manifest.get("prompt", {}).get("file")
    if not prompt_file:
        return ""
    path = Path(prompt_file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def asset_prefix(out: Path) -> str:
    out_dir = out.parent.resolve()
    try:
        relative = out_dir.relative_to(ROOT)
    except ValueError:
        return ""
    depth = len(relative.parts)
    return "../" * depth


def render_card(path: Path, manifest: dict[str, Any], prefix: str) -> str:
    prompt_text = read_prompt(manifest)
    item_id = html.escape(str(manifest.get("id", path.stem)))

    # Render every ordered reference asset, not only the manifest's primary
    # preview. Multi-image video tasks rely on this order for CLI binding.
    media_blocks: list[str] = []
    assets = manifest.get("mqrox_compile", {}).get("asset_manifest", {}).get("assets", [])
    if isinstance(assets, list) and assets:
        for index, asset in enumerate(assets, start=1):
            source = str(asset.get("source", "")) if isinstance(asset, dict) else ""
            source_stem = Path(source).stem
            manifest_preview = Path(str(manifest.get("preview_image", "")))
            batch_preview_dir = (ROOT / manifest_preview.parent) if not manifest_preview.is_absolute() else manifest_preview.parent
            preview_candidates = sorted(batch_preview_dir.glob(f"{source_stem}.*.preview.png"))
            preview_src = ""
            if preview_candidates:
                preview_src = rel(str(preview_candidates[0]))
            elif index == 1:
                preview_src = rel(manifest.get("preview_image"))
            label = html.escape(str(asset.get("tag") or f"图片{index}")) if isinstance(asset, dict) else f"图片{index}"
            if preview_src:
                media_blocks.append(
                    f'<div class="ref"><div class="ref-label">{label}</div>'
                    f'<img src="{html.escape(prefix + preview_src)}" alt="{item_id} {label}"></div>'
                )
    if not media_blocks:
        preview_src = rel(manifest.get("preview_image"))
        if preview_src:
            media_blocks.append(f'<div class="ref"><img src="{html.escape(prefix + preview_src)}" alt="{item_id}"></div>')

    return f"""
    <section class="card">
      <div class="media">{''.join(media_blocks)}</div>
      <div class="content">
        <h3>给即梦 AI 的中文提示词</h3>
        <pre>{html.escape(prompt_text or "提示词文件不存在或为空")}</pre>
      </div>
    </section>
    """


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review/index.html.")
    parser.add_argument("--manifests", type=Path, default=ROOT / "manifests")
    parser.add_argument("--out", type=Path, default=ROOT / "review" / "index.html")
    parser.add_argument("--batch", help="Batch/task id. Uses manifests/<batch> and review/<batch>/index.html.")
    args = parser.parse_args()
    if args.batch:
        args.manifests = ROOT / "manifests" / args.batch
        args.out = ROOT / "review" / args.batch / "index.html"

    if args.manifests.is_file():
        manifest_paths = [args.manifests]
    else:
        manifest_paths = sorted(path for path in args.manifests.glob("*.json") if path.is_file())
    prefix = asset_prefix(args.out)
    cards = [render_card(path, read_json(path), prefix) for path in manifest_paths]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>即梦图生视频提示词确认</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; background: #f6f7f9; color: #17191f; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    h3 {{ font-size: 15px; margin: 0 0 8px; }}
    p {{ line-height: 1.65; margin: 0; }}
    .card {{ display: grid; grid-template-columns: minmax(260px, 40%) 1fr; gap: 20px; background: white; border: 1px solid #dfe3ea; border-radius: 8px; padding: 16px; margin-bottom: 18px; }}
    .media {{ display: grid; gap: 12px; align-content: start; }}
    .media img {{ width: 100%; height: auto; border-radius: 6px; border: 1px solid #e1e5ec; display: block; }}
    .ref-label {{ font-size: 12px; color: #4b5563; margin-bottom: 4px; }}
    .content {{ min-width: 0; }}
    pre {{ white-space: pre-wrap; line-height: 1.65; background: #111827; color: #f9fafb; padding: 14px; border-radius: 6px; overflow-x: auto; }}
    @media (max-width: 860px) {{
      main {{ padding: 14px; }}
      .card {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>即梦图生视频提示词确认</h1>
    {''.join(cards) if cards else '<p>暂无 manifest。请先完成预览生成和 Codex 视觉识别。</p>'}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
