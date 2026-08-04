from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def find_project_root() -> Path:
    configured = os.environ.get("CODEX_IMAGE_ROOT")
    if configured and (Path(configured) / "CLI" / "Media-Router").is_dir():
        return Path(configured).resolve()
    marker = PLUGIN_ROOT / ".codex-image-registration.json"
    if marker.is_file():
        try:
            candidate = Path(json.loads(marker.read_text(encoding="utf-8-sig"))["source_root"])
            if (candidate / "CLI" / "Media-Router").is_dir():
                return candidate.resolve()
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            pass
    candidate = PLUGIN_ROOT.parent
    if (candidate / "CLI" / "Media-Router").is_dir():
        return candidate.resolve()
    raise RuntimeError("Codex_image source root is unavailable")


PROJECT_ROOT = find_project_root()
sys.path.insert(0, str(PROJECT_ROOT / "CLI" / "Media-Router"))
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from media_router.service import execute  # noqa: E402
from schemas import IMAGE_SCHEMA, VIDEO_SCHEMA  # noqa: E402


TOOLS = [
    {
        "name": "generate_image",
        "description": "Generate or edit one image through the default serial media router. This open-world operation may consume provider credits.",
        "inputSchema": IMAGE_SCHEMA,
        "annotations": {"openWorldHint": True, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "generate_video",
        "description": "Generate one video with Seedance/Dreamina. This open-world operation may consume provider credits.",
        "inputSchema": VIDEO_SCHEMA,
        "annotations": {"openWorldHint": True, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
]


def response(identifier, result=None, error=None) -> dict:
    payload = {"jsonrpc": "2.0", "id": identifier}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def handle(message: dict) -> dict | None:
    identifier, method = message.get("id"), message.get("method")
    if method == "initialize":
        return response(identifier, {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "codex-media", "version": "0.1.0"}})
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return response(identifier, {})
    if method == "tools/list":
        return response(identifier, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name, arguments = params.get("name"), params.get("arguments") or {}
        if name not in {"generate_image", "generate_video"}:
            return response(identifier, error={"code": -32602, "message": "Unknown tool"})
        try:
            result = execute(name, arguments.get("prompt", ""), arguments.get("images", []), arguments.get("videos", []), arguments.get("audios", []))
        except Exception as exc:
            result = {"status": "failed", "safe_reason": type(exc).__name__}
        return response(identifier, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "structuredContent": result, "isError": result.get("status") != "success"})
    return response(identifier, error={"code": -32601, "message": "Method not found"}) if identifier is not None else None


def main() -> None:
    for line in sys.stdin:
        try:
            result = handle(json.loads(line))
            if result is not None:
                print(json.dumps(result, ensure_ascii=False), flush=True)
        except json.JSONDecodeError:
            print(json.dumps(response(None, error={"code": -32700, "message": "Parse error"})), flush=True)


if __name__ == "__main__":
    main()
