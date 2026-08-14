from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from skill_package import FORBIDDEN_EXECUTION, SECRET_PATTERN, TERMINAL_METADATA, WINDOWS_ABSOLUTE_PATH


ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5")


def decode_source(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError("Unable to decode source as UTF-8, GB18030, GBK, or Big5")


def extract_metadata(text: str) -> tuple[str | None, str | None, str]:
    frontmatter = re.match(r"\A---\s*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if frontmatter:
        block = frontmatter.group(1)
        name = re.search(r"(?m)^\s*name\s*:\s*(.+?)\s*$", block)
        description = re.search(r"(?m)^\s*description\s*:\s*(.+?)\s*$", block)
        return (
            name.group(1).strip().strip("\"'") if name else None,
            description.group(1).strip().strip("\"'") if description else None,
            "yaml_frontmatter",
        )
    name = re.search(r"(?im)^#+\s*name\s*$\s*([^#\r\n][^\r\n]*)", text)
    description = re.search(r"(?im)^#+\s*description\s*$\s*([^#\r\n][^\r\n]*)", text)
    return (
        name.group(1).strip() if name else None,
        description.group(1).strip() if description else None,
        "legacy_heading" if name or description else "unknown",
    )


def inspect(path: Path) -> dict:
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError("Source must be a file")
    text, encoding = decode_source(path)
    name, description, metadata_format = extract_metadata(text)
    wrappers = sorted(set(re.findall(r"(?im)^.*(?:START OF FILE|END OF FILE).*?$", text)))
    media_hints = {
        "image": len(re.findall(r"(?i)图片|图\s*\d+|image\s*\d+", text)),
        "video": len(re.findall(r"(?i)参考视频|视频素材|video\s*\d+|footage", text)),
        "audio": len(re.findall(r"(?i)音频|音乐|配乐|audio\s*\d+|music\s*\d+", text)),
    }
    community_hints = len(re.findall(r"(?i)社区|实测|经验|反馈|测试发现|常见问题", text))
    failure_hints = len(re.findall(r"(?i)失败|错误表现|常见错误|问题|崩坏|漂移|穿模|闪烁", text))
    example_hints = len(re.findall(r"(?im)^#+\s*(?:示例|案例|example)|正例|反例", text))
    findings = []
    checks = (
        (bool(wrappers), "EXPORT_WRAPPER", "Source contains exported START/END file wrapper text"),
        (bool(TERMINAL_METADATA.search(text)), "TERMINAL_METADATA", "Source contains terminal execution metadata"),
        (bool(WINDOWS_ABSOLUTE_PATH.search(text)), "ABSOLUTE_PATH", "Source contains a machine-local absolute path"),
        (bool(SECRET_PATTERN.search(text)), "POSSIBLE_SECRET", "Source may contain a credential or authorization value"),
        (bool(FORBIDDEN_EXECUTION.search(text)), "EXECUTION_COUPLING", "Source contains provider, model, CLI, polling, or router execution details"),
        (bool(re.search(r"(?i)\btext2video\b|文生视频", text)), "TEXT2VIDEO_MENTION", "Source mentions a no-reference video mode that cannot be published"),
        (metadata_format != "yaml_frontmatter", "NONSTANDARD_METADATA", "Source does not use standard YAML frontmatter"),
    )
    for active, code, message in checks:
        if active:
            findings.append({"code": code, "message": message})
    return {
        "source": {
            "name": path.name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "encoding": encoding,
        },
        "metadata": {"format": metadata_format, "name": name, "description": description},
        "content_summary": {
            "characters": len(text),
            "lines": len(text.splitlines()),
            "media_hints": media_hints,
            "community_experience_hints": community_hints,
            "failure_case_hints": failure_hints,
            "example_hints": example_hints,
        },
        "export_wrappers": wrappers,
        "findings": findings,
        "next_state": "needs_review",
        "note": "This preflight report does not infer required counts, ordering, or final contract semantics.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect an uploaded legacy video Skill source without modifying it.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = inspect(args.source)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

