from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "project-pipeline" / "scripts" / "project_pipeline.py"
REGISTRY_PATH = ROOT / "skill-registry" / "scripts" / "registry.py"
VALIDATOR_PATH = ROOT / "skill-registry" / "scripts" / "validate_package.py"
SKILL_ROOT = ROOT / "business-skills" / "scene-storyboard-grid"
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "image-skill-curator" / "scripts"))
from package_integrity import HASH_ALGORITHM, package_sha256  # noqa: E402
from skill_package import VALIDATOR_VERSION, core_sha256, file_sha256  # noqa: E402
from skill_package import validate_package as validate_governed_package  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


pipeline = load_module("codex_is_pipeline", PIPELINE_PATH)
registry = load_module("codex_is_registry", REGISTRY_PATH)


def publish_copy(destination: Path) -> Path:
    import shutil
    target = destination / "scene-storyboard-grid"
    shutil.copytree(SKILL_ROOT, target)
    report = json.loads((target / "intake-report.json").read_text(encoding="utf-8"))
    report["status"] = "published"
    (target / "intake-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt = {
        "schema_version": 2,
        "hash_algorithm": HASH_ALGORITHM,
        "skill_id": "scene-storyboard-grid",
        "status": "published",
        "validator_version": VALIDATOR_VERSION,
        "approved_by": "user",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [{"name": "test-source.md", "sha256": "0" * 64}],
        "intake_report_sha256": file_sha256(target / "intake-report.json"),
        "reviewed_core_sha256": core_sha256(target),
        "package_sha256": package_sha256(target),
    }
    (target / "intake-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


class CodexIsTests(unittest.TestCase):
    def test_package_validator_and_contract(self):
        result = subprocess.run([sys.executable, str(VALIDATOR_PATH), str(SKILL_ROOT)], text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        contract = json.loads((SKILL_ROOT / "contract.json").read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in contract["references"]], ["scene-base", "identity-design"])
        constraints = contract["business_constraints"]
        self.assertEqual(constraints["panel_count"], 9)
        self.assertEqual(constraints["panel_orientation_source"], "scene-base")
        self.assertTrue(constraints["uniform_panel_orientation"])
        self.assertTrue(constraints["outer_ratio_independent_from_panel_orientation"])
        self.assertTrue(constraints["requires_per_scene_fact_ledger"])
        self.assertEqual(constraints["shot_selection_strategy"], "evidence_conditioned")

    def test_registry_only_indexes_published_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "skills"
            skills.mkdir()
            db = root / "registry.sqlite3"
            publish_copy(skills)
            built = registry.build(skills, db)
            self.assertEqual(built["indexed"], 1)
            found = registry.lookup("九宫格分镜", db, 3)
            self.assertEqual(found["candidates"][0]["skill_id"], "scene-storyboard-grid")

    def test_single_reference_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills, projects = root / "skills", root / "projects"
            skills.mkdir()
            publish_copy(skills)
            created = pipeline.create(projects, skills, "single", "scene-storyboard-grid", "场景一致性九宫格分镜", "16:9", 1, 1, True)
            scene = Path(created["material_directories"][0]["source_dir"]) / "scene.png"
            scene.write_bytes(b"fake-image")
            pipeline.lock_materials(projects, "single", True)
            prompt = "OUTPUT CONTRACT\nREFERENCE ROLES\nIDENTITY AND CONTINUITY\nSHOT COVERAGE\nALLOWED VARIATION\nPHYSICAL RELATIONSHIPS\nCLOSED-WORLD RULE\nOUTPUT NEGATIVES"
            pipeline.set_prompt(projects, "single", prompt, "business_skill")
            pipeline.confirm_prompt(projects, "single")
            result = pipeline.start_generation(projects, "single", True)
            self.assertEqual(result["generation"]["manifest"]["entry"], "generate_image")
            self.assertEqual(len(result["generation"]["manifest"]["reference_images_by_scene"]), 1)

    def test_batch_requires_paid_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills, projects = root / "skills", root / "projects"
            skills.mkdir()
            publish_copy(skills)
            created = pipeline.create(projects, skills, "batch", "scene-storyboard-grid", "场景一致性九宫格分镜", "3:2", 2, 1, True)
            Path(created["material_directories"][0]["source_dir"], "scene.png").write_bytes(b"image")
            pipeline.lock_materials(projects, "batch", True)
            pipeline.set_prompt(projects, "batch", "confirmed prompt", "business_skill")
            confirmed = pipeline.confirm_prompt(projects, "batch")
            self.assertEqual(confirmed["state"], "awaiting_paid_batch_confirmation")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.start_generation(projects, "batch", True)
            pipeline.confirm_paid_batch(projects, "batch")
            result = pipeline.start_generation(projects, "batch", True)
            self.assertEqual(result["generation"]["manifest"]["entry"], "batch-image-generation")

    def test_material_change_invalidates_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills, projects = root / "skills", root / "projects"
            skills.mkdir()
            publish_copy(skills)
            created = pipeline.create(projects, skills, "change", "scene-storyboard-grid", "场景一致性九宫格分镜", "1:1", 1, 1, True)
            source = Path(created["material_directories"][0]["source_dir"], "scene.png")
            source.write_bytes(b"one")
            pipeline.lock_materials(projects, "change", True)
            pipeline.set_prompt(projects, "change", "first prompt", "business_skill")
            source.write_bytes(b"two")
            final = Path(created["material_directories"][0]["final_dir"], "scene.png")
            final.write_bytes(b"two")
            pipeline.lock_materials(projects, "change", False)
            _, project = pipeline.load(projects, "change")
            self.assertEqual(project["prompts"], [])
            self.assertIsNone(project["confirmation"])

    def test_missing_scene_and_third_image_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills, projects = root / "skills", root / "projects"
            skills.mkdir()
            publish_copy(skills)
            created = pipeline.create(projects, skills, "invalid", "scene-storyboard-grid", "场景一致性九宫格分镜", "9:16", 1, 1, True)
            identity = Path(created["material_directories"][1]["source_dir"])
            (identity / "a.png").write_bytes(b"a")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.lock_materials(projects, "invalid", True)

    def test_scene_scoped_materials_are_replicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); skills, projects = root / "skills", root / "projects"; skills.mkdir(); publish_copy(skills)
            created = pipeline.create(projects, skills, "two-scenes", "scene-storyboard-grid", "场景一致性九宫格分镜", "16:9", 1, 2, True)
            scenes = [item for item in created["material_directories"] if item["id"] == "scene-base"]
            self.assertEqual([item["scene_index"] for item in scenes], [1, 2])
            Path(scenes[0]["source_dir"], "a.png").write_bytes(b"a")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.lock_materials(projects, "two-scenes", True)

    def test_observation_only_reference_is_not_sent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); skills, projects = root / "skills", root / "projects"; skills.mkdir(); published = publish_copy(skills)
            contract_path = published / "contract.json"; contract = json.loads(contract_path.read_text(encoding="utf-8")); contract["references"][1]["send_to_generation"] = False; contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            report = json.loads((published / "intake-report.json").read_text(encoding="utf-8")); report["reviewed_core_sha256"] = core_sha256(published); (published / "intake-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            receipt = json.loads((published / "intake-receipt.json").read_text(encoding="utf-8")); receipt["reviewed_core_sha256"] = core_sha256(published); receipt["intake_report_sha256"] = file_sha256(published / "intake-report.json"); receipt["package_sha256"] = package_sha256(published); (published / "intake-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            created = pipeline.create(projects, skills, "observe", "scene-storyboard-grid", "场景一致性九宫格分镜", "1:1", 1, 1, True)
            for item in created["material_directories"]: Path(item["source_dir"], item["id"] + ".png").write_bytes(item["id"].encode())
            pipeline.lock_materials(projects, "observe", True); pipeline.set_prompt(projects, "observe", "prompt", "business_skill"); pipeline.confirm_prompt(projects, "observe")
            manifest = pipeline.start_generation(projects, "observe", True)["generation"]["manifest"]
            self.assertEqual(len(manifest["reference_images_by_scene"][0]["reference_images"]), 1)

    def test_generic_text_only_skill_is_not_forced_into_storyboard_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "text-poster"; (root / "references").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: text-poster\ndescription: Create a text-only poster prompt for a confirmed visual brief.\n---\n\nRead the contract, author V1, and wait for confirmation.\n", encoding="utf-8")
            contract = {"schema_version":1,"skill_id":"text-poster","display_name":"纯文本海报提示词","description":"根据纯文本需求编写单张海报图片提示词。","input_mode":"text_only","references":[],"reference_policy":{"allowed_slot_ids":[],"reject_uncontracted_images":True,"maximum_reference_images_per_scene":0,"preserve_reference_order":True},"workload":{"scene_count":{"min":1,"max":1},"candidate_count_per_scene":{"min":1,"max":1},"batch_allowed":False},"output":{"media_type":"image","requires_ratio_confirmation":True,"supported_ratios":["1:1"]},"authoring":{"primary_language":"zh","requires_reference_binding":False,"requires_prompt_confirmation":True,"user_instruction_priority":"highest"},"execution":{"provider_neutral":True,"single_candidate_entry":"generate_image","batch_entry":"batch-image-generation","requires_paid_batch_confirmation":True,"automatic_retry":False,"automatic_visual_ranking":False},"knowledge":{"creative_guidance":"references/creative-guidance.md","failure_cases":"references/failure-cases.md","examples":"references/examples.md"},"business_constraints":{}}
            (root / "contract.json").write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
            routing={"schema_version":1,"skill_id":"text-poster","aliases":["文字海报"],"user_intents":["根据文字制作海报提示词"],"subjects":[],"styles":[],"narrative_patterns":[],"negative_intents":["九宫格分镜"],"priority":40}
            (root / "routing.json").write_text(json.dumps(routing, ensure_ascii=False), encoding="utf-8")
            (root / "references" / "creative-guidance.md").write_text("# Guidance\nUse the confirmed brief.\n", encoding="utf-8")
            (root / "references" / "failure-cases.md").write_text("# Failures\nSymptom, cause, fix, stop.\n", encoding="utf-8")
            (root / "references" / "examples.md").write_text("# Examples\nExamples do not define the contract.\n", encoding="utf-8")
            self.assertEqual(validate_governed_package(root), [])

    def test_scaffold_markers_block_publication_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "image-skill-curator" / "scripts" / "scaffold_business_skill.py"), "draft-skill", "--output", directory, "--display-name", "草稿图片 Skill"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            issues = validate_governed_package(Path(directory) / "draft-skill")
            self.assertIn("UNRESOLVED_TEMPLATE_MARKER", issues)


if __name__ == "__main__":
    unittest.main()
