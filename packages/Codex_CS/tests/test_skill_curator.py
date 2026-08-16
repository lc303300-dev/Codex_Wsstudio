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
from migrate_legacy_skills import (  # noqa: E402
    SPECS,
    extract_community_experience,
    extract_creative_guidance,
    extract_examples,
    extract_failure_section,
    migrate,
    strip_wrappers,
)
from prepare_dt_supplement import build_request  # noqa: E402
from receive_dt_supplement import DraftValidationError, receive  # noqa: E402
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

    def test_missing_count_rule_is_rejected_and_helper_adds_default(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            contract_path = package / "contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            del contract["references"][0]["count_rule"]
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            codes = {issue.code for issue in validate_package(package)}
            self.assertIn("INVALID_REFERENCE_FIELDS", codes)
            completed = subprocess.run([
                sys.executable, str(SCRIPTS / "add_count_rules.py"), str(package)
            ], text=True, capture_output=True, encoding="utf-8", check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
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

    def test_package_hash_is_stable_across_text_line_endings_and_bom(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            lf = root / "lf"
            crlf = root / "crlf"
            lf.mkdir()
            crlf.mkdir()
            (lf / "SKILL.md").write_text("第一行\n第二行\n", encoding="utf-8")
            (crlf / "SKILL.md").write_bytes(b"\xef\xbb\xbf" + "第一行\r\n第二行\r\n".encode("utf-8"))
            (lf / "contract.json").write_text('{"value": 1}\n', encoding="utf-8")
            (crlf / "contract.json").write_bytes(b'{"value": 1}\r\n')
            (lf / "asset.bin").write_bytes(b"same\r\nbytes")
            (crlf / "asset.bin").write_bytes(b"same\r\nbytes")
            self.assertEqual(package_sha256(lf), package_sha256(crlf))

    def test_package_hash_detects_text_and_binary_changes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "SKILL.md").write_text("内容\n", encoding="utf-8")
            (second / "SKILL.md").write_text("内容变化\n", encoding="utf-8")
            self.assertNotEqual(package_sha256(first), package_sha256(second))
            (second / "SKILL.md").write_text("内容\n", encoding="utf-8")
            (first / "asset.bin").write_bytes(b"a\r\nb")
            (second / "asset.bin").write_bytes(b"a\nb")
            self.assertNotEqual(package_sha256(first), package_sha256(second))

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
                "count_rule": {
                    "type": "fixed", "enforcement": "required", "fixed_count": 1,
                    "seconds_per_item": None, "rounding": None, "duration_share": 1,
                    "duration_to_count": [], "provenance": "source_explicit",
                    "confidence": "high", "rationale": "音乐参考固定使用一项即可锁定节奏与情绪"
                },
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
            self.assertIn("positive_examples_missing", payload["detected_reasons"])
            self.assertIn("negative_examples_missing", payload["detected_reasons"])
            self.assertIn("boundary_examples_missing", payload["detected_reasons"])
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

    def prepare_dt_intake(self, package: Path) -> None:
        request = build_request(package, force=True)
        (package / "dt-request.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        contract = json.loads((package / "contract.json").read_text(encoding="utf-8"))
        report = {
            "schema_version": 1,
            "status": "ready_for_approval",
            "skill_id": package.name,
            "display_name": contract["display_name"],
            "creative_supplement": {
                "status": "creative_supplement_pending",
                "generated_by": "prepare_dt_supplement.py",
                "request_path": "dt-request.json",
                "draft_path": None,
                "requires_user_review": True,
                "reason": "examples missing",
            },
            "user_approval": {"required": True, "approved": False},
        }
        (package / "intake-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def valid_dt_draft(self, skill_id: str) -> dict:
        return {
            "schema_version": 1,
            "status": "draft",
            "operation": "supplement_skill_creative_examples",
            "source_skill_id": skill_id,
            "generated_by": "Codex_DT",
            "provenance": {
                "benchmark_skill_ids": ["excellent-cinematic-reference"],
                "benchmark_usage": "creative_quality_only",
                "contract_inference": False,
                "topic_rule_copying": False,
            },
            "quality_rubric": {
                "dimensions": ["素材绑定", "镜头可执行性", "连续性"],
                "assessment": "案例已按优秀 Skill 的表达完整度检查，但未复制其题材规则。",
            },
            "outputs": {
                "positive_examples": [{
                    "input_conditions": "用户已确认一张主体身份图和一张有序场景图。",
                    "prompt": "镜头从场景全貌缓慢推进，主体结构与文字保持稳定，最后在确认构图处缓停。",
                    "why_it_works": "素材绑定、镜头动作、主体约束和结束条件均明确。",
                }],
                "negative_examples": [{
                    "input_conditions": "用户已提供主体与场景参考，但没有指定额外动作。",
                    "prompt": "镜头自然变化，主体自由运动并形成震撼画面。",
                    "reason": "动作和空间关系不可执行，并擅自增加主体运动。",
                    "correction": "分别写清摄影机运动与主体约束，并给出可观察的结束条件。",
                }],
                "boundary_examples": [{
                    "input_conditions": "用户给出完整且已可执行的提示词，只要求规范格式。",
                    "boundary": "不得借助优秀 Skill 范例新增题材、动作或素材要求。",
                    "handling": "仅修正引用标签、标点和明确的术语错误，保留原始创意。",
                    "why": "完整提示词只需要语义保持型规范化，不需要创意重写。",
                }],
                "optional_creative_guidance": ["分别描述摄影机运动和主体运动。"],
            },
        }

    def test_receive_dt_supplement_stages_draft_without_modifying_references(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw) / "staging")
            finalize_template(package)
            self.prepare_dt_intake(package)
            examples_before = (package / "references" / "examples.md").read_text(encoding="utf-8")
            draft_path = Path(raw) / "dt-draft.json"
            draft_path.write_text(
                json.dumps(self.valid_dt_draft(package.name), ensure_ascii=False, indent=2), encoding="utf-8"
            )

            result = receive(package, draft_path)

            self.assertEqual("draft_received", result["status"])
            self.assertFalse(result["references_modified"])
            self.assertFalse(result["published"])
            self.assertTrue((package / "review" / "dt-creative-supplement.draft.json").is_file())
            self.assertEqual(examples_before, (package / "references" / "examples.md").read_text(encoding="utf-8"))
            report = json.loads((package / "intake-report.json").read_text(encoding="utf-8"))
            self.assertEqual("draft_received", report["creative_supplement"]["status"])
            self.assertEqual("review/dt-creative-supplement.draft.json", report["creative_supplement"]["draft_path"])
            self.assertFalse(report["user_approval"]["approved"])

    def test_receive_dt_supplement_rejects_contract_and_execution_pollution(self):
        polluted_values = [
            {"provider": "example"},
            "请使用 Seedance 并提交 generate_video。",
            "必须提供三张图片素材。",
        ]
        for polluted in polluted_values:
            with self.subTest(polluted=polluted), tempfile.TemporaryDirectory() as raw:
                package = self.scaffold(Path(raw) / "staging")
                finalize_template(package)
                self.prepare_dt_intake(package)
                draft = self.valid_dt_draft(package.name)
                if isinstance(polluted, dict):
                    draft["outputs"].update(polluted)
                else:
                    draft["outputs"]["positive_examples"] = [polluted]
                draft_path = Path(raw) / "dt-draft.json"
                draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")

                with self.assertRaises(DraftValidationError):
                    receive(package, draft_path)
                self.assertFalse((package / "review" / "dt-creative-supplement.draft.json").exists())
                report = json.loads((package / "intake-report.json").read_text(encoding="utf-8"))
                self.assertEqual("creative_supplement_pending", report["creative_supplement"]["status"])

    def test_receive_dt_supplement_rejects_missing_example_category(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw) / "staging")
            finalize_template(package)
            self.prepare_dt_intake(package)
            draft = self.valid_dt_draft(package.name)
            del draft["outputs"]["boundary_examples"]
            draft_path = Path(raw) / "dt-draft.json"
            draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(DraftValidationError):
                receive(package, draft_path)

    def test_receive_dt_supplement_rejects_benchmark_contract_inference(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw) / "staging")
            finalize_template(package)
            self.prepare_dt_intake(package)
            draft = self.valid_dt_draft(package.name)
            draft["provenance"]["contract_inference"] = True
            draft_path = Path(raw) / "dt-draft.json"
            draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(DraftValidationError):
                receive(package, draft_path)

    def test_receive_dt_supplement_rejects_single_sentence_placeholders(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw) / "staging")
            finalize_template(package)
            self.prepare_dt_intake(package)
            draft = self.valid_dt_draft(package.name)
            draft["outputs"]["positive_examples"] = ["镜头很好。"]
            draft_path = Path(raw) / "dt-draft.json"
            draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(DraftValidationError):
                receive(package, draft_path)

    def test_dt_supplement_requires_each_example_category(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.scaffold(Path(raw))
            finalize_template(package)
            (package / "references" / "examples.md").write_text(
                "# 示例\n\n## 正例\n\n主体与素材绑定清楚。\n",
                encoding="utf-8",
            )
            payload = build_request(package)
            self.assertEqual("creative_supplement_pending", payload["status"])
            self.assertNotIn("positive_examples_missing", payload["detected_reasons"])
            self.assertIn("negative_examples_missing", payload["detected_reasons"])
            self.assertIn("boundary_examples_missing", payload["detected_reasons"])

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
            self.assertEqual("needs_review", result["status"])
            package = Path(result["package"])
            self.assertEqual([], validate_package(package))
            report_text = (package / "intake-report.json").read_text(encoding="utf-8")
            self.assertNotIn(str(source_root), report_text)
            self.assertIn("source_label", report_text)
            report = json.loads(report_text)
            self.assertEqual("needs_review", report["status"])
            self.assertEqual("creative_supplement_pending", report["creative_supplement"]["status"])

    def test_legacy_knowledge_is_split_instead_of_copying_the_whole_source(self):
        source = (
            "## 输入要求\n必须提供图片1。\n\n"
            "## 核心创作规则\n镜头缓慢推进，保持材质稳定。\n\n"
            "## 社区实测经验\n多次反馈慢速运动更稳定。\n\n"
            "## 正例\n图片1绑定主体并写清动作。\n\n"
            "## 常见失败案例与修正方法\n表现：主体漂移。修复：锁定身份。\n"
        )
        creative = extract_creative_guidance(source)
        community = extract_community_experience(source)
        examples = extract_examples(source)
        failures = extract_failure_section(source)
        self.assertIn("镜头缓慢推进", creative)
        self.assertNotIn("必须提供图片1", creative)
        self.assertNotIn("多次反馈", creative)
        self.assertIn("多次反馈", community)
        self.assertNotIn("镜头缓慢推进", community)
        self.assertIn("图片1绑定主体", examples)
        self.assertIn("主体漂移", failures)

    def test_legacy_migration_allows_missing_optional_duplicate_source(self):
        spec = next(item for item in SPECS if item.skill_id == "giant-3d-logo-landmark-video")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "legacy"
            source_root.mkdir()
            (source_root / spec.sources[0]).write_text(
                "---\nname: 巨型 Logo Skill\ndescription: 使用Logo和地标图生成巡游提示词。\n---\n"
                "## 核心创作规则\n分别描述摄影机与Logo动作，保持身份稳定。\n",
                encoding="utf-8",
            )
            result = migrate(spec, source_root, root / "out")
            self.assertEqual("needs_review", result["status"])
            report = json.loads((Path(result["package"]) / "intake-report.json").read_text(encoding="utf-8"))
            self.assertEqual(1, len(report["sources"]))
            self.assertEqual(1, len(report["duplicate_check"]["optional_sources_missing"]))

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
