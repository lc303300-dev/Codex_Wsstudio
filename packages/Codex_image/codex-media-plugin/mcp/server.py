from __future__ import annotations

import base64
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
from schemas import (  # noqa: E402
    BATCH_IMAGE_SCHEMA,
    DT_PREVIEW_SCHEMA,
    DT_START_BATCH_SCHEMA,
    DT_VALIDATE_BATCH_SCHEMA,
    FLOW_ROUTE_SCHEMA,
    GIF_SCHEMA,
    IMAGE_SCHEMA,
    TOOL_SCOUT_SCHEMA,
    VIDEO_SCHEMA,
)


TOOLS = [
    {
        "name": "generate_image",
        "description": "Generate or edit one image through the unified media router. By default it uses the configured serial fallback order; when the user explicitly names a supported image route, pass image_provider to use only that route. image_resolution is optional and supports 1K, 2K, or 4K; when omitted, GPT image routes default to 4K and Gemini image routes default to 2K. An explicit user-selected image_ratio is required. This open-world operation may consume provider credits.",
        "inputSchema": IMAGE_SCHEMA,
        "annotations": {"openWorldHint": True, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {
        "name": "generate_video",
        "description": "Generate one or more independent videos concurrently with Seedance/Dreamina. This open-world operation may consume provider credits.",
        "inputSchema": VIDEO_SCHEMA,
        "annotations": {"openWorldHint": True, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    },
    {"name": "convert_video_to_gif", "description": "Convert local video files to GIF through the Codex_Gif pipeline. Outputs remain local and may overwrite only when explicitly requested.", "inputSchema": GIF_SCHEMA, "annotations": {"openWorldHint": False, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}},
    {"name": "batch_generate_images", "description": "Run the deterministic Codex_Batch_Image scheduler. Real runs consume credits and require paid_confirmation=confirmed; dry_run does not.", "inputSchema": BATCH_IMAGE_SCHEMA, "annotations": {"openWorldHint": True, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}},
    {"name": "prepare_video_previews", "description": "Create <=1024px previews for a Codex_DT batch without inspecting or overwriting originals.", "inputSchema": DT_PREVIEW_SCHEMA, "annotations": {"openWorldHint": False, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}},
    {"name": "start_video_batch", "description": "Create a text-first Codex_DT batch and persist its request without submitting paid generation.", "inputSchema": DT_START_BATCH_SCHEMA, "annotations": {"openWorldHint": False, "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False}},
    {"name": "validate_video_batch", "description": "Validate Codex_DT batch manifests and prompt files before generation.", "inputSchema": DT_VALIDATE_BATCH_SCHEMA, "annotations": {"openWorldHint": False, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}},
    {"name": "route_creative_skill", "description": "Resolve a query through the local Codex_Flow compiled skill registry without paid execution.", "inputSchema": FLOW_ROUTE_SCHEMA, "annotations": {"openWorldHint": False, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}},
    {"name": "scout_tools", "description": "Search existing software, MCP servers, plugins, and skills with the bundled Codex_Github Tool Scout.", "inputSchema": TOOL_SCOUT_SCHEMA, "annotations": {"openWorldHint": True, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}},
]


IMAGE_MIME_TYPES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
)


def _image_mime_type(value: bytes) -> str | None:
    for signature, mime_type in IMAGE_MIME_TYPES:
        if value.startswith(signature):
            return mime_type
    if value.startswith(b"RIFF") and value[8:12] == b"WEBP":
        return "image/webp"
    return None


def _successful_image_content(result: dict) -> tuple[list[dict], dict]:
    output_path = Path(result["output_path"]).resolve()
    value = output_path.read_bytes()
    mime_type = _image_mime_type(value)
    if not value or mime_type is None:
        raise ValueError("Generated image output is unavailable or invalid")

    enriched = dict(result)
    enriched["output_path"] = str(output_path)
    enriched["output_uri"] = output_path.as_uri()
    return [
        {"type": "text", "text": json.dumps(enriched, ensure_ascii=False)},
        {"type": "image", "data": base64.b64encode(value).decode("ascii"), "mimeType": mime_type},
        {
            "type": "resource_link",
            "name": output_path.name,
            "title": "Open original image",
            "uri": enriched["output_uri"],
            "mimeType": mime_type,
            "size": len(value),
        },
    ], enriched


def _video_mime_type(output_path: Path, prefix: bytes) -> str | None:
    if prefix[4:8] == b"ftyp":
        return "video/mp4"
    if prefix.startswith(b"RIFF") and prefix[8:12] == b"AVI ":
        return "video/x-msvideo"
    if prefix.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm" if output_path.suffix.lower() == ".webm" else "video/x-matroska"
    return None


def _successful_video_content(result: dict) -> tuple[list[dict], dict]:
    output_path = Path(result["output_path"]).resolve()
    size = output_path.stat().st_size
    with output_path.open("rb") as stream:
        prefix = stream.read(16)
    mime_type = _video_mime_type(output_path, prefix)
    if size <= 0 or mime_type is None:
        raise ValueError("Generated video output is unavailable or invalid")

    enriched = dict(result)
    enriched["output_path"] = str(output_path)
    enriched["output_uri"] = output_path.as_uri()
    return [
        {"type": "text", "text": json.dumps(enriched, ensure_ascii=False)},
        {
            "type": "resource_link",
            "name": output_path.name,
            "title": "Open generated video",
            "uri": enriched["output_uri"],
            "mimeType": mime_type,
            "size": size,
        },
    ], enriched


def _run_process(args: list[str], cwd: Path) -> dict:
    import subprocess
    try:
        completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    except subprocess.TimeoutExpired as exc:
        return {"status": "failed", "failure_class": "timeout", "safe_reason": "tool execution exceeded 900 seconds", "stdout": (exc.stdout or "")[-12000:], "stderr": (exc.stderr or "")[-12000:]}
    return {"status": "success" if completed.returncode == 0 else "failed", "exit_code": completed.returncode, "stdout": completed.stdout[-12000:], "stderr": completed.stderr[-12000:]}


def _dispatch_auxiliary(name: str, arguments: dict) -> dict:
    if name == "convert_video_to_gif":
        root = PROJECT_ROOT.parent / "Codex_Gif"
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "run-video-to-gif.ps1"), "-InputDir", arguments["input_dir"]]
        if arguments.get("output_dir"): args += ["-OutputDir", arguments["output_dir"]]
        for key, flag in (("max_size_mb", "-MaxSizeMB"), ("max_duration_sec", "-MaxDurationSec"), ("min_fps", "-MinFps")):
            if arguments.get(key): args += [flag, str(arguments[key])]
        for key, flag in (("recursive", "-Recursive"), ("overwrite", "-Overwrite")):
            if arguments.get(key): args += [flag]
        return _run_process(args, root)
    if name == "batch_generate_images":
        if not arguments.get("dry_run") and arguments.get("paid_confirmation") != "confirmed":
            return {"status": "failed", "failure_class": "confirmation_required", "safe_reason": "paid_confirmation=confirmed is required for real batch image generation"}
        root = PROJECT_ROOT.parent / "Codex_Batch_Image"
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "run-batch-image-generation.ps1"), "-Manifest", arguments["manifest"]]
        if arguments.get("router_path"): args += ["-RouterPath", arguments["router_path"]]
        if arguments.get("dry_run"): args += ["-DryRun"]
        return _run_process(args, root)
    if name == "prepare_video_previews":
        root = PROJECT_ROOT.parent / "Codex_DT"
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "scripts" / "prepare_previews.ps1"), "-MaxLongEdge", str(arguments.get("max_long_edge", 1024))]
        for key, flag in (("batch", "-Batch"), ("input_directory", "-InputDirectory"), ("output_directory", "-OutputDirectory"), ("preview_tool", "-PreviewTool")):
            if arguments.get(key): args += [flag, str(arguments[key])]
        return _run_process(args, root)
    if name == "start_video_batch":
        root = PROJECT_ROOT.parent / "Codex_DT"
        args = [sys.executable, str(root / "scripts" / "start_text_batch.py"), "--name", arguments["name"], "--duration", str(arguments["duration"]), "--request", arguments["request"]]
        if arguments.get("ratio"): args += ["--ratio", arguments["ratio"]]
        if arguments.get("auto_generate"): args += ["--auto-generate"]
        if arguments.get("model_version"): args += ["--model-version", arguments["model_version"]]
        return _run_process(args, root)
    if name == "validate_video_batch":
        root = PROJECT_ROOT.parent / "Codex_DT"
        args = [sys.executable, str(root / "scripts" / "validate_batch.py")]
        for key, flag in (("batch", "--batch"), ("manifests", "--manifests"), ("tmp", "--tmp")):
            if arguments.get(key): args += [flag, arguments[key]]
        return _run_process(args, root)
    if name == "route_creative_skill":
        root = PROJECT_ROOT.parent / "Codex_Flow"
        args = [sys.executable, str(root / "platform" / "cli.py"), "route", arguments["query"], "--limit", str(arguments.get("limit", 5))]
        if arguments.get("capability"): args += ["--capability", arguments["capability"]]
        return _run_process(args, root)
    if name == "scout_tools":
        root = PROJECT_ROOT.parent / "Codex_Github" / ".claude" / "skills" / "tool-scout"
        args = [sys.executable, str(root / "scripts" / "tool_scout.py"), arguments["need"], "--limit", str(arguments.get("limit", 5)), "--json"]
        if arguments.get("sources"): args += ["--sources", arguments["sources"]]
        return _run_process(args, root)
    raise ValueError("Unknown tool")


def response(identifier, result=None, error=None) -> dict:
    payload = {"jsonrpc": "2.0", "id": identifier}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def _configure_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _write_json(payload: dict) -> None:
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


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
        if name not in {tool["name"] for tool in TOOLS}:
            return response(identifier, error={"code": -32602, "message": "Unknown tool"})
        try:
            if name not in {"generate_image", "generate_video"}:
                result = _dispatch_auxiliary(name, arguments)
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
                return response(identifier, {"content": content, "structuredContent": result, "isError": result.get("status") != "success"})
            if name == "generate_video" and arguments.get("video_execution_mode") == "production_submit_only":
                raise ValueError("production_submit_only is reserved for the trusted Wsstudio batch pipeline")
            if name == "generate_video" and arguments.get("video_execution_mode") == "test_submit_only" and arguments.get("video_test_confirmation") != "confirmed":
                raise ValueError("test_submit_only requires explicit video_test_confirmation=confirmed")
            options = {key: arguments[key] for key in ("image_ratio", "image_resolution", "image_provider", "video_duration", "video_ratio", "video_model", "video_model_selection_source", "video_execution_mode", "video_resolution", "video_confirmation_model", "video_confirmation_resolution", "video_confirmation_duration", "video_prompt_sha256", "video_test_confirmation", "video_count", "video_group") if key in arguments}
            result = execute(name, arguments.get("prompt", ""), arguments.get("images", []), arguments.get("videos", []), arguments.get("audios", []), **options)
        except Exception as exc:
            result = {"status": "failed", "safe_reason": str(exc) or type(exc).__name__}
        try:
            if name == "generate_image" and result.get("status") == "success" and result.get("output_path"):
                content, result = _successful_image_content(result)
            elif name == "generate_video" and result.get("status") == "success" and result.get("output_path"):
                content, result = _successful_video_content(result)
            elif name == "generate_video" and result.get("results"):
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
                enriched_results = []
                for item in result["results"]:
                    if item.get("status") == "success" and item.get("output_path"):
                        item_content, enriched = _successful_video_content(item)
                        content.extend(item_content[1:])
                        enriched_results.append(enriched)
                    else:
                        enriched_results.append(item)
                result = {**result, "results": enriched_results}
            else:
                content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
        except (OSError, ValueError, KeyError):
            safe_reason = "invalid_image_output" if name == "generate_image" else "invalid_video_output"
            result = {**result, "status": "failed", "safe_reason": safe_reason}
            content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
        return response(identifier, {"content": content, "structuredContent": result, "isError": result.get("status") not in {"success", "submitted"}})
    return response(identifier, error={"code": -32601, "message": "Method not found"}) if identifier is not None else None


def main() -> None:
    _configure_stdio()
    for raw_line in sys.stdin.buffer:
        try:
            result = handle(json.loads(raw_line.decode("utf-8")))
            if result is not None:
                _write_json(result)
        except json.JSONDecodeError:
            _write_json(response(None, error={"code": -32700, "message": "Parse error"}))


if __name__ == "__main__":
    main()
