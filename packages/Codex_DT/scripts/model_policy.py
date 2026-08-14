#!/usr/bin/env python3
"""Canonical video-model policy shared by manifest creation and submission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "seedance2.5"
DEFAULT_RESOLUTION = "480p"
SUPPORTED_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")

MODEL_ALIASES = {
    "seedance2.5": "seedance2.5",
    "seedance-2.5": "seedance2.5",
    "2.5": "seedance2.5",
    "seedance2.0": "seedance2.0_vip",
    "seedance-2.0": "seedance2.0_vip",
    "2.0": "seedance2.0_vip",
    "seedance2.0_vip": "seedance2.0_vip",
    "seedance2.0-vip": "seedance2.0_vip",
    "seedance2.0fast_vip": "seedance2.0fast_vip",
    "seedance2.0-fast-vip": "seedance2.0fast_vip",
    "seedance2.0mini": "seedance2.0mini",
    "seedance2.0-mini": "seedance2.0mini",
}
SUPPORTED_MODELS = tuple(dict.fromkeys(MODEL_ALIASES.values()))
SEEDANCE_20_MODELS = frozenset(model for model in SUPPORTED_MODELS if model.startswith("seedance2.0"))


def normalize_model(value: str | None) -> str:
    key = (value or DEFAULT_MODEL).strip().lower()
    try:
        return MODEL_ALIASES[key]
    except KeyError as exc:
        accepted = ", ".join(SUPPORTED_MODELS)
        raise ValueError(f"Unsupported video model {value!r}. Allowed canonical models: {accepted}.") from exc


def build_model_selection(value: str | None, *, explicit: bool, user_text: str | None = None) -> dict[str, Any]:
    model = normalize_model(value)
    if model in SEEDANCE_20_MODELS and not explicit:
        raise ValueError("Seedance 2.0 may only be selected by an explicit user request or --model-version option.")
    return {
        "requested": model,
        "selection_source": "user_explicit" if explicit else "default",
        "selection_evidence": "cli_option" if explicit else "pipeline_default",
        "user_text": user_text if explicit and user_text else None,
    }


def validate_settings(model: str, duration: Any, resolution: Any, ratio: Any) -> None:
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise ValueError("Video duration must be an integer.")
    if model == DEFAULT_MODEL:
        if not 4 <= duration <= 30:
            raise ValueError(f"Duration for {model} must be 4 through 30 seconds; got {duration}.")
        allowed_resolutions = {"480p", "720p"}
    else:
        if not 4 <= duration <= 15:
            raise ValueError(
                f"Duration for {model} is conservatively limited to 4 through 15 seconds; got {duration}. "
                "Re-check current provider help before expanding this limit."
            )
        # The precise high-resolution tiers differ across Seedance 2.0 variants and
        # provider releases. Keep the shared batch path on the verified common set.
        allowed_resolutions = {"480p", "720p"}
    if resolution not in allowed_resolutions:
        allowed = ", ".join(sorted(allowed_resolutions))
        raise ValueError(
            f"Resolution for {model} must be one of {allowed} in this verified batch path; got {resolution}. "
            "Use a provider-specific adapter after checking current CLI help for higher tiers."
        )
    if ratio not in SUPPORTED_RATIOS:
        raise ValueError(f"Ratio must be one of {', '.join(SUPPORTED_RATIOS)}; got {ratio}.")


def validate_manifest(data: dict[str, Any]) -> dict[str, Any]:
    compile_data = data.get("mqrox_compile")
    if not isinstance(compile_data, dict):
        raise ValueError("Manifest is missing mqrox_compile.")
    model = normalize_model(compile_data.get("model_version"))
    selection = compile_data.get("model_selection")
    if not isinstance(selection, dict):
        if model in SEEDANCE_20_MODELS:
            raise ValueError(
                "Seedance 2.0 submission refused: this manifest has no model_selection evidence. "
                "Recreate it with an explicit --model-version option after the user requests 2.0."
            )
        selection = build_model_selection(DEFAULT_MODEL, explicit=False)
    source = selection.get("selection_source")
    requested = normalize_model(selection.get("requested"))
    if requested != model:
        raise ValueError(f"model_selection.requested ({requested}) conflicts with model_version ({model}).")
    if model in SEEDANCE_20_MODELS and source != "user_explicit":
        raise ValueError(
            "Seedance 2.0 submission refused: selection_source must be user_explicit. "
            "Old, inferred, or manually edited 2.0 manifests cannot be submitted."
        )
    if model in SEEDANCE_20_MODELS and selection.get("selection_evidence") != "cli_option":
        raise ValueError(
            "Seedance 2.0 submission refused: selection_evidence must be cli_option. "
            "Recreate the request or manifests with --model-version after the user explicitly selects 2.0."
        )
    if model == DEFAULT_MODEL and source not in {"default", "user_explicit"}:
        raise ValueError(f"Invalid selection_source for {model}: {source!r}.")
    resolution = str(compile_data.get("resolution") or DEFAULT_RESOLUTION).lower()
    validate_settings(model, compile_data.get("duration"), resolution, compile_data.get("ratio"))
    return {"model_version": model, "resolution": resolution, "selection_source": source}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and normalize a Codex_DT manifest model selection.")
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    print(json.dumps(validate_manifest(data), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Model policy validation failed: {exc}")
