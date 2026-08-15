from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import registry


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_skill(library: Path, skill_id: str, display_name: str, description: str, routing: dict | None = None) -> Path:
    root = library / skill_id
    root.mkdir()
    (root / "SKILL.md").write_text(f"---\nname: {skill_id}\ndescription: {description}\n---\n", encoding="utf-8")
    write_json(root / "contract.json", {
        "schema_version": 1, "skill_id": skill_id, "display_name": display_name, "description": description,
        "references": [{"id": "scene", "media_type": "image", "description": "场景参考", "required": True, "min_count": 1, "max_count": None, "ordered": True}],
    })
    if routing:
        write_json(root / "routing.json", routing)
    write_json(root / "intake-receipt.json", {
        "schema_version": 1, "skill_id": skill_id, "status": "published", "approved_by": "user",
        "package_sha256": registry.package_sha256(root),
    })
    return root


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "business-skills"
        self.library.mkdir()
        self.database = self.root / "registry.db"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_lookup_and_material_guidance(self) -> None:
        make_skill(self.library, "sci-fi-city", "科幻城市宣传片", "制作未来感城市形象宣传片", {
            "schema_version": 1, "skill_id": "sci-fi-city", "aliases": ["未来城市片"],
            "user_intents": ["城市宣传片"], "subjects": ["城市"], "styles": ["科幻", "未来感"],
            "narrative_patterns": ["穿梭"], "negative_intents": ["IP巡游"], "priority": 60,
        })
        make_skill(self.library, "ip-parade", "巨型IP巡游", "让巨型角色在城市地标间巡游", {
            "schema_version": 1, "skill_id": "ip-parade", "aliases": ["IP巡游"],
            "user_intents": ["地标巡游"], "subjects": ["IP", "角色"], "styles": ["巨型"],
            "narrative_patterns": ["巡游"], "negative_intents": ["科幻城市宣传片"], "priority": 50,
        })
        result = registry.build(self.library, self.database, rebuild=True)
        self.assertEqual(sorted(result["indexed"]), ["ip-parade", "sci-fi-city"])
        found = registry.lookup(self.database, "我想制作一支科幻未来城市宣传片")
        self.assertEqual(found["candidates"][0]["skill_id"], "sci-fi-city")
        self.assertTrue(found["candidates"][0]["material_guidance"])
        self.assertTrue(any("科幻" in reason for reason in found["candidates"][0]["matched_reasons"]))

    def test_incremental_and_stale_receipt_rejection(self) -> None:
        root = make_skill(self.library, "city", "城市宣传片", "城市形象片")
        first = registry.build(self.library, self.database)
        self.assertEqual(first["indexed"], ["city"])
        second = registry.build(self.library, self.database)
        self.assertEqual(second["unchanged"], ["city"])
        (root / "SKILL.md").write_text("changed", encoding="utf-8")
        stale_db = self.root / "stale.db"
        stale = registry.build(self.library, stale_db)
        self.assertEqual(stale["indexed"], [])
        self.assertIn("stale publication receipt", stale["rejected"][0]["issues"])

    def test_validate_and_list(self) -> None:
        make_skill(self.library, "architecture", "建筑动态组装", "建筑从特写到全貌动态组装")
        registry.build(self.library, self.database)
        self.assertTrue(registry.validate_registry(self.database, self.library)["valid"])
        self.assertEqual(registry.list_skills(self.database)["skills"][0]["skill_id"], "architecture")

    def test_exact_alias(self) -> None:
        make_skill(self.library, "logo", "巨型Logo地标", "品牌Logo城市巡游", {
            "schema_version": 1, "skill_id": "logo", "aliases": ["品牌巨物"], "user_intents": [],
            "subjects": ["Logo"], "styles": ["巨型"], "narrative_patterns": ["巡游"],
            "negative_intents": [], "priority": 50,
        })
        registry.build(self.library, self.database)
        result = registry.lookup(self.database, "品牌巨物")
        self.assertEqual(result["candidates"][0]["skill_id"], "logo")
        self.assertIn("名称或别名精确命中", result["candidates"][0]["matched_reasons"])
        short = registry.lookup(self.database, "IP")
        self.assertEqual(short["candidates"], [])


if __name__ == "__main__":
    unittest.main()
