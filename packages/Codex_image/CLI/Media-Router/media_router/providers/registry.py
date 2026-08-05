from __future__ import annotations

from pathlib import Path

from ..config import PROJECT_ROOT
from .comfly_adapter import ComflyAdapter
from .command_adapter import DreaminaAdapter, PythonImageAdapter


COMFLY_MODELS = {
    "comfly-gemini-lite": "gemini-3.1-flash-lite-image",
    "comfly-gpt-image-2-all": "gpt-image-2-all",
    "comfly-gpt-image-2": "gpt-image-2",
}


def build_registry(config: dict) -> dict:
    providers = config["providers"]
    registry = {}
    for provider_id, model in COMFLY_MODELS.items():
        registry[provider_id] = ComflyAdapter(provider_id, model, providers[provider_id]["max_concurrency"])
    registry["apimart-gpt-image-2"] = PythonImageAdapter("apimart-gpt-image-2", "gpt-image-2", PROJECT_ROOT / "CLI" / "Gpt-API" / "gpt_api.py", "APIMART_API_KEY")
    registry["google-gemini-image"] = PythonImageAdapter("google-gemini-image", "gemini-3.1-flash-image", PROJECT_ROOT / "CLI" / "Gemini-API" / "gemini_api.py", "GEMINI_API_KEY")
    registry["dreamina-image"] = DreaminaAdapter("dreamina-image", "image", "4.0")
    registry["antigravity-image"] = PythonImageAdapter("antigravity-image", "antigravity", PROJECT_ROOT / "CLI" / "Gemini-CLI" / "agy_image.py", None)
    registry["dreamina-video"] = DreaminaAdapter("dreamina-video", "video", "seedance2.0_vip")
    for provider_id, adapter in registry.items():
        adapter.max_concurrency = providers[provider_id]["max_concurrency"]
        adapter.capacity_key = providers[provider_id].get("capacity_key", provider_id)
    return registry
