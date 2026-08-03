import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def read_prompt(args: argparse.Namespace) -> str:
    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError("Prompt must not be empty")
    return prompt.strip()


def write_log(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prompt_summary(prompt: str) -> dict:
    return {"value": "<redacted>", "characters": len(prompt), "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent Antigravity CLI image pipeline")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file")
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prompt = read_prompt(args)
    images = [Path(value).resolve() for value in args.image]
    missing = [str(path) for path in images if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing reference images: " + "; ".join(missing))
    out_path = Path(args.out).resolve()
    log_path = Path(args.log).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = Path(__file__).resolve().with_name("agy-proxy.ps1")

    reference_text = "\n".join(f"Reference {index + 1}: {path}" for index, path in enumerate(images)) or "No reference images."
    goal = (
        "Generate exactly one high-quality still image.\n"
        f"Save the final image as a local file at this exact absolute path: {out_path}\n"
        "Do not only describe the image and do not return a remote URL.\n"
        f"Use the references in this exact order:\n{reference_text}\n\n"
        f"Image prompt:\n{prompt}\n\n"
        "If image generation is unavailable, state the concrete reason and do not invoke another provider."
    )
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper),
        "--dangerously-skip-permissions",
        "--add-dir", str(out_path.parent),
    ]
    for directory in dict.fromkeys(str(path.parent) for path in images):
        command.extend(["--add-dir", directory])
    command.extend(["--print-timeout", f"{args.timeout}s", "--print", f"/goal {goal}"])
    report = {"provider": "Google Antigravity CLI", "prompt": prompt_summary(prompt), "reference_count": len(images), "output": str(out_path)}
    if args.dry_run:
        report["dry_run"] = True
        write_log(log_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout, check=False)
        report.update(exit_code=completed.returncode, transcript="<redacted>")
    except subprocess.TimeoutExpired as exc:
        report.update(status="timeout", transcript="<redacted>")
        write_log(log_path, report)
        raise TimeoutError(f"Antigravity did not finish within {args.timeout} seconds") from exc

    if report["exit_code"] != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        report.update(status="failed", failure_reason="Antigravity returned no usable local image")
        write_log(log_path, report)
        raise RuntimeError(report["failure_reason"])
    report.update(status="success", output_bytes=out_path.stat().st_size)
    write_log(log_path, report)
    print(str(out_path))


if __name__ == "__main__":
    main()
