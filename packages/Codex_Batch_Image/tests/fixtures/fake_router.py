import argparse
import json
import os
import time
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("command")
parser.add_argument("--prompt", required=True)
parser.add_argument("--image", action="append", default=[])
parser.add_argument("--image-ratio", required=True)
args = parser.parse_args()
log = Path(os.environ["FAKE_ROUTER_LOG"])
with log.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"prompt": args.prompt, "images": args.image, "started": time.monotonic()}) + "\n")
if args.prompt.startswith("hang"):
    time.sleep(30)
if args.prompt.startswith("fail"):
    print(json.dumps({"status": "failed", "failure_class": "definite_provider_failure"}))
    raise SystemExit(2)
output = log.parent / (args.prompt.replace(" ", "_") + ".png")
Image.new("RGB", (90, 160), "#4477aa").save(output)
print(json.dumps({"status": "success", "output_path": str(output), "provider_id": "fake", "model_id": "fake-v1"}))
