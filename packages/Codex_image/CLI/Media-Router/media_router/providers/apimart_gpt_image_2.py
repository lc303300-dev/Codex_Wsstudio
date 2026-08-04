from .command_adapter import PythonImageAdapter
from ..config import PROJECT_ROOT

Adapter = lambda max_concurrency=6: PythonImageAdapter("apimart-gpt-image-2", "gpt-image-2", PROJECT_ROOT / "CLI" / "Gpt-API" / "gpt_api.py", "APIMART_API_KEY", max_concurrency)
