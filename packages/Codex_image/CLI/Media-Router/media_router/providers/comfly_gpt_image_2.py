from .comfly_adapter import ComflyAdapter

Adapter = lambda max_concurrency=6: ComflyAdapter("comfly-gpt-image-2", "gpt-image-2", max_concurrency)
