from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_pipeline.py"
SPEC = importlib.util.spec_from_file_location("project_pipeline", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(pipeline)


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
                {"id": "scenes", "media_type": "image", "role": "scene", "required": True, "min_count": 1, "max_count": None, "ordered": True},
            ],
        }, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(self) -> dict:
        return pipeline.create_project(self.projects, self.skills, "demo", "test-skill", "测试 Skill", "9:16", 15, True)

    def put_sources(self) -> None:
        project = json.loads((self.projects / "demo" / "project.json").read_text(encoding="utf-8"))
        for index, slot in enumerate(project["material_slots"]):
            Path(slot["source_dir"], f"{index + 1:02}.png").write_bytes(f"image-{index}".encode())

    def test_create_requires_confirmation_and_creates_slot_directories(self) -> None:
        with self.assertRaises(pipeline.PipelineError):
            pipeline.create_project(self.projects, self.skills, "bad", "test-skill", "测试 Skill", "9:16", 15, False)
        result = self.create()
        self.assertEqual(result["state"], "awaiting_image_stage_choice")
        self.assertEqual(len(result["material_directories"]), 2)
        for slot in result["material_directories"]:
            self.assertTrue(Path(slot["source_dir"]).is_dir())
            self.assertTrue(Path(slot["final_dir"]).is_dir())
        for duration in (3, 31):
            with self.assertRaisesRegex(pipeline.PipelineError, "between 4 and 30"):
                pipeline.create_project(self.projects, self.skills, f"bad-{duration}", "test-skill", "测试 Skill", "9:16", duration, True)

    def test_happy_path_with_cs_prompt(self) -> None:
        self.create()
        pipeline.choose_image_stage(self.projects, "demo", "user_supplied")
        self.put_sources()
        locked = pipeline.lock_final(self.projects, "demo", True)
        self.assertEqual([item["slot_id"] for item in locked["final_images"]], ["identity", "scenes"])
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
        self.assertEqual(len(payload["ordered_media"]["images"]), 2)
        completed = pipeline.complete_project(self.projects, "demo", "external-task-1")
        self.assertEqual(completed["state"], "completed")

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
