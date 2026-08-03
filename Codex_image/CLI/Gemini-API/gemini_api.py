import argparse
import base64
import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def private_root() -> Path:
    return Path(__file__).resolve().parents[2] / ".codex-image-private"


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Prompt must not be empty")
    return prompt.strip()


def image_part(path: Path) -> dict:
    return {
        "type": "image",
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "mime_type": mimetypes.guess_type(path.name)[0] or "image/png",
    }


def opener_for(env_values: dict[str, str]) -> urllib.request.OpenerDirector:
    proxies: dict[str, str] = {}
    http_proxy = os.environ.get("HTTP_PROXY") or env_values.get("HTTP_PROXY")
    https_proxy = os.environ.get("HTTPS_PROXY") or env_values.get("HTTPS_PROXY")
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def extract_image(payload: dict) -> tuple[str, str]:
    direct = [payload.get("output_image", {}), payload.get("output", {}).get("image", {})]
    for item in direct:
        if isinstance(item, dict) and item.get("data"):
            return item["data"], item.get("mime_type", "image/jpeg")

    def walk(value: object) -> tuple[str, str] | None:
        if isinstance(value, dict):
            mime_type = str(value.get("mime_type", ""))
            if value.get("data") and (value.get("type") == "image" or mime_type.startswith("image/")):
                return str(value["data"]), mime_type or "image/jpeg"
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None

    found = walk(payload)
    if not found:
        raise RuntimeError("No image data found in Gemini response")
    return found


def sanitized(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: (f"<omitted {len(value)} base64 characters>" if key == "data" and isinstance(value, str) and len(value) > 200 else sanitized(value))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [sanitized(value) for value in payload]
    return payload


def write_log(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent official Google Gemini image pipeline")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--env-file", default=str(private_root() / ".env"))
    parser.add_argument("--model", default="gemini-3.1-flash-image")
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--image-size", default="1K")
    parser.add_argument("--mime-type", default="image/jpeg")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt = read_prompt(args)
    env_path = Path(args.env_file).resolve()
    env_values = load_dotenv(env_path)
    api_key = os.environ.get("GEMINI_API_KEY") or env_values.get("GEMINI_API_KEY")
    image_paths = [Path(value).resolve() for value in args.image]
    missing = [str(path) for path in image_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing reference images: " + "; ".join(missing))

    request_summary = {
        "provider": "Google Gemini official API",
        "endpoint": API_URL,
        "model": args.model,
        "prompt": {"value": "<redacted>", "characters": len(prompt), "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()},
        "references": [str(path) for path in image_paths],
        "response_format": {"type": "image", "mime_type": args.mime_type, "aspect_ratio": args.aspect_ratio, "image_size": args.image_size},
        "env_file": str(env_path),
    }
    log_path = Path(args.log).resolve()
    if args.dry_run:
        request_summary.update(dry_run=True, api_key_configured=bool(api_key))
        write_log(log_path, request_summary)
        print(json.dumps(request_summary, ensure_ascii=False, indent=2))
        return
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY not found in environment or {env_path}")

    input_parts = [{"type": "text", "text": prompt}]
    input_parts.extend(image_part(path) for path in image_paths)
    request_body = {"model": args.model, "input": input_parts, "response_format": request_summary["response_format"]}
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener_for(env_values).open(request, timeout=args.timeout) as response:
            status_code = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError as exc:
        write_log(log_path, {**request_summary, "status": "timeout", "failure_reason": f"Request did not complete within {args.timeout} seconds"})
        raise TimeoutError(f"Google Gemini request did not complete within {args.timeout} seconds") from exc
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            error_body = json.loads(body)
        except json.JSONDecodeError:
            error_body = body
        write_log(log_path, {**request_summary, "status": "failed", "status_code": exc.code, "response": sanitized(error_body)})
        raise RuntimeError(f"Google Gemini request failed with HTTP {exc.code}") from exc

    image_b64, response_mime = extract_image(payload)
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(image_b64))
    if out_path.stat().st_size == 0:
        raise RuntimeError("Gemini output file is empty")
    write_log(log_path, {**request_summary, "status": "success", "status_code": status_code, "response_mime_type": response_mime, "response": sanitized(payload), "output": str(out_path), "output_bytes": out_path.stat().st_size})
    print(str(out_path))


if __name__ == "__main__":
    main()
