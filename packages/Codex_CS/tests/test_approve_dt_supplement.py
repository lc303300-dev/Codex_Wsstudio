from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "codex-cs-skill-curator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from approve_dt_supplement import SupplementApprovalError, approve  # noqa: E402


def finalize(package: Path) -> None:
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


class ApproveDtSupplementTests(unittest.TestCase):
    def package(self, root: Path) -> Path:
        completed = subprocess.run([
            sys.executable, str(SCRIPTS / "scaffold_business_skill.py"),
            "--skill-id", "sample-video-skill",
            "--display-name", "样本视频业务 Skill",
            "--description", "根据用户提供的场景参考素材编写专业、连续且可执行的视频生成提示词。",
            "--short-description", "根据已确认参考素材与专业业务规则编写连续且可执行的视频提示词",
            "--output", str(root),
        ], text=True, capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        package = root / "sample-video-skill"
        finalize(package)
        draft = {
            "schema_version": 1,
            "status": "draft",
            "operation": "supplement_skill_creative_examples",
            "source_skill_id": package.name,
            "generated_by": "Codex_DT",
            "provenance": {
                "benchmark_skill_ids": ["architectural-assembly-reveal"],
                "benchmark_usage": "creative_quality_only",
                "contract_inference": False,
                "topic_rule_copying": False,
            },
            "quality_rubric": {
                "dimensions": ["素材绑定", "动作可执行性", "结尾条件"],
                "assessment": "范例按目标 Skill 自身规则生成，结构完整且没有改变素材契约。",
            },
            "outputs": {
                "positive_examples": [{
                    "input_conditions": "用户提供一张场景图并明确主体动作与结尾状态。",
                    "prompt": "图片1绑定主体和场景。镜头缓慢推进，主体完成可见动作，最终稳定停在明确构图。",
                    "why_it_works": "素材、摄影机、主体动作和结尾状态均可观察并可审核。",
                }],
                "negative_examples": [{
                    "input_conditions": "同样使用图片1作为主要参考素材。",
                    "prompt": "画面自然变化并适当运动。",
                    "reason": "没有动作主体、方向、时间推进和结束条件。",
                    "correction": "分别补充摄影机运动、主体动作、可见结果和停止状态。",
                }],
                "boundary_examples": [{
                    "input_conditions": "用户已经提供内容完整且可执行的最终提示词。",
                    "boundary": "创意补写会改变用户已经固定的镜头意图。",
                    "handling": "仅修复引用编号和格式，不加入新的镜头、动作或视觉设定。",
                    "why": "用户明确内容优先，示例和默认经验不得覆盖当前指令。",
                }],
                "optional_creative_guidance": ["摄影机运动和主体动作应分别描述。"],
            },
        }
        review = package / "review"
        review.mkdir()
        (review / "dt-creative-supplement.draft.json").write_text(
            json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report = {
            "schema_version": 1,
            "status": "needs_review",
            "skill_id": package.name,
            "creative_supplement": {
                "status": "draft_received",
                "generated_by": "Codex_DT",
                "request_path": "dt-request.json",
                "draft_path": "review/dt-creative-supplement.draft.json",
                "requires_user_review": True,
                "reason": "draft received",
            },
            "extraction_summary": {},
            "blocking_questions": [],
            "contract_conflicts": [],
            "validation_issues": [],
            "user_approval": {"required": True, "approved": False},
        }
        (package / "intake-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return package

    def test_user_approval_merges_validated_draft_without_publishing(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.package(Path(raw))
            result = approve(package, "user")
            self.assertEqual("user_approved", result["status"])
            self.assertFalse(result["published"])
            examples = (package / "references" / "examples.md").read_text(encoding="utf-8")
            self.assertIn("Codex_DT 创意补充（用户已批准）", examples)
            self.assertIn("### 反例", examples)
            self.assertIn("### 边界案例", examples)
            report = json.loads((package / "intake-report.json").read_text(encoding="utf-8"))
            self.assertEqual("user_approved", report["creative_supplement"]["status"])
            self.assertEqual("ready_for_approval", report["status"])

    def test_rejects_non_user_or_unreceived_draft(self):
        with tempfile.TemporaryDirectory() as raw:
            package = self.package(Path(raw))
            with self.assertRaises(SupplementApprovalError):
                approve(package, "agent")
            report_path = package / "intake-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["creative_supplement"]["status"] = "creative_supplement_pending"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(SupplementApprovalError):
                approve(package, "user")


if __name__ == "__main__":
    unittest.main()
