from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_ROOT = PROJECT_ROOT / ".codex-image-private"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "media-router.defaults.json"
PRIVATE_CONFIG = PRIVATE_ROOT / "config" / "media-router.json"


def _merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(default_path: Path = DEFAULT_CONFIG, private_path: Path = PRIVATE_CONFIG) -> dict:
    config = json.loads(default_path.read_text(encoding="utf-8"))
    if private_path.is_file():
        config = _merge(config, json.loads(private_path.read_text(encoding="utf-8-sig")))
    child_limit = config.get("scheduler", {}).get("max_child_agents", 6)
    if isinstance(child_limit, bool) or not isinstance(child_limit, int) or not 1 <= child_limit <= 6:
        raise ValueError("scheduler.max_child_agents must be an integer from 1 to 6")
    timeouts = config.get("image_timeouts", {})
    for name in ("provider_seconds", "task_seconds"):
        value = timeouts.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"image_timeouts.{name} must be a positive integer")
    if timeouts["provider_seconds"] > timeouts["task_seconds"]:
        raise ValueError("image_timeouts.provider_seconds must not exceed image_timeouts.task_seconds")
    max_image_long_edge = config.get("media_inputs", {}).get("max_image_long_edge")
    if isinstance(max_image_long_edge, bool) or not isinstance(max_image_long_edge, int) or not 1 <= max_image_long_edge <= 1920:
        raise ValueError("media_inputs.max_image_long_edge must be an integer from 1 to 1920")
    for provider_id, provider in config.get("providers", {}).items():
        limit = provider.get("max_concurrency", 6)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 6:
            raise ValueError(f"providers.{provider_id}.max_concurrency must be an integer from 1 to 6")
        provider["max_concurrency"] = limit
        provider.setdefault("capacity_key", provider_id)
        if provider_id.startswith("comfly-"):
            model = provider.get("model")
            if not isinstance(model, str) or not model.strip():
                raise ValueError(f"providers.{provider_id}.model must be a non-empty string")
            size_profile = provider.get("size_profile")
            if size_profile is not None and size_profile not in {"gemini-1k"}:
                raise ValueError(f"providers.{provider_id}.size_profile is unsupported: {size_profile}")
    return config
