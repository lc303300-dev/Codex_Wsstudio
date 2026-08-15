import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "batch-image-generation" / "scripts" / "run_batch.py"
FAKE = Path(__file__).parent / "fixtures" / "fake_router.py"


class BatchTests(unittest.TestCase):
    def invoke(self, manifest, folder, dry_run=False):
        manifest_path = folder / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, FAKE_ROUTER_LOG=str(folder / "calls.jsonl"), PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-B", str(RUNNER), "--manifest", str(manifest_path), "--router", str(FAKE)]
        if dry_run:
            command.append("--dry-run")
        return subprocess.run(command, text=True, capture_output=True, env=env, timeout=15)

    def test_default_deadline_is_estimate_plus_half(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            manifest = {"batch_id": "timing", "image_ratio": "1:1", "concurrency": 10,
                        "groups": [{"id": "A", "prompt": "one", "candidates": 40}]}
            result = self.invoke(manifest, folder, dry_run=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["seconds_per_image"], 60)
            self.assertEqual(plan["deadline_multiplier"], 1.5)
            self.assertEqual(plan["expected_seconds"], 240)
            self.assertEqual(plan["deadline_seconds"], 360)

    def test_explicit_deadline_overrides_per_image_default(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            manifest = {"batch_id": "override", "image_ratio": "1:1", "deadline_seconds": 75,
                        "groups": [{"id": "A", "prompt": "one", "candidates": 4}]}
            result = self.invoke(manifest, folder, dry_run=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["expected_seconds"], 60)
            self.assertEqual(json.loads(result.stdout)["deadline_seconds"], 75)

    def test_nonpositive_seconds_per_image_is_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            manifest = {"batch_id": "invalid-timing", "image_ratio": "1:1", "seconds_per_image": 0,
                        "groups": [{"id": "A", "prompt": "one", "candidates": 1}]}
            result = self.invoke(manifest, folder)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((folder / "calls.jsonl").exists())

    def test_partial_wave_rounds_up(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            manifest = {"batch_id": "partial-wave", "image_ratio": "1:1", "concurrency": 10,
                        "groups": [{"id": "A", "prompt": "one", "candidates": 11}]}
            result = self.invoke(manifest, folder, dry_run=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["expected_seconds"], 120)
            self.assertEqual(plan["deadline_seconds"], 180)

    def test_ratio_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            result = self.invoke({"groups": [{"id": "A", "prompt": "ok", "candidates": 1}]}, folder)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((folder / "calls.jsonl").exists())

    def test_partial_results_and_fixed_review_sheet(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            original = folder / "original.png"
            Image.new("RGB", (90, 160), "white").save(original)
            manifest = {"batch_id": "b1", "image_ratio": "9:16", "output_dir": "out", "start_delay_seconds": 0.01, "deadline_seconds": 5,
                        "groups": [{"id": "SJ01", "prompt": "ok", "reference_images": [str(original)], "original_image": str(original), "candidates": 2},
                                   {"id": "SJ02", "prompt": "fail", "candidates": 1}]}
            result = self.invoke(manifest, folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((folder / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"], {"success": 2, "failed": 1, "abandoned": 0})
            self.assertEqual(len(summary["review_sheets"]), 2)
            self.assertTrue(all(Path(path).is_file() for path in summary["review_sheets"]))

    def test_deadline_abandons_and_never_resubmits(self):
        with tempfile.TemporaryDirectory() as value:
            folder = Path(value)
            manifest = {"batch_id": "b2", "image_ratio": "9:16", "output_dir": "out", "start_delay_seconds": 0, "deadline_seconds": 0.3,
                        "groups": [{"id": "A", "prompt": "hang", "candidates": 2}]}
            first = self.invoke(manifest, folder)
            self.assertEqual(first.returncode, 0, first.stderr)
            calls = (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 2)
            second = self.invoke(manifest, folder)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(len((folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()), 2)
            db = sqlite3.connect(folder / "out" / "batch-state.sqlite3")
            try:
                self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE status='abandoned'").fetchone()[0], 2)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
