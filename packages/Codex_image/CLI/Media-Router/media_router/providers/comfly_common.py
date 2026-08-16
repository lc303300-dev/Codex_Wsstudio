from __future__ import annotations

import json
import mimetypes
import os
import socket
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from time import monotonic

from ..config import PRIVATE_ROOT
from ..errors import FailureClass, MediaRouterError
from ..output_validation import atomic_write_bytes


BASE_URL = "https://ai.comfly.org/v1"
GENERATIONS_URL = f"{BASE_URL}/images/generations"
EDITS_URL = f"{BASE_URL}/images/edits"
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://ai.comfly.org/",
}
GEMINI_RESOLUTION_PROFILE = "gemini-resolution"
GEMINI_LITE_1K_SIZES = {
    "1:1": "1024x1024",
    "2:3": "848x1264",
    "3:2": "1264x848",
    "3:4": "896x1200",
    "4:3": "1200x896",
    "4:5": "928x1152",
    "5:4": "1152x928",
    "9:16": "768x1376",
    "16:9": "1376x768",
    "21:9": "1584x672",
}
GEMINI_LITE_DEFAULT_SIZE = GEMINI_LITE_1K_SIZES["1:1"]
GPT_IMAGE_2_SIZES = {
    "1K": {
        "21:9": "1280x544",
        "16:9": "1280x720",
        "3:2": "1200x800",
        "4:3": "1152x864",
        "1:1": "1024x1024",
        "3:4": "864x1152",
        "2:3": "800x1200",
        "9:16": "720x1280",
    },
    "2K": {
        "21:9": "2048x880",
        "16:9": "2048x1152",
        "3:2": "1920x1280",
        "4:3": "1920x1440",
        "1:1": "2048x2048",
        "3:4": "1440x1920",
        "2:3": "1280x1920",
        "9:16": "1152x2048",
    },
    "4K": {
        "21:9": "3840x1648",
        "16:9": "3840x2160",
        "3:2": "3520x2352",
        "4:3": "3312x2480",
        "1:1": "2880x2880",
        "3:4": "2480x3312",
        "2:3": "2352x3520",
        "9:16": "2160x3840",
    },
}


def _is_timeout_error(exc: BaseException) -> bool:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    return isinstance(reason, (TimeoutError, socket.timeout))


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def api_key() -> str | None:
    return os.environ.get("COMFLY_API_KEY") or load_dotenv(PRIVATE_ROOT / ".env").get("COMFLY_API_KEY")


def opener() -> urllib.request.OpenerDirector:
    values = load_dotenv(PRIVATE_ROOT / ".env")
    proxies = {}
    for scheme, key in (("http", "HTTP_PROXY"), ("https", "HTTPS_PROXY")):
        value = os.environ.get(key) or values.get(key)
        if value:
            proxies[scheme] = value
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def normalize_size(model: str, size: str | None, size_profile: str | None = None, resolution: str = "1K") -> str:
    value = (size or "").strip()
    if model == "gpt-image-2":
        sizes = GPT_IMAGE_2_SIZES.get(resolution.upper())
        if sizes is None:
            raise MediaRouterError("Unsupported image resolution: " + resolution, FailureClass.INPUT_ERROR)
        if not value or value.upper() in {"1K", "2K", "4K"}:
            return sizes["1:1"]
        if value in sizes:
            return sizes[value]
        if value in sizes.values():
            return value
        raise MediaRouterError(
            f"{model} requires a supported aspect ratio for {resolution.upper()} output",
            FailureClass.INPUT_ERROR,
        )
    if size_profile != GEMINI_RESOLUTION_PROFILE:
        return value or "1024x1024"
    scale = {"1K": 1, "2K": 2, "4K": 4}.get(resolution.upper())
    if scale is None:
        raise MediaRouterError("Unsupported image resolution: " + resolution, FailureClass.INPUT_ERROR)
    if not value or value.upper() in {"1K", "2K", "4K"}:
        width, height = (int(part) for part in GEMINI_LITE_DEFAULT_SIZE.split("x"))
        return f"{width * scale}x{height * scale}"
    if value in GEMINI_LITE_1K_SIZES:
        width, height = (int(part) for part in GEMINI_LITE_1K_SIZES[value].split("x"))
        return f"{width * scale}x{height * scale}"
    allowed_sizes = set(GEMINI_LITE_1K_SIZES.values()) if scale == 1 else set()
    if value in allowed_sizes:
        return value
    raise MediaRouterError(
        f"{model} requires a supported aspect ratio for {resolution.upper()} output",
        FailureClass.INPUT_ERROR,
    )


def json_body(model: str, prompt: str, size: str, size_profile: str | None = None, resolution: str = "1K") -> bytes:
    size = normalize_size(model, size, size_profile, resolution)
    payload = {"model": model, "prompt": prompt, "n": 1, "size": size, "response_format": "url"}
    if model != "gpt-image-2":
        payload["resolution"] = resolution.lower()
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def multipart_body(model: str, prompt: str, size: str, images: tuple[Path, ...], boundary: str | None = None, size_profile: str | None = None, resolution: str = "1K") -> tuple[bytes, str]:
    size = normalize_size(model, size, size_profile, resolution)
    boundary = boundary or f"----CodexMedia{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    fields = [("model", model), ("prompt", prompt), ("n", "1"), ("size", size)]
    if model != "gpt-image-2":
        fields.append(("resolution", resolution.lower()))
    fields.append(("response_format", "url"))
    for name, value in fields:
        chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(), value.encode("utf-8"), b"\r\n"]
    for index, path in enumerate(images, 1):
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks += [f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="image"; filename="reference-{index}{path.suffix}"\r\nContent-Type: {mime}\r\n\r\n'.encode("ascii"), path.read_bytes(), b"\r\n"]
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def extract_url(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict) and isinstance(data[0].get("url"), str) and data[0]["url"].strip():
        return data[0]["url"].strip()
    raise MediaRouterError("Provider returned no downloadable image URL", FailureClass.DEFINITE_PROVIDER_FAILURE, submitted=True)


def request_id(headers, payload: dict) -> str | None:
    for name in ("x-request-id", "request-id", "cf-ray"):
        value = headers.get(name)
        if value:
            return str(value)
    for name in ("request_id", "task_id", "id"):
        if payload.get(name):
            return str(payload[name])
    return None


def execute_once(model: str, prompt: str, images: tuple[Path, ...], output: Path, size: str = "1024x1024", timeout: float = 180, deadline: float | None = None, timeout_failure: FailureClass | None = None, size_profile: str | None = None, resolution: str = "1K") -> dict:
    def remaining() -> float:
        value = min(timeout, deadline - monotonic()) if deadline is not None else timeout
        if value <= 0:
            raise MediaRouterError("Image provider exceeded its deadline", timeout_failure or FailureClass.INDETERMINATE_SUBMISSION, submitted=True)
        return max(0.001, value)

    key = api_key()
    if not key:
        raise MediaRouterError("COMFLY_API_KEY is not configured", FailureClass.AUTH_UNAVAILABLE)
    client = opener()
    if images:
        endpoint = EDITS_URL
        try:
            body, content_type = multipart_body(model, prompt, size, images, size_profile=size_profile, resolution=resolution)
        except OSError as exc:
            raise MediaRouterError("A local reference image could not be read", FailureClass.INPUT_ERROR) from exc
    else:
        endpoint = GENERATIONS_URL
        body, content_type = json_body(model, prompt, size, size_profile, resolution), "application/json; charset=utf-8"
    request = urllib.request.Request(endpoint, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": content_type, "Accept": "application/json"}, method="POST")
    try:
        with client.open(request, timeout=remaining()) as response:
            headers = response.headers
            payload = json.loads(response.read().decode("utf-8"))
        url = extract_url(payload)
    except urllib.error.HTTPError as exc:
        failure = FailureClass.AUTH_UNAVAILABLE if exc.code in (401, 403) else FailureClass.QUOTA_UNAVAILABLE if exc.code in (402, 429) else FailureClass.POLICY_REJECTION if exc.code in (400, 422) else FailureClass.DEFINITE_PROVIDER_FAILURE
        raise MediaRouterError(f"Comfly request failed with HTTP {exc.code}", failure, submitted=exc.code not in (401, 403)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        timed_out = bool(timeout_failure and (_is_timeout_error(exc) or (deadline is not None and monotonic() >= deadline)))
        failure = timeout_failure if timed_out else FailureClass.INDETERMINATE_SUBMISSION
        raise MediaRouterError("Comfly submission timed out" if timed_out else "Comfly submission outcome is unknown", failure, submitted=True) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise MediaRouterError("Comfly returned an invalid response", FailureClass.DEFINITE_PROVIDER_FAILURE, submitted=True) from exc
    try:
        download = urllib.request.Request(url, headers=DOWNLOAD_HEADERS, method="GET")
        with client.open(download, timeout=remaining()) as response:
            content_type = response.headers.get("Content-Type", "")
            value = response.read()
        signature_ok = value.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8")) or (value.startswith(b"RIFF") and value[8:12] == b"WEBP")
        if not value or (not content_type.lower().startswith("image/") and not signature_ok):
            raise ValueError("not an image")
        atomic_write_bytes(output, value)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        timed_out = bool(timeout_failure and (_is_timeout_error(exc) or (deadline is not None and monotonic() >= deadline)))
        failure = timeout_failure if timed_out else FailureClass.DOWNLOAD_FAILURE
        raise MediaRouterError("Comfly image download timed out" if failure == timeout_failure else "Comfly image download failed", failure, submitted=True) from exc
    return {"request_id": request_id(headers, payload), "source_url": url, "output_bytes": output.stat().st_size}
