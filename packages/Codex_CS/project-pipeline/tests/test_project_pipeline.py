from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_pipeline.py"
SPEC = importlib.util.spec_from_file_location("project_pipeline", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(pipeline)

INTEGRITY_ROOT = Path(__file__).resolve().parents[2] / "codex-cs-skill-curator" / "scripts"
sys.path.insert(0, str(INTEGRITY_ROOT))
from package_integrity import CANONICAL_HASH_ALGORITHM, package_sha256  # noqa: E402


class ProjectPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.skills = self.root / "skills"
        self.projects = self.root / "projects"
        skill = self.skills / "test-skill"
        skill.mkdir(parents=True)
        (skill / "contract.json").write_text(json.dumps({
            "skill_id": "test-skill",
            "display_name": "测试 Skill",
            "references": [
                {"id": "identity", "media_type": "image", "role": "identity", "required": True, "min_count": 1, "max_count": 1, "ordered": True},
                {"id": "scenes", "media_type": "image", "role": "scene", "required": True, "min_count": 1, "max_count": 10, "ordered": True},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        contract_path = skill / "contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["references"][0]["count_rule"] = {
            "type": "fixed", "enforcement": "required", "fixed_count": 1,
            "seconds_per_item": None, "rounding": None, "duration_share": 1,
            "duration_to_count": [], "provenance": "source_explicit", "confidence": "high", "rationale": "身份图固定一张"
        }
        contract["references"][1]["count_rule"] = {
            "type": "duration_formula", "enforcement": "required", "fixed_count": None,
            "seconds_per_item": 5, "rounding": "ceil", "duration_share": 1,
            "duration_to_count": [], "provenance": "source_explicit", "confidence": "high", "rationale": "每五秒一张场景图"
        }
        contract_path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        (skill / "SKILL.md").write_text("---\nname: test-skill\ndescription: 测试已发布视频业务 Skill\n---\n\n# 测试\n", encoding="utf-8")
        receipt = {
            "schema_version": 2,
            "hash_algorithm": CANONICAL_HASH_ALGORITHM,
            "skill_id": "test-skill",
            "status": "published",
            "validator_version": "1.2.0",
            "approved_by": "user",
            "validated_at": "2026-08-16T00:00:00+00:00",
            "sources": [{"name": "source.md", "sha256": "0" * 64}],
            "package_sha256": package_sha256(skill),
        }
        (skill / "intake-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        self.skill = skill

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(self) -> dict:
        return pipeline.create_project(self.projects, self.skills, "demo", "test-skill", "测试 Skill", "9:16", 15, True)

    def put_sources(self) -> None:
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        for index, slot in enumerate(project["material_slots"]):
            for item in range(slot["planned_count"]):
                Path(slot["source_dir"], f"{item + 1:02}.png").write_bytes(f"image-{index}-{item}".encode())

    def put_named_sources(self) -> None:
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        names = {
            "identity": ["Logo_设定图.png"],
            "scenes": ["Tu_001.png", "Tu_002.png", "Tu_003.png"],
        }
        for slot in project["material_slots"]:
            for name in names[slot["id"]]:
                Path(slot["source_dir"], name).write_bytes(name.encode())

    def test_create_requires_confirmation_and_creates_slot_directories(self) -> None:
        with self.assertRaises(pipeline.PipelineError):
            pipeline.create_project(self.projects, self.skills, "bad", "test-skill", "测试 Skill", "9:16", 15, False)
        result = self.create()
        self.assertEqual(result["state"], "awaiting_image_stage_choice")
        self.assertEqual(len(result["material_directories"]), 2)
        for slot in result["material_directories"]:
            self.assertTrue(Path(slot["source_dir"]).is_dir())
            self.assertTrue(Path(slot["final_dir"]).is_dir())
            self.assertEqual(slot["source_dir_link_target"], Path(slot["source_dir"]).resolve().as_posix())
            self.assertEqual(slot["final_dir_link_target"], Path(slot["final_dir"]).resolve().as_posix())
            self.assertNotIn("\\", slot["source_dir_link_target"])
            self.assertNotIn("\\", slot["final_dir_link_target"])
        self.assertEqual(result["project_dir_link_target"], Path(result["project_dir"]).resolve().as_posix())
        self.assertEqual(result["project_file_link_target"], Path(result["project_file"]).resolve().as_posix())
        for duration in (3, 31):
            with self.assertRaisesRegex(pipeline.PipelineError, "between 4 and 30"):
                pipeline.create_project(self.projects, self.skills, f"bad-{duration}", "test-skill", "测试 Skill", "9:16", duration, True)

    def test_create_rejects_missing_or_stale_receipt(self) -> None:
        receipt = self.skill / "intake-receipt.json"
        receipt.unlink()
        with self.assertRaisesRegex(pipeline.PipelineError, "MISSING_RECEIPT"):
            pipeline.create_project(self.projects, self.skills, "missing", "test-skill", "测试 Skill", "9:16", 15, True)
        self.assertFalse((self.projects / "missing").exists())

        self.setUp_receipt()
        with (self.skill / "contract.json").open("a", encoding="utf-8") as stream:
            stream.write(" ")
        with self.assertRaisesRegex(pipeline.PipelineError, "STALE_RECEIPT"):
            pipeline.create_project(self.projects, self.skills, "stale", "test-skill", "测试 Skill", "9:16", 15, True)
        self.assertFalse((self.projects / "stale").exists())

    def setUp_receipt(self) -> None:
        receipt = {
            "schema_version": 2, "hash_algorithm": CANONICAL_HASH_ALGORITHM,
            "skill_id": "test-skill", "status": "published", "validator_version": "1.2.0",
            "approved_by": "user", "validated_at": "2026-08-16T00:00:00+00:00",
            "sources": [{"name": "source.md", "sha256": "0" * 64}],
            "package_sha256": package_sha256(self.skill),
        }
        (self.skill / "intake-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

    def test_create_accepts_line_ending_only_change(self) -> None:
        skill_file = self.skill / "SKILL.md"
        normalized = skill_file.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        skill_file.write_bytes(normalized.replace(b"\n", b"\r\n"))
        result = pipeline.create_project(self.projects, self.skills, "line-endings", "test-skill", "测试 Skill", "9:16", 15, True)
        self.assertEqual(result["state"], "awaiting_image_stage_choice")

    def test_happy_path_with_cs_prompt(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        locked = pipeline.lock_final(self.projects, "demo", True)
        self.assertEqual([item["slot_id"] for item in locked["final_images"]], ["identity", "scenes", "scenes", "scenes"])
        prompt = pipeline.set_cs_prompt(self.projects, "demo", "V1 提示词")
        self.assertEqual(prompt["active_prompt_version"], 1)
        pipeline.confirm_prompt(self.projects, "demo")
        started = pipeline.start_generation(self.projects, "demo")
        self.assertEqual(started["state"], "generating_video")
        payload = started["generation"]["submission_payload"]
        self.assertEqual(payload["tool"], "generate_video")
        self.assertEqual(payload["prompt"], "V1 提示词")
        self.assertEqual(payload["video_ratio"], "9:16")
        self.assertEqual(payload["video_duration"], 15)
        self.assertEqual(len(payload["ordered_media"]["images"]), 4)
        completed = pipeline.complete_project(self.projects, "demo", "external-task-1")
        self.assertEqual(completed["state"], "completed")

    def test_prompt_rejects_internal_material_filename_leaks(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_named_sources()
        pipeline.lock_final(self.projects, "demo", True)
        with self.assertRaisesRegex(pipeline.PipelineError, "internal material filename"):
            pipeline.set_cs_prompt(self.projects, "demo", "图片2是 Tu_001：第一段场景参考。")

    def test_prompt_rejects_pipe_storyboard_heading(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        pipeline.lock_final(self.projects, "demo", True)
        bad = "0.0-4.0 秒｜第一段｜图片2\n完全依据图片2建立空间。"
        with self.assertRaisesRegex(pipeline.PipelineError, "invalid storyboard heading"):
            pipeline.set_cs_prompt(self.projects, "demo", bad)
        good = pipeline.set_cs_prompt(self.projects, "demo", "0.0-4.0 秒，第一段，参考图片2。依据图片2建立空间。")
        self.assertEqual(good["active_prompt_version"], 1)

    def test_revision_is_dt_owned(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        pipeline.lock_final(self.projects, "demo", True)
        pipeline.set_cs_prompt(self.projects, "demo", "V1")
        with self.assertRaises(pipeline.PipelineError):
            pipeline.set_cs_prompt(self.projects, "demo", "非法 V2")
        pipeline.request_revision(self.projects, "demo", "运镜更快")
        result = pipeline.set_dt_revision(self.projects, "demo", "DT V2")
        project = json.loads(Path(result["project_file"]).read_text(encoding="utf-8"))
        self.assertEqual(project["prompts"][-1]["author"], "dt")
        self.assertEqual(project["prompts"][-1]["feedback"], "运镜更快")

    def test_changed_material_blocks_confirmed_submission(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        pipeline.lock_final(self.projects, "demo", True)
        pipeline.set_cs_prompt(self.projects, "demo", "V1")
        pipeline.confirm_prompt(self.projects, "demo")
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        Path(project["material_slots"][0]["final_dir"], "01.png").write_bytes(b"changed")
        with self.assertRaisesRegex(pipeline.PipelineError, "changed after confirmation"):
            pipeline.start_generation(self.projects, "demo")

    def test_stale_skill_blocks_generation(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        pipeline.lock_final(self.projects, "demo", True)
        pipeline.set_cs_prompt(self.projects, "demo", "V1")
        pipeline.confirm_prompt(self.projects, "demo")
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("\ntampered\n")
        with self.assertRaisesRegex(pipeline.PipelineError, "STALE_RECEIPT"):
            pipeline.start_generation(self.projects, "demo")

    def test_slot_count_is_enforced(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "generate")
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        identity = Path(project["material_slots"][0]["final_dir"])
        identity.joinpath("a.png").write_bytes(b"a")
        identity.joinpath("b.png").write_bytes(b"b")
        Path(project["material_slots"][1]["final_dir"], "scene.png").write_bytes(b"scene")
        with self.assertRaisesRegex(pipeline.PipelineError, "at most 1"):
            pipeline.lock_final(self.projects, "demo", False)

    def test_duration_plans_required_material_count(self) -> None:
        result = pipeline.create_project(self.projects, self.skills, "short", "test-skill", "测试 Skill", "9:16", 11, True)
        counts = {item["slot_id"]: item["planned_count"] for item in result["material_directories"]}
        self.assertEqual({"identity": 1, "scenes": 3}, counts)
        pipeline.choose_image_stage(self.projects, "short", "user_supplied")
        project = json.loads((self.projects / "short" / "project.json").read_text(encoding="utf-8"))
        Path(project["material_slots"][0]["source_dir"], "identity.png").write_bytes(b"identity")
        Path(project["material_slots"][1]["source_dir"], "scene.png").write_bytes(b"scene")
        with self.assertRaisesRegex(pipeline.PipelineError, "requires exactly 3"):
            pipeline.lock_final(self.projects, "short", True)

    def test_generate_mode_rejects_source_as_final(self) -> None:
        self.create()
        result = pipeline.choose_image_stage(self.projects, "demo", "generate")
        self.assertIn("image_generation_tasks", result)
        self.put_sources()
        with self.assertRaisesRegex(pipeline.PipelineError, "user_supplied"):
            pipeline.lock_final(self.projects, "demo", True)

    def test_material_change_archives_stale_draft_and_restarts_v1(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        pipeline.lock_final(self.projects, "demo", True)
        pipeline.set_cs_prompt(self.projects, "demo", "过期草稿")
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        Path(project["material_slots"][0]["final_dir"], "01.png").write_bytes(b"changed")
        pipeline.lock_final(self.projects, "demo", False)
        restarted = pipeline.set_cs_prompt(self.projects, "demo", "新素材 V1")
        self.assertEqual(restarted["active_prompt_version"], 1)
        stored = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["archived_prompts"][0]["status"], "superseded_by_material_change")


if __name__ == "__main__":
    unittest.main()
