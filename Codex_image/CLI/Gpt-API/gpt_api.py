import argparse
import hashlib
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "https://api.apimart.ai/v1"
GENERATIONS_URL = f"{BASE_URL}/images/generations"


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"").strip("'")
    return values


def default_workspace() -> Path:
    return Path(__file__).resolve().parents[2] / ".codex-image-private"


def read_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Prompt must not be empty")
    return prompt.strip()


def opener_for(env_values: dict[str, str]) -> urllib.request.OpenerDirector:
    proxies: dict[str, str] = {}
    http_proxy = os.environ.get("HTTP_PROXY") or env_values.get("HTTP_PROXY")
    https_proxy = os.environ.get("HTTPS_PROXY") or env_values.get("HTTPS_PROXY")
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def local_image_data_uri(path: Path) -> str:
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError(f"GPT Image reference exceeds 20 MB: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def request_json(opener: urllib.request.OpenerDirector, request: urllib.request.Request, timeout: float) -> tuple[int, dict]:
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": {"message": body}}
        raise RuntimeError(f"APIMart HTTP {exc.code}: {payload}") from exc


def task_id_from(payload: dict) -> str:
    data = payload.get("data") or []
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("task_id"):
        return str(data[0]["task_id"])
    raise RuntimeError(f"APIMart response contains no task_id: {payload}")


def image_url_from(payload: dict) -> str:
    data = payload.get("data") or {}
    images = (data.get("result") or {}).get("images") or []
    for image in images:
        urls = image.get("url") or []
        if isinstance(urls, str):
            return urls
        if urls:
            return str(urls[0])
    raise RuntimeError(f"Completed APIMart task contains no image URL: {payload}")


def sanitized(payload: object) -> object:
    if isinstance(payload, dict):
        clean = {}
        for key, value in payload.items():
            if key == "prompt" and isinstance(value, str):
                clean[key] = {"value": "<redacted>", "characters": len(value), "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
            elif key == "image_urls" and isinstance(value, list):
                clean[key] = ["<local image data omitted>" if str(item).startswith("data:") else item for item in value]
            else:
                clean[key] = sanitized(value)
        return clean
    if isinstance(payload, list):
        return [sanitized(value) for value in payload]
    return payload


def write_log(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("APIMart GPT Image task did not complete within the configured timeout")
    return remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent APIMart GPT Image 2 pipeline")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    parser.add_argument("--image", action="append", default=[], help="Local reference image; repeat to preserve order")
    parser.add_argument("--image-url", action="append", default=[], help="Public reference URL; repeat to preserve order")
    parser.add_argument("--out", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--workspace", default=str(default_workspace()), help="Private runtime root containing .env")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--size", default="16:9")
    parser.add_argument("--resolution", default="1k", choices=["1k", "2k", "4k"])
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--poll-timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt = read_prompt(args)
    workspace = Path(args.workspace).resolve()
    env_path = workspace / ".env"
    env_values = load_dotenv(env_path)
    api_key = os.environ.get("APIMART_API_KEY") or env_values.get("APIMART_API_KEY")
    image_paths = [Path(value).resolve() for value in args.image]
    missing = [str(path) for path in image_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing reference images: " + "; ".join(missing))
    if len(image_paths) + len(args.image_url) > 16:
        raise ValueError("GPT Image 2 accepts at most 16 reference images")

    payload = {
        "model": args.model,
        "prompt": prompt,
        "n": 1,
        "size": args.size,
        "resolution": args.resolution,
        "official_fallback": False,
    }
    references = [str(path) for path in image_paths] + list(args.image_url)
    if references and not args.dry_run:
        payload["image_urls"] = [local_image_data_uri(path) for path in image_paths] + list(args.image_url)

    log_path = Path(args.log).resolve()
    report = {
        "provider": "APIMart GPT Image 2",
        "endpoint": GENERATIONS_URL,
        "request": sanitized(payload),
        "references": references,
        "shared_env": str(env_path),
        "attempts": [],
    }
    if args.dry_run:
        report.update(dry_run=True, api_key_configured=bool(api_key))
        write_log(log_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if not api_key:
        raise RuntimeError(f"APIMART_API_KEY not found in environment or shared file: {env_path}")

    opener = opener_for(env_values)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    submit_request = urllib.request.Request(GENERATIONS_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    deadline = time.monotonic() + args.poll_timeout
    try:
        status_code, submit_payload = request_json(opener, submit_request, min(args.timeout, remaining_seconds(deadline)))
        report["attempts"].append({"action": "submit", "status_code": status_code, "response": submit_payload})
        task_id = task_id_from(submit_payload)
        report["task_id"] = task_id

        final_payload: dict | None = None
        while time.monotonic() < deadline:
            query_url = f"{BASE_URL}/tasks/{task_id}?language=en"
            query_request = urllib.request.Request(query_url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
            query_status, query_payload = request_json(opener, query_request, min(args.timeout, remaining_seconds(deadline)))
            task = query_payload.get("data") or {}
            state = str(task.get("status", "")).lower()
            report["attempts"].append({"action": "query", "status_code": query_status, "task_status": state, "progress": task.get("progress")})
            if state == "completed":
                final_payload = query_payload
                break
            if state in {"failed", "cancelled"}:
                report.update(status="failed", final_response=query_payload)
                write_log(log_path, report)
                raise RuntimeError(f"APIMart GPT Image task ended with status {state}: {task.get('error')}")
            time.sleep(min(max(1, args.poll_interval), remaining_seconds(deadline)))
        if final_payload is None:
            raise TimeoutError("APIMart GPT Image task did not complete within the configured timeout")

        image_url = image_url_from(final_payload)
        with opener.open(image_url, timeout=min(args.timeout, remaining_seconds(deadline))) as response:
            image_bytes = response.read()
    except TimeoutError as exc:
        report.update(status="timeout", failure_reason=f"Task did not complete within {args.poll_timeout} seconds")
        write_log(log_path, report)
        raise TimeoutError(report["failure_reason"]) from exc
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    if out_path.stat().st_size == 0:
        raise RuntimeError("Downloaded APIMart GPT Image output is empty")
    report.update(status="success", final_response=final_payload, output=str(out_path), output_bytes=out_path.stat().st_size, source_url=image_url)
    write_log(log_path, report)
    print(str(out_path))


if __name__ == "__main__":
    main()
