from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("comfly_api.py")
SPEC = importlib.util.spec_from_file_location("comfly_api", MODULE_PATH)
comfly_api = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(comfly_api)


class ComflyCliTests(unittest.TestCase):
    def test_models_are_explicit_and_fixed(self):
        self.assertEqual(comfly_api.MODELS, ("gemini-3.1-flash-lite-image", "gpt-image-2-all", "gpt-image-2"))
        self.assertFalse(hasattr(comfly_api, "MODEL_PRIORITY"))

    def test_prompt_summary_is_redacted(self):
        value = comfly_api.prompt_summary("private complete prompt")
        self.assertEqual(value["value"], "<redacted>")
        self.assertNotIn("private", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
