#!/usr/bin/env python3
"""Static preflight checks for Seedance 2.5 prompts.

The checks separate official constraints from conservative heuristics. They do
not predict generation quality and do not replace a provider schema check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    basis: str


REF_PATTERNS = {
    "image": re.compile(r"(?<!\w)(?:@|\[)?(?:image|画像|图片)\s*[_#-]?\s*(\d+)\]?", re.IGNORECASE),
    "video": re.compile(r"(?<!\w)(?:@|\[)?(?:video|動画|视频)\s*[_#-]?\s*(\d+)\]?", re.IGNORECASE),
    "audio": re.compile(r"(?<!\w)(?:@|\[)?(?:audio|音声|音频)\s*[_#-]?\s*(\d+)\]?", re.IGNORECASE),
}

MEDIA_LIMITS = {"image": 50, "video": 50, "audio": 50}
TOTAL_REFERENCE_LIMIT = 50
SURFACES = (
    "generic",
    "dreamina",
    "volcengine-zh",
    "byteplus-api",
    "fal",
    "jimeng-zh",
    "muapi",
    "higgsfield",
)
MODES = ("auto", "text", "first-frame", "first-last", "multimodal", "edit", "extend", "stitch")
SURFACE_TAGS = {
    "dreamina": {"image": "@Image {n}", "video": "@Video {n}", "audio": "@Audio {n}"},
    "volcengine-zh": {"image": "@图片{n}", "video": "@视频{n}", "audio": "@音频{n}"},
    "byteplus-api": {"image": "[Image {n}]", "video": "[Video {n}]", "audio": "[Audio {n}]"},
    "fal": {"image": "@Image{n}", "video": "@Video{n}", "audio": "@Audio{n}"},
    "jimeng-zh": {"image": "@图片{n}", "video": "@视频{n}", "audio": "@音频{n}"},
    "muapi": {"image": "@image{n}", "video": "@video{n}", "audio": "@audio{n}"},
    "higgsfield": {"image": "@Image {n}", "video": "@Video {n}", "audio": "@Audio {n}"},
}
ROLE_MODALITY = {
    "first_frame": "image",
    "last_frame": "image",
    "reference_image": "image",
    "reference_video": "video",
    "reference_audio": "audio",
}
PRIMARY_ROLES = {
    "identity",
    "wardrobe",
    "product",
    "environment",
    "composition",
    "style",
    "first_frame",
    "last_frame",
    "motion",
    "camera",
    "timing",
    "effect",
    "voice",
    "music",
    "ambience",
    "edit_source",
    "extension_source",
    "other",
}
CAMERA_GROUPS = {
    "pan": (" pan ", "pans ", "パン", "摇镜", "摇移"),
    "tilt": (" tilt ", "tilts ", "ティルト", "仰拍移动", "俯仰"),
    "dolly": ("dolly", "push-in", "push in", "pull-back", "pull back", "ドリー", "寄る", "引く", "推镜", "拉镜"),
    "track": ("tracking", "track shot", "follow shot", "follow-cam", "追従", "跟拍", "移镜"),
    "orbit": ("orbit", "arc shot", "旋回", "オービット", "环绕"),
    "zoom": (" zoom ", "zooms ", "ズーム", "变焦"),
    "crane": ("crane", "jib", "boom shot", "クレーン", "升降"),
    "handheld": ("handheld", "hand-held", "手持ち", "ハンドヘルド", "手持"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Seedance 2.5 prompt before generation.")
    parser.add_argument("prompt_file", nargs="?", help="UTF-8 prompt file. Reads stdin when omitted.")
    parser.add_argument("--text", help="Prompt text supplied directly instead of a file/stdin.")
    parser.add_argument("--images", type=int, default=None, help="Number of attached images.")
    parser.add_argument("--videos", type=int, default=None, help="Number of attached videos.")
    parser.add_argument("--audios", type=int, default=None, help="Number of attached audios.")
    parser.add_argument("--duration", type=int, default=None, help="Target duration in seconds.")
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="auto",
    )
    parser.add_argument("--surface", choices=SURFACES, default=None, help="Provider/UI tag profile.")
    parser.add_argument("--manifest", help="UTF-8 asset manifest JSON; supplies defaults and validates bindings.")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--strict", action="store_true", help="Return exit code 2 when warnings remain.")
    return parser.parse_args()


def read_prompt(args: argparse.Namespace) -> str:
    if args.text is not None and args.prompt_file:
        raise ValueError("Use either --text or prompt_file, not both.")
    if args.text is not None:
        return args.text
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return sys.stdin.read()


def read_manifest(path: str | None) -> dict | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object.")
    return data


def manifest_counts(manifest: dict) -> dict[str, int]:
    counts = {"image": 0, "video": 0, "audio": 0}
    assets = manifest.get("assets", [])
    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, dict) and asset.get("modality") in counts:
                counts[asset["modality"]] += 1
    return counts


def apply_manifest_defaults(args: argparse.Namespace, manifest: dict | None) -> None:
    if manifest:
        counts = manifest_counts(manifest)
        for modality, attr in (("image", "images"), ("video", "videos"), ("audio", "audios")):
            if getattr(args, attr) is None:
                setattr(args, attr, counts[modality])
        if args.mode == "auto" and manifest.get("mode") in MODES:
            args.mode = manifest["mode"]
        if args.duration is None and isinstance(manifest.get("duration"), int):
            args.duration = manifest["duration"]
        if args.surface is None and manifest.get("surface") in SURFACES:
            args.surface = manifest["surface"]
    if args.surface is None:
        args.surface = "generic"


def refs_in(text: str) -> dict[str, list[int]]:
    return {
        kind: [int(match.group(1)) for match in pattern.finditer(text)]
        for kind, pattern in REF_PATTERNS.items()
    }


def add(issues: list[Issue], severity: str, code: str, message: str, basis: str) -> None:
    issues.append(Issue(severity=severity, code=code, message=message, basis=basis))


def expected_surface_tag(surface: str, modality: str, index: int) -> str | None:
    profile = SURFACE_TAGS.get(surface)
    if not profile:
        return None
    return profile[modality].format(n=index)


def validate_manifest(manifest: dict, text: str, args: argparse.Namespace) -> list[Issue]:
    """Validate the neutral asset map and its compiled surface bindings."""
    issues: list[Issue] = []
    allowed_top = {
        "surface",
        "model_version",
        "model_variant",
        "reference_mode",
        "mode",
        "duration",
        "ratio",
        "resolution",
        "generate_audio",
        "assets",
    }
    unknown_top = sorted(set(manifest) - allowed_top)
    if unknown_top:
        add(issues, "error", "O601", f"Unknown manifest field(s): {', '.join(unknown_top)}.", "schema")

    for required in ("surface", "mode", "assets"):
        if required not in manifest:
            add(issues, "error", "O602", f"Manifest is missing required field '{required}'.", "schema")

    surface = manifest.get("surface")
    if surface not in SURFACES:
        add(issues, "error", "O603", f"Manifest surface must be one of {', '.join(SURFACES)}.", "schema")
        surface = "generic"
    elif args.surface != surface:
        add(
            issues,
            "error",
            "O604",
            f"CLI surface '{args.surface}' conflicts with manifest surface '{surface}'.",
            "schema",
        )

    manifest_mode = manifest.get("mode")
    if manifest_mode not in MODES[1:]:
        add(issues, "error", "O605", "Manifest mode is missing or unsupported.", "schema")
    elif args.mode != manifest_mode:
        add(
            issues,
            "error",
            "O606",
            f"CLI mode '{args.mode}' conflicts with manifest mode '{manifest_mode}'.",
            "schema",
        )

    model_version = manifest.get("model_version", "seedance-2.5")
    if model_version not in {"seedance-2.5", "seedance-2.0"}:
        add(issues, "error", "O638", "model_version must be seedance-2.5 or seedance-2.0.", "schema")

    variant = manifest.get("model_variant", "standard")
    if variant not in {"standard", "fast", "mini"}:
        add(issues, "error", "O607", "model_variant must be standard, fast, or mini.", "schema")

    reference_mode = manifest.get("reference_mode", "all-around")
    if reference_mode not in {"all-around", "strict-first-last", "provider-default"}:
        add(issues, "error", "O639", "reference_mode must be all-around, strict-first-last, or provider-default.", "schema")

    duration = manifest.get("duration")
    if duration is not None and (not isinstance(duration, int) or isinstance(duration, bool) or not 4 <= duration <= 30):
        add(issues, "error", "O608", "Manifest duration must be an integer from 4 through 30 for the default Seedance 2.5 path.", "project-default")
    elif duration is not None and args.duration != duration:
        add(
            issues,
            "error",
            "O609",
            f"CLI duration {args.duration}s conflicts with manifest duration {duration}s.",
            "schema",
        )

    if manifest.get("ratio") is not None and manifest["ratio"] not in {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"}:
        add(issues, "error", "O631", "Manifest ratio is not supported by the current official profile.", "official")
    if manifest.get("resolution") is not None and manifest["resolution"] not in {"480p", "720p", "1080p", "4k"}:
        add(issues, "error", "O632", "Manifest resolution must be 480p, 720p, 1080p, or 4k.", "official")
    if "generate_audio" in manifest and not isinstance(manifest["generate_audio"], bool):
        add(issues, "error", "O633", "Manifest generate_audio must be boolean.", "schema")

    assets = manifest.get("assets")
    if not isinstance(assets, list):
        add(issues, "error", "O610", "Manifest assets must be an array.", "schema")
        return issues

    required_asset = {
        "modality",
        "index",
        "tag",
        "alias",
        "transport_role",
        "primary_role",
        "transfers",
        "must_not_transfer",
    }
    allowed_asset = required_asset | {"source"}
    seen_keys: set[tuple[str, int]] = set()
    seen_tags: set[str] = set()
    indices = {"image": [], "video": [], "audio": []}
    transport_roles: list[str] = []

    for position, asset in enumerate(assets, start=1):
        label = f"asset {position}"
        if not isinstance(asset, dict):
            add(issues, "error", "O611", f"Manifest {label} must be an object.", "schema")
            continue
        missing = sorted(required_asset - set(asset))
        unknown = sorted(set(asset) - allowed_asset)
        if missing:
            add(issues, "error", "O612", f"Manifest {label} is missing: {', '.join(missing)}.", "schema")
        if unknown:
            add(issues, "error", "O613", f"Manifest {label} has unknown field(s): {', '.join(unknown)}.", "schema")

        modality = asset.get("modality")
        index = asset.get("index")
        tag = asset.get("tag")
        alias = asset.get("alias")
        role = asset.get("transport_role")
        primary_role = asset.get("primary_role")
        transfers = asset.get("transfers")
        exclusions = asset.get("must_not_transfer")

        if modality not in MEDIA_LIMITS:
            add(issues, "error", "O614", f"Manifest {label} has invalid modality '{modality}'.", "schema")
            continue
        if not isinstance(index, int) or isinstance(index, bool) or index < 1:
            add(issues, "error", "O615", f"Manifest {label} index must be a positive integer.", "schema")
            continue

        key = (modality, index)
        if key in seen_keys:
            add(issues, "error", "O616", f"Duplicate manifest binding for {modality} {index}.", "schema")
        seen_keys.add(key)
        indices[modality].append(index)

        if role not in ROLE_MODALITY:
            add(issues, "error", "O617", f"Manifest {label} has unsupported transport_role '{role}'.", "schema")
        elif ROLE_MODALITY[role] != modality:
            add(
                issues,
                "error",
                "O618",
                f"Transport role '{role}' cannot be assigned to a {modality} asset.",
                "transport",
            )
        else:
            transport_roles.append(role)

        if primary_role not in PRIMARY_ROLES:
            add(issues, "error", "O634", f"Manifest {label} has unsupported primary_role '{primary_role}'.", "schema")

        if not isinstance(tag, str) or not tag.strip():
            add(issues, "error", "O619", f"Manifest {label} needs a non-empty tag.", "schema")
        else:
            if tag in seen_tags:
                add(issues, "error", "O620", f"Manifest tag '{tag}' is duplicated.", "schema")
            seen_tags.add(tag)
            expected = expected_surface_tag(surface, modality, index)
            if expected and tag != expected:
                add(
                    issues,
                    "warning",
                    "H601",
                    f"Surface '{surface}' normally compiles {modality} {index} as '{expected}', not '{tag}'.",
                    "surface-profile",
                )
            if tag not in text:
                add(
                    issues,
                    "error",
                    "O621",
                    f"Manifest tag '{tag}' does not appear verbatim in the prompt.",
                    "binding",
                )

        if not isinstance(alias, str) or not alias.strip():
            add(issues, "error", "O636", f"Manifest {label} needs a readable alias.", "binding")
        elif alias not in text:
            add(
                issues,
                "error",
                "O637",
                f"Manifest alias '{alias}' does not appear in the prompt.",
                "binding",
            )

        if not isinstance(transfers, list) or not transfers or not all(isinstance(item, str) and item.strip() for item in transfers):
            add(issues, "error", "O622", f"Manifest {label} needs at least one named transfer job.", "binding")
            transfers = []
        if not isinstance(exclusions, list) or not all(isinstance(item, str) and item.strip() for item in exclusions):
            add(issues, "error", "O623", f"Manifest {label} must_not_transfer must be a string array.", "binding")
            exclusions = []
        overlap = sorted(set(transfers) & set(exclusions))
        if overlap:
            add(
                issues,
                "error",
                "O624",
                f"Manifest {label} both transfers and forbids: {', '.join(overlap)}.",
                "binding",
            )

    for modality, values in indices.items():
        unique = sorted(set(values))
        if unique and unique != list(range(1, len(unique) + 1)):
            add(
                issues,
                "error",
                "O625",
                f"Manifest {modality} indices must be contiguous from 1; found {unique}.",
                "transport",
            )
        cli_count = getattr(args, f"{modality}s")
        if cli_count is not None and cli_count != len(values):
            add(
                issues,
                "error",
                "O626",
                f"CLI says {cli_count} {modality}(s), but manifest contains {len(values)}.",
                "schema",
            )

    if len(assets) > TOTAL_REFERENCE_LIMIT:
        add(
            issues,
            "error",
            "O640",
            f"Manifest attaches {len(assets)} reference content item(s), exceeding the default Seedance 2.5 all-around limit of {TOTAL_REFERENCE_LIMIT}.",
            "project-default",
        )

    strict_roles = {role for role in transport_roles if role in {"first_frame", "last_frame"}}
    reference_roles = {role for role in transport_roles if role.startswith("reference_")}
    if strict_roles and reference_roles:
        add(
            issues,
            "error",
            "O627",
            "Strict first/last-frame roles cannot be mixed with multimodal reference roles in one API request.",
            "official",
        )
    if manifest_mode == "first-frame" and "first_frame" not in transport_roles:
        add(issues, "error", "O628", "first-frame mode needs an image with transport_role first_frame.", "official")
    if manifest_mode == "first-last" and not {"first_frame", "last_frame"}.issubset(transport_roles):
        add(issues, "error", "O629", "first-last mode needs both first_frame and last_frame roles.", "official")
    if manifest_mode == "multimodal" and strict_roles:
        add(issues, "error", "O630", "multimodal mode cannot use strict first_frame/last_frame roles.", "official")
    if manifest_mode == "text" and assets:
        add(issues, "error", "O635", "Text-to-video mode cannot contain attached assets.", "official")

    primary_roles = {asset.get("primary_role") for asset in assets if isinstance(asset, dict)}
    if manifest_mode == "edit" and "edit_source" not in primary_roles:
        add(issues, "warning", "H602", "Edit manifest has no asset marked as edit_source.", "heuristic")
    if manifest_mode == "extend" and "extension_source" not in primary_roles:
        add(issues, "warning", "H603", "Extension manifest has no asset marked as extension_source.", "heuristic")

    return issues


def split_shots(text: str) -> list[str]:
    marker = re.compile(r"(?im)(?=^\s*(?:shot|scene|ショット|カット|镜头|鏡頭)\s*[#:_-]?\s*\d+)")
    parts = [part.strip() for part in marker.split(text) if part.strip()]
    if len(parts) <= 1:
        return [text]
    if not re.match(r"(?i)^\s*(?:shot|scene|ショット|カット|镜头|鏡頭)", parts[0]):
        parts = parts[1:]
    return parts or [text]


def camera_moves(segment: str) -> list[str]:
    normalized = f" {segment.lower()} "
    found = []
    for name, terms in CAMERA_GROUPS.items():
        if any(term.lower() in normalized for term in terms):
            found.append(name)
    return found


def find_unaliased_references(text: str) -> set[str]:
    all_matches = []
    for kind, pattern in REF_PATTERNS.items():
        for match in pattern.finditer(text):
            all_matches.append((kind, match))
    if len(all_matches) < 2:
        return set()

    unaliased = set()
    for kind, match in all_matches:
        tail = text[match.end() : match.end() + 24].lstrip()
        if not tail.startswith(("(", "（")):
            label = f"{kind.title()} {match.group(1)}"
            unaliased.add(label)
    return unaliased


def repeated_sentences(text: str) -> list[str]:
    """Find exact repeated requirement-like sentence fragments after whitespace cleanup."""
    fragments = [
        re.sub(r"\s+", " ", fragment).strip(" \t\r\n。.!！?？；;")
        for fragment in re.split(r"[。.!！?？；;\n]+", text)
    ]
    seen: set[str] = set()
    repeated: list[str] = []
    for fragment in fragments:
        normalized = fragment.lower()
        if len(normalized) < 12:
            continue
        if normalized in seen and fragment not in repeated:
            repeated.append(fragment)
        seen.add(normalized)
    return repeated


def check_media(
    issues: list[Issue],
    refs: dict[str, list[int]],
    counts: dict[str, int | None],
    mode: str,
) -> None:
    total_attached = sum(count or 0 for count in counts.values())
    if total_attached > TOTAL_REFERENCE_LIMIT:
        add(
            issues,
            "error",
            "O110",
            f"{total_attached} attached reference item(s) exceed the default Seedance 2.5 all-around limit of {TOTAL_REFERENCE_LIMIT}.",
            "project-default",
        )
    for kind, limit in MEDIA_LIMITS.items():
        count = counts[kind]
        if count is not None:
            if count < 0:
                add(issues, "error", "O101", f"{kind} count cannot be negative.", "official")
                continue
            if count > limit:
                add(
                    issues,
                    "error",
                    "O102",
                    f"{count} {kind} assets exceed the default Seedance 2.5 all-around per-modality ceiling of {limit}.",
                    "project-default",
                )
            for index in sorted(set(refs[kind])):
                if index < 1 or index > count:
                    add(
                        issues,
                        "error",
                        "O103",
                        f"{kind.title()} {index} is referenced, but only {count} {kind} asset(s) are attached.",
                        "official",
                    )
            used = set(refs[kind])
            unused = [index for index in range(1, count + 1) if index not in used]
            if unused:
                add(
                    issues,
                    "warning",
                    "H101",
                    f"Attached {kind} asset(s) {unused} are never referenced; assign a job or remove them.",
                    "heuristic",
                )

        unique = sorted(set(refs[kind]))
        if unique:
            expected = list(range(1, max(unique) + 1))
            if unique != expected:
                add(
                    issues,
                    "warning",
                    "H102",
                    f"{kind.title()} references have numbering gaps: {unique}. Verify upload order and surface syntax.",
                    "heuristic",
                )

    images = counts["image"] or 0
    videos = counts["video"] or 0
    audios = counts["audio"] or 0
    if audios and not (images or videos):
        add(
            issues,
            "error",
            "O104",
            "Reference audio cannot be the only multimodal input; attach at least one image or video.",
            "official",
        )

    if mode == "text" and any(refs.values()):
        add(issues, "error", "O105", "Text-to-video mode cannot contain numbered media references.", "official")
    if mode == "first-frame" and counts["image"] is not None and counts["image"] < 1:
        add(issues, "error", "O106", "First-frame mode requires one image.", "official")
    if mode == "first-last" and counts["image"] is not None and counts["image"] < 2:
        add(issues, "error", "O107", "First/last-frame mode requires two images.", "official")
    if mode in {"edit", "extend"} and counts["video"] is not None and counts["video"] < 1:
        add(issues, "error", "O108", f"{mode.title()} mode requires a source video.", "official")
    if mode == "stitch" and counts["video"] is not None and counts["video"] < 2:
        add(issues, "error", "O109", "Stitch mode requires at least two source videos.", "official")


def check_prompt(text: str, args: argparse.Namespace) -> list[Issue]:
    issues: list[Issue] = []
    stripped = text.strip()
    if not stripped:
        add(issues, "error", "O001", "Prompt is empty.", "official")
        return issues

    word_count = len(re.findall(r"\S+", stripped))
    if word_count > 1000:
        add(
            issues,
            "error",
            "O002",
            f"Prompt contains {word_count} whitespace-delimited words; official guidance recommends under 1000.",
            "official",
        )
    elif word_count > 600 or len(stripped) > 6000:
        add(
            issues,
            "warning",
            "H001",
            "Prompt is very dense. Remove redundant detail or stage lower-priority ideas across clips.",
            "heuristic",
        )

    if args.duration is not None and not 4 <= args.duration <= 30:
        add(
            issues,
            "error",
            "O003",
            f"Duration {args.duration}s is outside the default Seedance 2.5 range of 4–30 seconds.",
            "project-default",
        )

    refs = refs_in(stripped)
    counts = {"image": args.images, "video": args.videos, "audio": args.audios}
    check_media(issues, refs, counts, args.mode)

    if re.search(r"\bseed\s*[:=]\s*-?\d+", stripped, re.IGNORECASE):
        add(issues, "error", "O201", "Seed/API seed controls belong in provider parameters, not prompt prose.", "prompt-cleaning")
    if re.search(r"\bcamera_fixed\b", stripped, re.IGNORECASE):
        add(issues, "error", "O202", "camera_fixed is a provider/control-layer field, not prompt prose.", "prompt-cleaning")
    if re.search(r"\b(?:480p|720p|1080p|4k|8k|resolution\s*[:=]|分辨率|清晰度\s*[:=])\b", stripped, re.IGNORECASE):
        add(
            issues,
            "warning",
            "H201",
            "Resolution/model-quality controls appear in prompt prose. Put 480P and other resolution settings in provider controls, not the prompt.",
            "prompt-cleaning",
        )

    if re.search(r"asset[-_:][a-z0-9_-]{6,}", stripped, re.IGNORECASE):
        add(
            issues,
            "warning",
            "O203",
            "An opaque asset ID appears in prompt prose. Keep it in the request/asset map and use a numbered readable label for the subject.",
            "prompt-cleaning",
        )

    dirty_patterns = (
        r"(?i)\b(?:model|workflow|api|endpoint|payload|json|curl|http|request|response|parameter|params|node|workflow_id)\b",
        r"(?i)\b(?:Seedance\s*2\.5|Seedance\s*2\.0|Dreamina|Doubao|Jimeng)\b",
        r"(?:模型|工作流|接口|端点|参数|请求体|返回|节点|调用|生成流程|提交任务|全能参考模式|参考模式|使用\s*default-video-generation|调用\s*default-video-generation)",
        r"(?:你是一个.*?(?:专家|助手)|请严格遵守|系统规则|规则如下|以上规则|下面的规则)",
    )
    for pattern in dirty_patterns:
        if re.search(pattern, stripped):
            add(
                issues,
                "warning",
                "H202",
                "Prompt appears to contain model names, workflow/API terms, provider settings, or system-rule text that should be stripped before generation.",
                "prompt-cleaning",
            )
            break

    repeated = repeated_sentences(stripped)
    if repeated:
        add(
            issues,
            "warning",
            "H203",
            f"Prompt repeats the same requirement more than once: {repeated[0][:80]}",
            "prompt-cleaning",
        )

    unaliased = sorted(find_unaliased_references(stripped))
    if unaliased:
        add(
            issues,
            "warning",
            "O204",
            f"Multi-reference prompt has labels without an immediate noun/alias: {', '.join(unaliased)}.",
            "official",
        )

    timed = re.search(
        r"(?:\b\d+(?:\.\d+)?\s*(?:-|–|—|to)\s*\d+(?:\.\d+)?\s*(?:s|sec(?:ond)?s?|秒)\b|\b(?:at|around)\s+\d+(?:\.\d+)?\s*(?:s|sec(?:ond)?s?)\b)",
        stripped,
        re.IGNORECASE,
    )
    if timed and args.mode not in {"edit", "stitch"}:
        add(
            issues,
            "warning",
            "O301",
            "Exact time slices are present. Official guidance prefers Shot order because precise timing is unstable; keep timing only for required sync or edit windows.",
            "official",
        )

    shots = split_shots(stripped)
    for index, segment in enumerate(shots, start=1):
        moves = camera_moves(segment)
        if len(moves) > 1:
            add(
                issues,
                "warning",
                "O302",
                f"Shot {index} appears to stack camera moves {moves}. Keep one primary movement unless a reference video deliberately supplies the compound path.",
                "official",
            )
    if args.duration and len(shots) > max(1, args.duration // 2):
        add(
            issues,
            "warning",
            "H301",
            f"{len(shots)} shots may be too dense for {args.duration}s. Reduce beats or split the clip.",
            "heuristic",
        )

    lower = stripped.lower()
    no_subtitles = any(term in lower for term in ("subtitle-free", "no subtitles", "avoid subtitles", "字幕なし", "字幕を生成しない", "保持无字幕", "避免生成任何文字或字幕"))
    wants_subtitles = any(term in lower for term in ("display subtitles", "subtitles appear", "render the dialogue as subtitles", "字幕を表示", "字幕が表示", "字幕内容", "〖", "【"))
    if no_subtitles and wants_subtitles:
        add(issues, "error", "O401", "Prompt both requests and forbids subtitles/on-screen text.", "official")

    no_logo = any(term in lower for term in ("no logo", "do not generate a logo", "logoなし", "ロゴを生成しない", "不要生成 logo"))
    wants_logo = any(term in lower for term in ("preserve the logo", "logo remains", "ロゴを維持", "ロゴを表示", "保持 logo", "logo placement"))
    if no_logo and wants_logo:
        add(issues, "error", "O402", "Prompt both requests and forbids a logo.", "official")

    fixed_terms = ("fixed camera", "locked camera", "camera stays locked", "固定カメラ", "カメラ固定", "固定机位")
    if any(term in lower for term in fixed_terms):
        all_moves = set(move for segment in shots for move in camera_moves(segment))
        if all_moves - {"handheld"}:
            add(issues, "warning", "O403", "Prompt requests a fixed/locked camera and also describes camera movement.", "official")

    pairs = (("{", "}"), ("<", ">"), ("〖", "〗"), ("【", "】"))
    for opening, closing in pairs:
        if stripped.count(opening) != stripped.count(closing):
            add(
                issues,
                "warning",
                "H401",
                f"Unbalanced Seedance notation: {opening}{closing}.",
                "heuristic",
            )

    if refs["audio"]:
        audio_context = any(
            term in lower
            for term in (
                "voice",
                "timbre",
                "music",
                "rhythm",
                "beat",
                "sound",
                "ambience",
                "声",
                "音色",
                "音楽",
                "リズム",
                "効果音",
                "環境音",
                "声音",
                "音乐",
                "节奏",
                "音效",
            )
        )
        if not audio_context:
            add(
                issues,
                "warning",
                "O501",
                "Audio is referenced without saying whether to transfer voice, timbre, music, rhythm, ambience, content, or effects.",
                "official",
            )

    return issues


def print_text(issues: Iterable[Issue]) -> None:
    issues = list(issues)
    if not issues:
        print("PASS: no static preflight issues found.")
        return
    for issue in issues:
        print(f"{issue.severity.upper()} {issue.code} [{issue.basis}]: {issue.message}")
    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    print(f"SUMMARY: {errors} error(s), {warnings} warning(s).")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    try:
        manifest = read_manifest(args.manifest)
        apply_manifest_defaults(args, manifest)
        prompt = read_prompt(args)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    issues = validate_manifest(manifest, prompt, args) if manifest else []
    issues.extend(check_prompt(prompt, args))
    if args.output_format == "json":
        payload = {
            "ok": not any(issue.severity == "error" for issue in issues),
            "profile": {
                "surface": args.surface,
                "mode": args.mode,
                "duration": args.duration,
                "images": args.images,
                "videos": args.videos,
                "audios": args.audios,
            },
            "issues": [asdict(issue) for issue in issues],
            "summary": {
                "errors": sum(issue.severity == "error" for issue in issues),
                "warnings": sum(issue.severity == "warning" for issue in issues),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text(issues)

    if any(issue.severity == "error" for issue in issues):
        return 1
    if args.strict and any(issue.severity == "warning" for issue in issues):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
