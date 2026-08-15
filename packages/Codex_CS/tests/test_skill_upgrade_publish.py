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

from skill_package import package_sha256, validate_package  # noqa: E402


def finalize_template(package: Path, marker: str) -> None:
    contract_path = package / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["references"][0]["description"] = "作为主要场景与构图参考，创作前必须完成视觉观察"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replacements = {
        "<!-- CURATOR-REQUIRED: 用一段话说明该 Skill 独有的业务目标，不重复 description。 -->": f"根据场景参考设计连续、明确且可执行的视频提示词。{marker}",
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


class SkillUpgradePublishTests(unittest.TestCase):
    def scaffold(self, root: Path, marker: str) -> Path:
        completed = subprocess.run([
            sys.executable, str(SCRIPTS / "scaffold_business_skill.py"),
            "--skill-id", "sample-video-skill",
            "--display-name", "样本视频业务 Skill",
            "--description", "根据用户提供的场景参考素材编写专业、连续且可执行的视频生成提示词。",
            "--short-description", "根据已确认参考素材与专业业务规则编写连续且可执行的视频生成提示词",
            "--output", str(root),
        ], text=True, capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        package = root / "sample-video-skill"
        finalize_template(package, marker)
        return package

    def publish_initial(self, package: Path, library: Path, source: Path) -> None:
        completed = subprocess.run([
            sys.executable, str(SCRIPTS / "publish_skill.py"), str(package),
            "--library-root", str(library), "--source", str(source), "--approved-by", "user",
        ], text=True, capture_output=True, encoding="utf-8", check=False)
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

    def write_report(self, package: Path, source: Path, *, supplement: str = "not_required", blockers=None) -> None:
        report = {
            "schema_version": 1,
            "status": "ready_for_approval",
            "skill_id": package.name,
            "sources": [{"name": source.name, "sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest()}],
            "creative_supplement": {"status": supplement},
            "contract_conflicts": [],
            "blocking_questions": blockers or [],
            "validation_issues": [],
        }
        (package / "intake-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def run_upgrade(self, staging: Path, library: Path, source: Path):
        return subprocess.run([
            sys.executable, str(SCRIPTS / "upgrade_published_skill.py"), str(staging),
            "--library-root", str(library), "--source", str(source), "--approved-by", "user",
        ], text=True, capture_output=True, encoding="utf-8", check=False)

    def test_upgrades_existing_valid_skill_and_renews_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            source.write_text("# reviewed source\n", encoding="utf-8")
            library = root / "library"
            initial = self.scaffold(root / "initial", "OLD")
            self.publish_initial(initial, library, source)
            old_hash = json.loads((library / initial.name / "intake-receipt.json").read_text(encoding="utf-8"))["package_sha256"]

            staging = self.scaffold(root / "staging", "NEW")
            self.write_report(staging, source)
            completed = self.run_upgrade(staging, library, source)
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            published = library / staging.name
            self.assertIn("NEW", (published / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual([], validate_package(published, require_receipt=True))
            receipt = json.loads((published / "intake-receipt.json").read_text(encoding="utf-8"))
            self.assertNotEqual(old_hash, receipt["package_sha256"])
            self.assertEqual(package_sha256(published), receipt["package_sha256"])

    def test_rejects_unresolved_report_without_changing_published_skill(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            source.write_text("# reviewed source\n", encoding="utf-8")
            library = root / "library"
            initial = self.scaffold(root / "initial", "OLD")
            self.publish_initial(initial, library, source)
            before = package_sha256(library / initial.name)

            staging = self.scaffold(root / "staging", "NEW")
            self.write_report(staging, source, supplement="creative_supplement_pending", blockers=["confirm contract"])
            completed = self.run_upgrade(staging, library, source)
            self.assertNotEqual(0, completed.returncode)
            self.assertEqual(before, package_sha256(library / initial.name))
            self.assertIn("OLD", (library / initial.name / "SKILL.md").read_text(encoding="utf-8"))

    def test_rejects_invalid_existing_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            source.write_text("# reviewed source\n", encoding="utf-8")
            library = root / "library"
            initial = self.scaffold(root / "initial", "OLD")
            self.publish_initial(initial, library, source)
            with (library / initial.name / "SKILL.md").open("a", encoding="utf-8") as stream:
                stream.write("\ntampered\n")

            staging = self.scaffold(root / "staging", "NEW")
            self.write_report(staging, source, supplement="user_approved")
            completed = self.run_upgrade(staging, library, source)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("invalid credential", completed.stdout)

    def test_rejects_source_not_covered_by_report(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            source.write_text("# reviewed source\n", encoding="utf-8")
            other = root / "other.md"
            other.write_text("# different source\n", encoding="utf-8")
            library = root / "library"
            initial = self.scaffold(root / "initial", "OLD")
            self.publish_initial(initial, library, source)
            staging = self.scaffold(root / "staging", "NEW")
            self.write_report(staging, other)
            completed = self.run_upgrade(staging, library, source)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("not covered", completed.stdout)

    def test_upgrade_leaves_no_transaction_directories_inside_library(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            source.write_text("# reviewed source\n", encoding="utf-8")
            library = root / "library"
            initial = self.scaffold(root / "initial", "OLD")
            self.publish_initial(initial, library, source)
            staging = self.scaffold(root / "staging", "NEW")
            self.write_report(staging, source)
            completed = self.run_upgrade(staging, library, source)
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            self.assertEqual(["sample-video-skill"], sorted(path.name for path in library.iterdir()))
            transaction_root = root / ".codex-cs-private" / "upgrade-transactions"
            if transaction_root.exists():
                self.assertEqual([], list(transaction_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
