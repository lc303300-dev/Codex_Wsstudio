#!/usr/bin/env python3
"""Regression tests for Codex_DT's explicit Seedance 2.0 selection gate."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_policy import build_model_selection, normalize_model, validate_manifest


def manifest(model: str = "seedance2.5", selection: dict | None = None, duration: int = 8, resolution: str = "480p") -> dict:
    compile_data = {
        "model_version": model,
        "duration": duration,
        "ratio": "16:9",
        "resolution": resolution,
    }
    if selection is not None:
        compile_data["model_selection"] = selection
    return {"mqrox_compile": compile_data}


class ModelPolicyTests(unittest.TestCase):
    def test_default_is_seedance25(self) -> None:
        self.assertEqual(normalize_model(None), "seedance2.5")
        result = validate_manifest(manifest())
        self.assertEqual(result["model_version"], "seedance2.5")
        self.assertEqual(result["selection_source"], "default")

    def test_aliases_are_canonicalized(self) -> None:
        self.assertEqual(normalize_model("seedance-2.5"), "seedance2.5")
        self.assertEqual(normalize_model("seedance-2.0"), "seedance2.0_vip")

    def test_explicit_seedance20_is_allowed(self) -> None:
        selection = build_model_selection("2.0", explicit=True, user_text="请使用即梦 2.0")
        result = validate_manifest(manifest("seedance2.0_vip", selection))
        self.assertEqual(result["selection_source"], "user_explicit")

    def test_stale_seedance20_without_evidence_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "no model_selection evidence"):
            validate_manifest(manifest("seedance2.0_vip"))

    def test_non_explicit_seedance20_is_refused(self) -> None:
        selection = {"requested": "seedance2.0_vip", "selection_source": "default"}
        with self.assertRaisesRegex(ValueError, "selection_source must be user_explicit"):
            validate_manifest(manifest("seedance2.0_vip", selection))

    def test_seedance20_without_cli_evidence_is_refused(self) -> None:
        selection = {"requested": "seedance2.0_vip", "selection_source": "user_explicit"}
        with self.assertRaisesRegex(ValueError, "selection_evidence must be cli_option"):
            validate_manifest(manifest("seedance2.0_vip", selection))

    def test_model_selection_conflict_is_refused(self) -> None:
        selection = build_model_selection("seedance2.5", explicit=False)
        with self.assertRaisesRegex(ValueError, "conflicts with model_version"):
            validate_manifest(manifest("seedance2.0_vip", selection))

    def test_seedance20_uses_conservative_duration_limit(self) -> None:
        selection = build_model_selection("seedance2.0mini", explicit=True)
        with self.assertRaisesRegex(ValueError, "conservatively limited"):
            validate_manifest(manifest("seedance2.0mini", selection, duration=20))

    def test_unknown_model_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported video model"):
            validate_manifest(manifest("mystery-model"))


if __name__ == "__main__":
    unittest.main()
