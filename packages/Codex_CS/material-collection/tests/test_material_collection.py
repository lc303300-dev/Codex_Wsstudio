import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("material_collection", ROOT / "material_collection.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class MaterialCollectionTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "skill_id": "demo",
            "display_name": "演示 Skill",
            "references": [
                {"id": "identity", "media_type": "image", "role": "identity", "description": "主体设定图", "required": True, "min_count": 1, "max_count": 1, "ordered": True, "observation_required": True},
                {"id": "music", "media_type": "audio", "role": "music", "description": "背景音乐", "required": False, "min_count": 0, "max_count": 1, "ordered": False, "observation_required": False},
            ],
        }

    def test_selected_skill_guides_materials(self):
        state = module.build_collection_state(self.contract)
        self.assertEqual(state["state"], "skill_selected")
        text = module.render_guidance(state)
        self.assertIn("主体设定图", text)
        self.assertIn("必选", text)

    def test_missing_only_and_ready(self):
        state = module.build_collection_state(self.contract, {"identity": 1})
        self.assertEqual(state["state"], "materials_ready")
        self.assertIn("已经齐全", module.render_guidance(state, only_missing=True))

    def test_too_many_is_invalid(self):
        state = module.build_collection_state(self.contract, {"identity": 2})
        self.assertEqual(state["invalid_slots"], ["identity"])
        self.assertIn("数量超限", module.render_guidance(state, only_missing=True))


if __name__ == "__main__":
    unittest.main()
