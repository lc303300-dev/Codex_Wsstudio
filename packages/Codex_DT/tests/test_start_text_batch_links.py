from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "start_text_batch.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("start_text_batch", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class StartTextBatchLinkTests(unittest.TestCase):
    def test_markdown_link_target_is_absolute_and_uses_forward_slashes(self) -> None:
        target = module.markdown_link_target(Path("inputs") / "中文 folder")
        self.assertEqual(target, (Path.cwd() / "inputs" / "中文 folder").resolve().as_posix())
        self.assertNotIn("\\", target)
        self.assertFalse(target.startswith("file:"))


if __name__ == "__main__":
    unittest.main()
