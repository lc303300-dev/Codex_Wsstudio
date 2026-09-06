from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("environment_motion", SCRIPT_ROOT / "environment_motion.py")
assert SPEC and SPEC.loader
environment_motion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment_motion)


class EnvironmentMotionTests(unittest.TestCase):
    def test_only_recognized_elements_receive_strategies(self) -> None:
        result = environment_motion.compile_environment_motion({
            "description_zh": "湖边有芦苇，水面映出树木倒影，远处是一座静止的建筑。",
            "movable_elements": ["芦苇", "水面"],
        })
        self.assertTrue(result["detected"])
        self.assertEqual([item["key"] for item in result["elements"]], ["plants", "water_surface", "reflection"])
        self.assertTrue(any("微风" in line for line in result["motion_lines_zh"]))
        self.assertTrue(any("波纹" in line for line in result["motion_lines_zh"]))

    def test_no_match_is_a_noop_payload(self) -> None:
        result = environment_motion.compile_environment_motion({"description_zh": "室内白墙和木桌"})
        self.assertFalse(result["detected"])
        self.assertEqual(result["prompt_section_zh"], "")
        self.assertEqual(result["forge_queries_zh"], [])

    def test_apply_preserves_existing_queries_and_deduplicates(self) -> None:
        manifest = {
            "visual": {"description_zh": "阳台盆栽，窗外小池塘"},
            "motion_plan": {"environment_motion_zh": ["已有导演要求"]},
            "forge": {
                "queries_zh": ["固定机位"],
                "matches": [{"id": "camera", "title": "推镜技巧", "content_preview": "镜头推进"}],
            },
        }
        updated = environment_motion.apply_to_manifest(manifest)
        self.assertEqual(updated["motion_plan"]["environment_motion_zh"][0], "已有导演要求")
        self.assertIn("固定机位", updated["forge"]["queries_zh"])
        self.assertIn("plants", updated["environment_motion"]["elements"][0]["key"])
        self.assertEqual(len(updated["forge"]["queries_zh"]), len(set(updated["forge"]["queries_zh"])))
        self.assertEqual(updated["forge"]["matches"], [])
        self.assertEqual(updated["forge"]["corpus_scope"], "environmental_motion_only")

    def test_prompt_section_contains_stability_constraints(self) -> None:
        result = environment_motion.compile_environment_motion({"main_subjects": ["树木", "湖面"]})
        section = environment_motion.render_prompt_section(result)
        self.assertIn("保持原始构图", section)
        self.assertIn("不让静态建筑", section)

    def test_corpus_sanitizer_removes_camera_only_records(self) -> None:
        matches = [
            {"id": "camera", "title": "推镜与景深技巧", "content_preview": "镜头缓慢推进，使用广角镜头。"},
            {
                "id": "mixed",
                "title": "风吹芦苇",
                "content_preview": "镜头缓慢推进。微风吹过芦苇，叶片轻轻摆动，水面形成连续波纹。",
            },
        ]
        cleaned = environment_motion.sanitize_corpus_matches(matches)
        self.assertEqual([item["id"] for item in cleaned], ["mixed"])
        self.assertNotIn("镜头缓慢推进", cleaned[0]["content_preview"])
        self.assertIn("叶片轻轻摆动", cleaned[0]["content_preview"])
        self.assertTrue(cleaned[0]["environmental_motion_only"])

    def test_corpus_sanitizer_drops_generic_style_pollution(self) -> None:
        result = environment_motion.sanitize_corpus_match({
            "title": "电影感自然风光",
            "content_preview": "电影感构图，胶片颗粒，色调高级。",
        })
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
