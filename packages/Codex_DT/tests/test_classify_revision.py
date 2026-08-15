from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "classify_revision.py"
SPEC = importlib.util.spec_from_file_location("classify_revision", SCRIPT)
assert SPEC and SPEC.loader
classify_revision = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(classify_revision)


def payload(feedback: str) -> dict:
    return {
        "current_prompt": "图片1锁定主体。第二镜头环绕主体，结尾定格。",
        "user_feedback": feedback,
        "locked_context": {
            "contract_rules": ["图片1锁定主体身份", "禁止改变 Logo 文字"],
            "material_order": ["图片1: logo-design", "图片2: landmark-scenes/01"],
            "ratio": "16:9",
            "duration_seconds": 10,
        },
    }


class ClassifyRevisionTests(unittest.TestCase):
    def test_explicit_local_skips_corpus(self) -> None:
        result = classify_revision.build_revision_request(payload("第二镜不要环绕，改成低机位向前推进。"))
        self.assertEqual(result["classification"], "explicit_local")
        self.assertFalse(result["should_search_corpus"])
        self.assertEqual(result["corpus_search"]["max_results"], 0)

    def test_parameter_change_is_explicit_local(self) -> None:
        result = classify_revision.build_revision_request(payload("把时长从 10 秒改成 8 秒。"))
        self.assertEqual(result["classification"], "explicit_local")

    def test_ambiguous_creative_requests_up_to_three_matches(self) -> None:
        result = classify_revision.build_revision_request(payload("整体不够震撼，想要更有电影感。"))
        self.assertEqual(result["classification"], "ambiguous_creative")
        self.assertTrue(result["should_search_corpus"])
        self.assertEqual(result["corpus_search"]["max_results"], 3)

    def test_structural_rewrite_takes_priority(self) -> None:
        result = classify_revision.build_revision_request(payload("重新编排全部镜头顺序，重构整段叙事。"))
        self.assertEqual(result["classification"], "structural_rewrite")
        self.assertTrue(result["should_search_corpus"])

    def test_unknown_feedback_is_conservatively_ambiguous(self) -> None:
        result = classify_revision.build_revision_request(payload("我想换一种表达。"))
        self.assertEqual(result["classification"], "ambiguous_creative")

    def test_locked_context_is_preserved_and_hashed(self) -> None:
        source = payload("删除字幕。")
        result = classify_revision.build_revision_request(source)
        self.assertEqual(result["locked_context"], source["locked_context"])
        self.assertEqual(len(result["locked_context_sha256"]), 64)
        self.assertTrue(result["revision_policy"]["contract_rules_are_immutable"])
        self.assertTrue(result["revision_policy"]["material_order_is_immutable"])

    def test_rejects_invalid_locked_context(self) -> None:
        source = payload("删除字幕。")
        source["locked_context"]["ratio"] = "adaptive"
        with self.assertRaises(ValueError):
            classify_revision.build_revision_request(source)


if __name__ == "__main__":
    unittest.main()
