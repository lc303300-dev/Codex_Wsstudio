from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
sys.path.insert(0, str(PLATFORM))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_package = load_module("codex_flow_skill_package", PLATFORM / "skill_package.py")
registry = load_module("codex_flow_registry", PLATFORM / "registry.py")
approval = load_module("codex_flow_approval", PLATFORM / "approval.py")
project = load_module("codex_flow_project", PLATFORM / "project.py")
cutover_check = load_module("codex_flow_cutover_check", PLATFORM / "cutover_check.py")


def write_minimum_skill(root: Path, *, name: str = "simple-poster", profile: str = "simple") -> Path:
    package = root / name
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Create a concise poster prompt from a confirmed brief.\n"
        "---\n\n"
        "# Simple Poster\n\n"
        "Use the confirmed brief and produce one business prompt.\n",
        encoding="utf-8",
    )
    (package / "meta.yaml").write_text(
        "schema: codex-flow-skill/v1\n"
        f"name: {name}\n"
        "version: 1.0.0\n"
        "primary-output: image\n"
        f"workflow-profile: {profile}\n"
        "interaction-profile: conversation\n"
        "tags:\n"
        "  - poster\n"
        "aliases:\n"
        "  - poster prompt\n"
        "capabilities:\n"
        "  - image.generate\n",
        encoding="utf-8",
    )
    return package


class CodexFlowTests(unittest.TestCase):
    def test_minimum_simple_skill_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory))
            self.assertEqual(skill_package.validate_package(package), [])

    def test_staged_skill_requires_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory), name="staged-film", profile="staged")
            issues = skill_package.validate_package(package)
            self.assertIn("MISSING_WORKFLOW_YAML", issues)

    def test_provider_model_dag_and_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory))
            with (package / "SKILL.md").open("a", encoding="utf-8") as handle:
                handle.write("\nUse Seedance 2.5 with DAG ID abc and Authorization Bearer secret.\n")
            issues = skill_package.validate_package(package)
            self.assertIn("PROVIDER_POLLUTION", issues)
            self.assertIn("MODEL_POLLUTION", issues)
            self.assertIn("DAG_POLLUTION", issues)
            self.assertIn("CREDENTIAL_POLLUTION", issues)

    def test_references_are_checked_and_routed(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory), name="reference-skill")
            references = package / "references"
            references.mkdir()
            (references / "storyboard.md").write_text("# Storyboard\n", encoding="utf-8")
            with (package / "meta.yaml").open("a", encoding="utf-8") as handle:
                handle.write(
                    "references:\n"
                    "  storyboard:\n"
                    "    path: references/storyboard.md\n"
                    "    load-at:\n"
                    "      - storyboard\n"
                )
            self.assertEqual(skill_package.validate_package(package), [])
            routes = registry.reference_routes(skill_package.parse_yaml_text(package / "meta.yaml"))
            self.assertEqual(routes["storyboard"]["load_at"], ["storyboard"])

    def test_unreferenced_and_duplicate_resources_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory), name="bad-resources")
            references = package / "references"
            references.mkdir()
            (references / "one.md").write_text("same", encoding="utf-8")
            (references / "two.md").write_text("same", encoding="utf-8")
            issues = skill_package.validate_package(package)
            self.assertIn("UNREFERENCED_RESOURCE:references/one.md", issues)
            self.assertIn("UNREFERENCED_RESOURCE:references/two.md", issues)
            self.assertIn("DUPLICATE_RESOURCE:references/one.md:references/two.md", issues)

    def test_workflow_unknown_dependency_and_cycle_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = write_minimum_skill(Path(directory), name="loop-skill", profile="staged")
            (package / "workflow.yaml").write_text(
                "schema: codex-flow-workflow/v1\n"
                "profile: staged\n"
                "stages:\n"
                "  - id: one\n"
                "    depends-on:\n"
                "      - two\n"
                "    gate: approval\n"
                "  - id: two\n"
                "    depends-on:\n"
                "      - one\n"
                "    gate: paid-execution\n"
                "  - id: three\n"
                "    depends-on:\n"
                "      - missing\n",
                encoding="utf-8",
            )
            issues = skill_package.validate_package(package)
            self.assertIn("WORKFLOW_CYCLE", issues)
            self.assertIn("UNKNOWN_DEPENDENCY:three:missing", issues)

    def test_registry_compiles_only_valid_lightweight_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skills = root / "skills"
            skills.mkdir()
            write_minimum_skill(skills, name="simple-poster")
            invalid = write_minimum_skill(skills, name="staged-film", profile="staged")
            output = root / "registry.json"
            result = registry.build(skills, output)
            self.assertEqual(result["indexed"], 1)
            self.assertEqual(result["rejected"][0]["skill_id"], invalid.name)
            compiled = json.loads(output.read_text(encoding="utf-8"))
            skill = compiled["skills"][0]
            self.assertEqual(skill["skill_id"], "simple-poster")
            self.assertEqual(skill["capabilities"], ["image.generate"])
            self.assertNotIn("body", skill)
            lookup = registry.lookup("poster", output, 3)
            self.assertEqual(lookup["candidates"][0]["skill_id"], "simple-poster")

    def test_approval_invalidates_when_package_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = write_minimum_skill(root)
            review = approval.create_review(package, root / "reviews", "a" * 64)
            approval_record = approval.approve_review(review, root / "approvals")
            approval_path = root / "approvals" / f"{approval_record['approval_id']}.json"
            with (package / "SKILL.md").open("a", encoding="utf-8") as handle:
                handle.write("\nAdditional business rule.\n")
            with self.assertRaises(ValueError):
                approval.consume_approval(approval_path, package, review)

    def test_publish_consumes_approval_once_and_builds_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = write_minimum_skill(root / "drafts")
            review = approval.create_review(package, root / "reviews", "b" * 64)
            approval_record = approval.approve_review(review, root / "approvals")
            approval_path = root / "approvals" / f"{approval_record['approval_id']}.json"
            review_path = root / "reviews" / f"{review['review_id']}.json"
            release = approval.publish(package, root / "business-skills", root / "registry.json", root / "releases", review_path, approval_path)
            self.assertEqual(release["skill_id"], "simple-poster")
            self.assertTrue(json.loads(approval_path.read_text(encoding="utf-8"))["consumed"])
            compiled = json.loads((root / "registry.json").read_text(encoding="utf-8"))
            self.assertEqual(compiled["indexed"], 1)
            with self.assertRaises(ValueError):
                approval.consume_approval(approval_path, root / "business-skills" / "simple-poster", review)

    def test_project_invalidation_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = project.create_project(root, {"id": "simple-poster", "version": "1.0.0"}, {"image_ratio": "16:9"}, "flow_test")
            brief_v1 = project.upsert_artifact(manifest, "brief", "brief", {"text": "one"})
            storyboard_v1 = project.upsert_artifact(manifest, "storyboard", "storyboard", {"panels": 9}, [f"brief:v{brief_v1['version']}"])
            project.approve_artifact(manifest, "brief", 1)
            project.approve_artifact(manifest, "storyboard", 1)
            project.record_execution(manifest, "motion", "p1", ["storyboard:v1"], {"duration": 5}, 1)
            with self.assertRaises(ValueError):
                project.record_execution(manifest, "motion", "p1", ["storyboard:v1"], {"duration": 5}, 1)
            project.upsert_artifact(manifest, "brief", "brief", {"text": "two"})
            self.assertEqual(storyboard_v1["status"], "invalidated")
            active = [item for item in manifest["approvals"] if item["status"] == "active"]
            self.assertEqual(active, [])

    def test_migrated_flow_library_is_independently_indexable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "registry.json"
            skills_root = ROOT / "business-skills"
            discovered, rejected = registry.discover(skills_root)
            self.assertEqual(rejected, [])
            self.assertEqual({item["skill_id"] for item in discovered}, {
                "architectural-assembly-reveal",
                "city-real-estate-habitat-promo",
                "dawn-mist-aerial-real-estate",
                "giant-ip-landmark-parade",
                "sci-fi-city-promo",
                "scene-storyboard-grid",
            })
            compiled = registry.build(skills_root, output)
            self.assertEqual(compiled["indexed"], 6)

    def test_cutover_check_blocks_unresolved_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.json"
            report.write_text(
                json.dumps({"blocked": [{"skill_id": "blocked-skill", "reason": "not approved"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            result = cutover_check.check(report, root)
            self.assertFalse(result["ready"])
            self.assertEqual(result["issues"][0]["code"], "BLOCKED_SKILL")


if __name__ == "__main__":
    unittest.main()
