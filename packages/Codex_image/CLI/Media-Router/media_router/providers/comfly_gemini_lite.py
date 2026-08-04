from .comfly_adapter import ComflyAdapter

Adapter = lambda max_concurrency=6: ComflyAdapter("comfly-gemini-lite", "gemini-3.1-flash-lite-image", max_concurrency)
