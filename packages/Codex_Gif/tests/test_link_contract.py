from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "convert-video-to-gif.ps1"


class GifLinkContractTests(unittest.TestCase):
    def test_output_folder_markdown_target_normalizes_windows_separators(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8-sig")
        function = text.split("function Get-MarkdownFileLink", 1)[1].split("$ffmpeg =", 1)[0]
        self.assertIn(".Replace('\\', '/')", function)
        self.assertIn('return "[$Label](<$fullPath>)"', function)


if __name__ == "__main__":
    unittest.main()
