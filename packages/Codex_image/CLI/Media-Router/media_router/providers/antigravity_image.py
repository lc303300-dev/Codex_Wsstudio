from .command_adapter import PythonImageAdapter
from ..config import PROJECT_ROOT

Adapter = lambda max_concurrency=6: PythonImageAdapter("antigravity-image", "antigravity", PROJECT_ROOT / "CLI" / "Gemini-CLI" / "agy_image.py", None, max_concurrency)
