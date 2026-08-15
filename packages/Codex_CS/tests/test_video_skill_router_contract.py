from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "video-skill-router" / "SKILL.md"


class VideoSkillRouterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_requires_settings_confirmation_before_project_creation(self):
        required = ["Skill 正式名称", "画幅比例", "视频时长", "project-pipeline"]
        for value in required:
            self.assertIn(value, self.text)
        self.assertLess(self.text.index("画幅比例"), self.text.index("调用 `project-pipeline`"))

    def test_routes_image_branches_through_unified_tool(self):
        for value in ["`generate`", "`user_supplied`", "`generate_image`", "最终图片"]:
            self.assertIn(value, self.text)
        for value in ["choose-image-stage", "scan <project-id>", "lock-final <project-id> --use-source"]:
            self.assertIn(value, self.text)

    def test_cs_authors_first_prompt_and_dt_only_revises(self):
        for value in [
            "CS Skill 拥有首版提示词生成主权",
            "任何提示词修改都自动交给 Codex_DT",
            "不检索提示词语料库",
            "最多 3 个高相关案例",
            "每个新版本都使旧确认失效",
            "`generate_video`",
        ]:
            self.assertIn(value, self.text)

    def test_lookup_command_does_not_use_removed_json_flag(self):
        command_section = self.text.split("## 本地命令", 1)[1].split("## 交互约定", 1)[0]
        self.assertIn('lookup_skill.py "<用户创作意图>"', command_section)
        self.assertNotIn("--json", command_section)

    def test_documents_real_project_pipeline_commands(self):
        for value in [
            "project_pipeline.py create",
            "--skill-confirmed",
            "set-cs-prompt",
            "request-revision",
            "set-dt-revision",
            "confirm-prompt",
            "start-generation",
        ]:
            self.assertIn(value, self.text)

    def test_plans_material_counts_from_skill_specific_pacing_rules(self):
        for value in ["`count_rule`", "`planned_count`", "计划数量", "不得用全库统一"]:
            self.assertIn(value, self.text)


if __name__ == "__main__":
    unittest.main()
