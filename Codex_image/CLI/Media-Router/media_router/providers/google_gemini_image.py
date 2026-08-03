from .command_adapter import PythonImageAdapter
from ..config import PROJECT_ROOT

Adapter = lambda max_concurrency=6: PythonImageAdapter("google-gemini-image", "gemini-3.1-flash-image", PROJECT_ROOT / "CLI" / "Gemini-API" / "gemini_api.py", "GEMINI_API_KEY", max_concurrency)
