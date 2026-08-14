from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "codex-media-plugin"
sys.path.insert(0, str(ROOT / "CLI" / "Media-Router"))
sys.path.insert(0, str(PLUGIN / "mcp"))

SPEC = importlib.util.spec_from_file_location("codex_media_server", PLUGIN / "mcp" / "server.py")
server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(server)


class PluginContractTests(unittest.TestCase):
    def test_only_two_tools_are_public(self):
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = reply["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["generate_image", "generate_video"])
        self.assertTrue(all(tool["annotations"]["openWorldHint"] for tool in tools))

    def test_exact_public_schemas(self):
        tools = {tool["name"]: tool["inputSchema"] for tool in server.TOOLS}
        self.assertEqual(set(tools["generate_image"]["properties"]), {"prompt", "images"})
        self.assertEqual(set(tools["generate_video"]["properties"]), {"prompt", "images", "videos", "audios", "video_duration", "video_ratio", "video_model", "video_model_selection_source", "video_execution_mode", "video_resolution"})
        self.assertFalse(tools["generate_image"]["additionalProperties"])
        self.assertFalse(tools["generate_video"]["additionalProperties"])

    def test_provider_skills_are_not_implicit(self):
        for name in ("gemini-api", "gemini-cli", "seedance-cli", "gpt-api", "comfly-api"):
            value = (ROOT / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: false", value)

    def test_default_video_prompt_sets_sound_effects_only(self):
        skill = (PLUGIN / "skills" / "default-video-generation" / "SKILL.md").read_text(encoding="utf-8")
        agent = (PLUGIN / "skills" / "default-video-generation" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        instruction = "不生成音乐，仅生成音效。"
        self.assertIn(instruction, skill)
        self.assertIn(instruction, agent)

    def test_submitted_video_is_a_non_error_response(self):
        submitted = {"status": "submitted", "submit_id": "task-123", "model_id": "seedance2.0"}
        with mock.patch.object(server, "execute", return_value=submitted):
            reply = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "test", "video_execution_mode": "test_submit_only"}}})
        result = reply["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"], submitted)


if __name__ == "__main__":
    unittest.main()
