#!/usr/bin/env python3
"""Compile detected environmental elements into reusable motion guidance.

The compiler is deliberately conservative: it only emits a motion strategy when
the visual-recognition payload contains a matching element.  It does not infer
plants or water from a filename, camera style, or an absent field.
"""

from __future__ import annotations

import re
from typing import Any


class MotionStrategy:
    __slots__ = ("key", "label_zh", "aliases", "motion_zh", "corpus_terms_zh", "corpus_terms_en")

    def __init__(
        self,
        key: str,
        label_zh: str,
        aliases: tuple[str, ...],
        motion_zh: str,
        corpus_terms_zh: tuple[str, ...],
        corpus_terms_en: tuple[str, ...],
    ) -> None:
        self.key = key
        self.label_zh = label_zh
        self.aliases = aliases
        self.motion_zh = motion_zh
        self.corpus_terms_zh = corpus_terms_zh
        self.corpus_terms_en = corpus_terms_en


STRATEGIES: tuple[MotionStrategy, ...] = (
    MotionStrategy(
        key="plants",
        label_zh="植物",
        aliases=(
            "植物", "树", "树木", "树枝", "枝条", "树叶", "树影", "叶片", "绿叶", "竹林",
            "竹子", "芦苇", "草", "草地", "花", "花朵", "灌木", "藤蔓", "盆栽",
        ),
        motion_zh=(
            "植物受微风影响产生轻微、连续、不同步的摆动：近处叶片和细枝运动更明显，"
            "远处植被幅度更小，枝条自然弯曲并回弹；光影和阴影随叶片运动发生细微变化。"
        ),
        corpus_terms_zh=("植物随风摆动", "枝叶微动", "环境自然运动"),
        corpus_terms_en=("wind moving foliage", "subtle plant motion", "environmental motion"),
    ),
    MotionStrategy(
        key="water_surface",
        label_zh="水面",
        aliases=(
            "水面", "湖面", "河面", "池塘", "池水", "溪流", "河流", "湖泊", "海面", "海水",
            "水波", "水纹", "水体", "水上", "水中",
        ),
        motion_zh=(
            "水面在微风作用下形成细密、连续、沿风向传播的波纹；反射高光轻微闪烁，"
            "天空、建筑或植物倒影随波面自然变形，水体保持平面连贯，不出现无原因的剧烈翻腾。"
        ),
        corpus_terms_zh=("水面波纹扩散", "倒影随水波变化", "自然水体运动"),
        corpus_terms_en=("ripples spreading across water", "reflection moving with waves", "natural water motion"),
    ),
    MotionStrategy(
        key="reflection",
        label_zh="倒影",
        aliases=("倒影", "倒映", "水中倒影", "反射影像"),
        motion_zh=(
            "倒影只随承载它的水面或反射面发生同步、低幅度变形，保持与真实主体的空间对应关系，"
            "不独立漂移、不新增主体。"
        ),
        corpus_terms_zh=("倒影同步变化", "反射连续性"),
        corpus_terms_en=("reflection continuity", "reflection distortion following surface motion"),
    ),
)

# Corpus hygiene: only sentences that describe environmental motion or its
# physical consequence are allowed into this feature.  Camera, lens, exposure,
# editing, style, and generic subject-action advice are intentionally excluded.
ENVIRONMENTAL_TERMS = (
    "植物", "树", "树叶", "叶片", "枝条", "竹", "芦苇", "草", "花", "灌木", "藤蔓",
    "foliage", "leaf", "leaves", "branch", "plant", "tree", "reed", "grass", "flower",
    "水面", "湖面", "河面", "池塘", "溪流", "河流", "湖泊", "海面", "水波", "水纹", "波纹",
    "水体", "水花", "倒影", "反射", "涟漪", "water", "lake", "river", "pond", "stream",
    "ocean", "ripple", "wave", "reflection", "reflected",
    "微风", "风吹", "摆动", "摇曳", "飘动", "扩散", "流动", "闪烁", "回弹", "wind", "sway",
    "swaying", "breeze", "moving", "motion", "ripples", "flowing", "shimmer",
)
GENERIC_POLLUTION_TERMS = (
    "镜头", "运镜", "推镜", "拉镜", "摇镜", "跟拍", "航拍", "景别", "焦段", "广角", "长焦",
    "曝光", "景深", "胶片", "颗粒", "色调", "构图", "cinematic", "camera", "lens", "shot",
    "tracking", "push-in", "zoom", "pan", "tilt", "dolly", "exposure", "depth of field",
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "；".join(_as_text(item) for item in value)
    if isinstance(value, dict):
        return "；".join(f"{key}:{_as_text(item)}" for key, item in value.items())
    return str(value)


def _recognition_text(visual: dict[str, Any]) -> str:
    """Flatten only recognition fields; user prompt text is intentionally excluded."""
    fields = (
        "description_zh", "main_subjects", "fixed_elements", "movable_elements",
        "elements", "environment", "background", "scene",
    )
    return _as_text({field: visual.get(field, "") for field in fields}).lower()


def detect_environment_elements(visual: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return stable, auditable element detections from a visual recognition payload."""
    if not isinstance(visual, dict):
        return []
    text = _recognition_text(visual)
    found: list[dict[str, Any]] = []
    for strategy in STRATEGIES:
        aliases = [alias for alias in strategy.aliases if alias.lower() in text]
        if aliases:
            found.append({
                "key": strategy.key,
                "label_zh": strategy.label_zh,
                "evidence": aliases,
                "source": "visual_recognition",
            })
    return found


def _strategy(key: str) -> MotionStrategy:
    return next(item for item in STRATEGIES if item.key == key)


def compile_environment_motion(
    visual: dict[str, Any] | None,
    *,
    intensity: str = "subtle",
) -> dict[str, Any]:
    """Compile a manifest-friendly strategy block.

    ``intensity`` is intentionally limited to descriptive modifiers.  Camera
    direction remains owned by the director layer and is never overwritten.
    """
    if intensity not in {"subtle", "moderate"}:
        raise ValueError("intensity must be 'subtle' or 'moderate'")
    detections = detect_environment_elements(visual)
    if not detections:
        return {
            "schema": "environment-motion/v1",
            "detected": False,
            "elements": [],
            "motion_lines_zh": [],
            "negative_constraints_zh": [],
            "prompt_section_zh": "",
            "forge_queries_zh": [],
            "forge_queries_en": [],
        }

    modifier = "幅度保持克制" if intensity == "subtle" else "幅度自然但清晰可见"
    motion_lines: list[str] = []
    queries_zh: list[str] = []
    queries_en: list[str] = []
    for detection in detections:
        strategy = _strategy(detection["key"])
        motion_lines.append(f"{strategy.motion_zh}{modifier}。")
        queries_zh.extend(strategy.corpus_terms_zh)
        queries_en.extend(strategy.corpus_terms_en)

    # A shared constraint prevents the common failure mode where environmental
    # motion causes the whole image to wobble or the scene geometry to drift.
    negative = [
        "保持原始构图、主体位置、空间结构、材质和光线关系稳定。",
        "环境运动只发生在被识别出的元素上，不让静态建筑、地面或主体跟随漂移。",
        "避免突然跳动、同步机械摆动、无原因的剧烈运动、结构变形和新增物体。",
    ]
    # Keep order deterministic for reproducible manifests and corpus queries.
    queries_zh = list(dict.fromkeys(queries_zh))
    queries_en = list(dict.fromkeys(queries_en))
    section = "环境动态（由图像识别自动注入）：\n" + "\n".join(
        f"- {line}" for line in motion_lines + negative
    )
    return {
        "schema": "environment-motion/v1",
        "detected": True,
        "elements": detections,
        "motion_lines_zh": motion_lines,
        "negative_constraints_zh": negative,
        "prompt_section_zh": section,
        "forge_queries_zh": queries_zh,
        "forge_queries_en": queries_en,
    }


def apply_to_manifest(manifest: dict[str, Any], *, intensity: str = "subtle") -> dict[str, Any]:
    """Update a manifest in place and return it for convenient CLI use."""
    visual = manifest.get("visual") if isinstance(manifest.get("visual"), dict) else {}
    compiled = compile_environment_motion(visual, intensity=intensity)
    manifest["environment_motion"] = compiled

    motion_plan = manifest.setdefault("motion_plan", {})
    existing = motion_plan.get("environment_motion_zh", [])
    if not isinstance(existing, list):
        existing = [str(existing)] if existing else []
    motion_plan["environment_motion_zh"] = list(dict.fromkeys(
        [item for item in existing if item not in {""}] + compiled["motion_lines_zh"]
    ))
    negatives = motion_plan.get("negative_constraints_zh", [])
    if not isinstance(negatives, list):
        negatives = [str(negatives)] if negatives else []
    motion_plan["negative_constraints_zh"] = list(dict.fromkeys(negatives + compiled["negative_constraints_zh"]))

    forge = manifest.setdefault("forge", {})
    for field in ("queries_zh", "queries_en"):
        existing_queries = forge.get(field, [])
        if isinstance(existing_queries, str):
            existing_queries = [existing_queries]
        if not isinstance(existing_queries, list):
            existing_queries = []
        forge[field] = list(dict.fromkeys(existing_queries + compiled[f"forge_{field}"]))
    if compiled["detected"]:
        forge["matches"] = sanitize_corpus_matches(forge.get("matches", []))
        forge["corpus_scope"] = "environmental_motion_only"
        forge["excluded_advice"] = ["camera", "lens", "shot", "exposure", "style", "generic_subject_action"]
    return manifest


def render_prompt_section(compiled: dict[str, Any]) -> str:
    return str(compiled.get("prompt_section_zh", "")).strip()


def _contains_term(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def sanitize_corpus_match(match: dict[str, Any]) -> dict[str, Any] | None:
    """Keep only environmental-motion sentences from a corpus record.

    A record is discarded when it has no environmental evidence.  Within a
    mixed record, camera/style sentences are removed rather than allowed to
    leak into this feature's reusable evidence.
    """
    evidence_text = "\n".join(str(match.get(field, "")) for field in ("title", "description", "content_preview", "content") if match.get(field))
    if not _contains_term(evidence_text, ENVIRONMENTAL_TERMS):
        return None

    # Titles are retrieval metadata, not prompt evidence.  Never copy them into
    # the reusable motion description (a title may contain camera/style advice).
    source = "\n".join(str(match.get(field, "")) for field in ("description", "content_preview", "content") if match.get(field))
    chunks = [part.strip() for part in re.split(r"[。！？.!?;；]\s*|\n+", source) if part.strip()]
    kept: list[str] = []
    for chunk in chunks:
        has_environment = _contains_term(chunk, ENVIRONMENTAL_TERMS)
        has_generic = _contains_term(chunk, GENERIC_POLLUTION_TERMS)
        # Keep a mixed sentence only if it explicitly describes an environmental
        # action/feedback; the generic camera clause itself is not retained.
        if has_environment and (not has_generic or any(term in chunk.lower() for term in ("随", "形成", "扩散", "摆动", "倒影", "波纹", "wind", "ripple", "sway"))):
            kept.append(chunk)
    if not kept:
        return None

    cleaned = dict(match)
    cleaned["content_preview"] = " ".join(kept[:8])
    if "content" in cleaned:
        cleaned["content"] = " ".join(kept)
    cleaned["environmental_motion_only"] = True
    cleaned["removed_generic_advice"] = True
    return cleaned


def sanitize_corpus_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically remove camera/style/general-action corpus pollution."""
    cleaned: list[dict[str, Any]] = []
    for match in matches:
        if isinstance(match, dict):
            result = sanitize_corpus_match(match)
            if result is not None:
                cleaned.append(result)
    return cleaned
