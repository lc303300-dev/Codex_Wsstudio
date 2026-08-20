from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one provider-facing image")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--max-long-edge", type=int, default=1920)
    parser.add_argument("--max-bytes", type=int, default=4_500_000)
    args = parser.parse_args()
    if args.max_long_edge < 1:
        raise ValueError("max-long-edge must be greater than 0")
    if args.max_bytes < 1:
        raise ValueError("max-bytes must be greater than 0")

    source_path = Path(args.input).resolve(strict=True)
    output_path = Path(args.output).resolve()
    metadata_path = Path(args.metadata).resolve()
    with Image.open(source_path) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
    original_width, original_height = image.size
    resized = max(image.size) > args.max_long_edge
    byte_reencoded = source_path.stat().st_size > args.max_bytes

    if resized or byte_reencoded:
        image.thumbnail((args.max_long_edge, args.max_long_edge), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output_path.stem}.", suffix=".tmp.png", dir=output_path.parent)
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            try:
                image.save(temporary_path, format="PNG", optimize=True)
                if temporary_path.stat().st_size <= args.max_bytes:
                    temporary_path.replace(output_path)
                    break
                next_width = max(1, int(image.width * 0.9))
                next_height = max(1, int(image.height * 0.9))
                if (next_width, next_height) == image.size:
                    raise ValueError("Cannot compress provider image below max-bytes")
                image = image.resize((next_width, next_height), Image.Resampling.LANCZOS)
                resized = True
            finally:
                temporary_path.unlink(missing_ok=True)
        provider_path = output_path
    else:
        provider_path = source_path

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "provider_path": str(provider_path),
        "resized": resized,
        "original_width": original_width,
        "original_height": original_height,
        "provider_width": image.width,
        "provider_height": image.height,
        "max_long_edge": args.max_long_edge,
        "max_bytes": args.max_bytes,
        "provider_bytes": provider_path.stat().st_size,
        "byte_reencoded": byte_reencoded,
    }
    temporary_metadata = metadata_path.with_name(f".{metadata_path.name}.tmp")
    temporary_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_metadata.replace(metadata_path)


if __name__ == "__main__":
    main()
