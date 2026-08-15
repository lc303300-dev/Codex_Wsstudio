from ..config import load_config
from .comfly_adapter import ComflyAdapter

Adapter = lambda max_concurrency=6: ComflyAdapter(
    "comfly-gemini-lite",
    load_config()["providers"]["comfly-gemini-lite"]["model"],
    max_concurrency,
    load_config()["providers"]["comfly-gemini-lite"].get("size_profile"),
)
