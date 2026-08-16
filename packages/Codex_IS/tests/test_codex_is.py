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
from package_integrity import HASH_ALGORITHM, package_sha256  # noqa: E402


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
    receipt = {
        "schema_version": 1,
        "hash_algorithm": HASH_ALGORITHM,
        "skill_id": "scene-storyboard-grid",
        "status": "published",
        "approved_by": "user",
        "validated_at": datetime.now(timezone.utc).isoformat(),
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
        self.assertEqual(contract["output"]["panel_count"], 9)

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
            scene = Path(created["material_directories"][0]["source_dir"])
            (scene / "a.png").write_bytes(b"a")
            (scene / "b.png").write_bytes(b"b")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.lock_materials(projects, "invalid", True)


if __name__ == "__main__":
    unittest.main()

