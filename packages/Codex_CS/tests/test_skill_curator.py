from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURATOR = ROOT / "codex-cs-skill-curator"
SCRIPTS = CURATOR / "scripts"
sys.path.insert(0, str(SCRIPTS))

from discover_published_skills import discover  # noqa: E402
from inspect_skill_source import inspect  # noqa: E402
from migrate_legacy_skills import migrate, SPECS, strip_wrappers  # noqa: E402
from prepare_dt_supplement import build_request  # noqa: E402
from skill_package import package_sha256, validate_package  # noqa: E402


def finalize_template(package: Path) -> None:
    contract_path = package / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["references"][0]["description"] = "作为主要场景与构图参考，创作前必须完成视觉观察"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replacements = {
        "<!-- CURATOR-REQUIRED: 用一段话说明该 Skill 独有的业务目标，不重复 description。 -->": "根据场景参考设计连续、明确且可执行的视频提示词。",
        "<!-- CURATOR-REQUIRED: 保存该业务 Skill 独有的视觉、镜头、动作、光色、材质、声音、节奏和连续性方法。区分强制规则与建议规则。 -->": "本文件记录来源中确认的专业创作方法。",
        "<!-- CURATOR-REQUIRED: 完整保留有价值的社区经验。每条注明结论、适用条件、不适用条件、证据等级和来源背景。没有社区资料时明确写“原始资料未提供社区经验”。 -->": "原始资料未提供社区经验。",
        "<!-- CURATOR-REQUIRED: 按“表现 / 可能原因 / 规避或修复 / 适用条件”整理。不得只列负面词。 -->": "原始资料未提供独立失败案例。",
        "<!-- CURATOR-REQUIRED: 分离正例、反例和边界案例。示例仅帮助理解，不得定义素材契约或覆盖用户指令。没有示例时明确说明。 -->": "原始资料未提供示例。",
    }
    for path in package.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


class SkillCuratorTests(unittest.TestCase):
    def scaffold(self, root: Path) -> Path:
        command = [
            sys.executable,
            str(SCRIPTS / "scaffold_business_skill.py"),
            "--skill-id", "sample-video-skill",
            "--display-name", "样本视频业务 Skill",
            "--description", "根据用户提供的场景参考素材编写专业、连续且可执行的视频生成提示词。",
            "--short-description", "根据已确认参考素材与专业业务规则编写连续且可执行的视频生成提示词",
            "--output", str(root),
        ]
        completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        return root / "sample-video-skill"

    def test_unfinished_template_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            codes = {issue.code for issue in validate_package(package)}
            self.assertIn("UNRESOLVED_PLACEHOLDER", codes)

    def test_finished_reference_based_package_is_valid(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            self.assertEqual([], validate_package(package))

    def test_text2video_and_zero_reference_contract_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            contract_path = package / "contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["references"] = []
            contract["video"]["allowed_modes"] = ["text2video"]
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            codes = {issue.code for issue in validate_package(package)}
            self.assertIn("MISSING_REFERENCES", codes)
            self.assertIn("INVALID_VIDEO_MODE", codes)
            self.assertIn("TEXT2VIDEO_FORBIDDEN", codes)

    def test_publish_creates_receipt_and_tamper_invalidates_it(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = self.scaffold(root / "staging")
            finalize_template(package)
            source = root / "uploaded.md"
            source.write_text("# original source\n", encoding="utf-8")
            library = root / "library"
            command = [
                sys.executable,
                str(SCRIPTS / "publish_skill.py"),
                str(package),
                "--library-root", str(library),
                "--source", str(source),
                "--approved-by", "user",
            ]
            completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            published = library / package.name
            self.assertEqual([], validate_package(published, require_receipt=True))
            receipt = json.loads((published / "intake-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["package_sha256"], package_sha256(published))
            with (published / "references" / "examples.md").open("a", encoding="utf-8") as stream:
                stream.write("\nchanged after publish\n")
            codes = {issue.code for issue in validate_package(published, require_receipt=True)}
            self.assertIn("STALE_RECEIPT", codes)

    def test_registry_ignores_direct_drop_and_accepts_only_published_package(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            library = root / "library"
            library.mkdir()
            direct = self.scaffold(library)
            finalize_template(direct)
            published, rejected = discover(library)
            self.assertEqual([], published)
            self.assertEqual(1, len(rejected))
            shutil.rmtree(direct)

            staging = self.scaffold(root / "staging")
            finalize_template(staging)
            source = root / "source.md"
            source.write_text("# source\n", encoding="utf-8")
            completed = subprocess.run([
                sys.executable,
                str(SCRIPTS / "publish_skill.py"),
                str(staging),
                "--library-root", str(library),
                "--source", str(source),
                "--approved-by", "user",
            ], text=True, capture_output=True, encoding="utf-8", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            published, rejected = discover(library)
            self.assertEqual(["sample-video-skill"], [item["skill_id"] for item in published])
            self.assertEqual([], rejected)

    def test_audio_reference_is_valid_without_images(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            contract_path = package / "contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["references"] = [{
                "id": "music-reference",
                "media_type": "audio",
                "role": "music",
                "description": "作为节奏、情绪和声音结构参考的音乐素材",
                "required": True,
                "min_count": 1,
                "max_count": 1,
                "ordered": True,
                "observation_required": False,
            }]
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual([], validate_package(package))

    def test_source_preflight_detects_legacy_wrapper_without_guessing_contract(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "legacy.md"
            source.write_text(
                "--- START OF FILE SKILL.md ---\n## name\n旧视频 Skill\n## description\n"
                "使用图片1和音乐1创作视频。历史命令：seedance-cli --model_version old。\n",
                encoding="utf-8",
            )
            report = inspect(source)
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("EXPORT_WRAPPER", codes)
            self.assertIn("EXECUTION_COUPLING", codes)
            self.assertIn("NONSTANDARD_METADATA", codes)
            self.assertGreater(report["content_summary"]["media_hints"]["image"], 0)
            self.assertEqual("needs_review", report["next_state"])
            self.assertNotIn("contract", report)

    def test_dt_supplement_request_is_pending_for_missing_examples(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            payload = build_request(package)
            self.assertEqual("creative_supplement_pending", payload["status"])
            self.assertEqual("supplement_skill_creative_examples", payload["operation"])
            self.assertEqual("sample-video-skill", payload["source_skill_id"])
            self.assertIn("examples_missing", payload["detected_reasons"])
            constraints = payload["constraints"]
            self.assertTrue(constraints["preserve_meaning"])
            self.assertTrue(constraints["do_not_infer_contract"])
            self.assertTrue(constraints["do_not_submit_video"])
            self.assertEqual("zh-CN", constraints["language"])

    def test_dt_supplement_not_required_when_creative_examples_exist(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            (package / "references" / "examples.md").write_text(
                "# 示例\n\n## 正例\n\n包含主体、动作和镜头。\n\n## 反例\n\n缺少素材绑定。\n\n## 边界案例\n\n用户提供完整提示词时仅规范格式。\n",
                encoding="utf-8",
            )
            (package / "references" / "creative-guidance.md").write_text(
                "# 创意指导\n\n使用 slow dolly-in 运镜、明确动作变化、光色和声音节奏，但不改变用户意图。\n",
                encoding="utf-8",
            )
            payload = build_request(package)
            self.assertEqual("not_required", payload["status"])
            self.assertEqual([], payload["detected_reasons"])

    def test_legacy_migration_creates_valid_package_without_absolute_report_paths(self):
        spec = next(item for item in SPECS if item.skill_id == "architectural-assembly-reveal")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "legacy"
            source_root.mkdir()
            (source_root / spec.sources[0]).write_text(
                "# 建筑特写至全貌动态组装展示视频提示词生成 Skill\n\n"
                "## name\n建筑特写至全貌动态组装展示视频提示词生成 Skill\n\n"
                "## description\n将建筑外观参考图转为视频提示词。\n\n"
                "## 输入要求\n必须提供视频时长、画面比例和图片1。\n\n"
                "## 核心生成原则\n镜头使用 slow dolly-in，构件沿真实装配路径运动。\n\n"
                "## 合格镜头写法示例\n正例：图片1作为尾帧，构件压合后停止。\n\n"
                "## 常见失败案例与修正方法\n失败案例：只写自然组合。修正：写清装配目标。\n",
                encoding="utf-8",
            )
            result = migrate(spec, source_root, root / "out")
            self.assertEqual("migrated", result["status"])
            package = Path(result["package"])
            self.assertEqual([], validate_package(package))
            report_text = (package / "intake-report.json").read_text(encoding="utf-8")
            self.assertNotIn(str(source_root), report_text)
            self.assertIn("source_label", report_text)

    def test_legacy_wrapper_cleanup_removes_direct_generation_symbol(self):
        cleaned = strip_wrappers(
            "--- START OF FILE SKILL.md ---\n"
            "生成完成后调用 `generate_video`，不要写 seedance-cli。\n"
            "--- END OF FILE SKILL.md ---\n"
        )
        self.assertNotIn("START OF FILE", cleaned)
        self.assertNotIn("generate_video", cleaned)
        self.assertIn("统一视频生成入口", cleaned)


if __name__ == "__main__":
    unittest.main()
