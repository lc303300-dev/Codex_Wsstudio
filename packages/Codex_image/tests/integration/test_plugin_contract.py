from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
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
    def test_workspace_tools_are_public(self):
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = reply["result"]["tools"]
        self.assertEqual(
            [tool["name"] for tool in tools],
            ["generate_image", "generate_video", "convert_video_to_gif", "batch_generate_images", "prepare_video_previews", "start_video_batch", "validate_video_batch", "route_creative_skill", "scout_tools"],
        )
        self.assertTrue(all("openWorldHint" in tool["annotations"] for tool in tools))

    def test_exact_public_schemas(self):
        tools = {tool["name"]: tool["inputSchema"] for tool in server.TOOLS}
        self.assertEqual(set(tools["generate_image"]["properties"]), {"prompt", "images", "image_ratio", "image_resolution", "image_provider"})
        self.assertEqual(set(tools["generate_image"]["required"]), {"prompt", "image_ratio"})
        self.assertEqual(tools["generate_image"]["properties"]["image_ratio"]["enum"], ["21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"])
        self.assertEqual(tools["generate_image"]["properties"]["image_resolution"]["enum"], ["1K", "2K", "4K"])
        self.assertNotIn("default", tools["generate_image"]["properties"]["image_resolution"])
        self.assertEqual(tools["generate_image"]["properties"]["image_provider"]["enum"], ["comfly-gemini-lite", "comfly-gpt-image-2", "dreamina-image"])
        self.assertEqual(set(tools["generate_video"]["properties"]), {"prompt", "images", "videos", "audios", "video_duration", "video_ratio", "video_model", "video_model_selection_source", "video_execution_mode", "video_resolution", "video_confirmation_model", "video_confirmation_resolution", "video_confirmation_duration", "video_prompt_sha256", "video_test_confirmation", "video_count", "video_group"})
        self.assertFalse(tools["generate_image"]["additionalProperties"])
        self.assertFalse(tools["generate_video"]["additionalProperties"])
        self.assertEqual(set(tools["convert_video_to_gif"]["required"]), {"input_dir"})
        self.assertEqual(set(tools["batch_generate_images"]["required"]), {"manifest"})

    def test_batch_generation_requires_paid_confirmation(self):
        reply = server.handle({"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {"name": "batch_generate_images", "arguments": {"manifest": "x.json"}}})
        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["failure_class"], "confirmation_required")

    def test_auxiliary_tools_dispatch_without_provider_calls(self):
        with mock.patch.object(server, "_run_process", return_value={"status": "success", "exit_code": 0}) as run:
            reply = server.handle({"jsonrpc": "2.0", "id": 21, "method": "tools/call", "params": {"name": "route_creative_skill", "arguments": {"query": "楼盘宣传片"}}})
        self.assertFalse(reply["result"]["isError"])
        run.assert_called_once()

    def test_provider_skills_are_not_implicit(self):
        for name in ("gemini-api", "seedance-cli", "gpt-api", "comfly-api"):
            value = (ROOT / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: false", value)

    def test_default_video_prompt_sets_sound_effects_only(self):
        skill = (PLUGIN / "skills" / "default-video-generation" / "SKILL.md").read_text(encoding="utf-8")
        agent = (PLUGIN / "skills" / "default-video-generation" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        instruction = "不生成音乐，仅生成音效。"
        self.assertIn(instruction, skill)
        self.assertIn(instruction, agent)

    def test_default_video_skill_derives_a_group_name(self):
        skill = (PLUGIN / "skills" / "default-video-generation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("never invent a brand", skill)
        self.assertIn("distinctive subject and action or theme", skill)
        self.assertIn("华为 Mate 80_产品视频", skill)
        self.assertIn("do not use a bare `_视频` suffix", skill)
        self.assertIn("no longer than 20 Unicode characters", skill)
        self.assertIn("2026_08_20-华为 Mate 80_产品视频", skill)
        self.assertIn("Omit `video_group` only when the user explicitly asks", skill)

    def test_default_video_skill_requires_one_unified_concurrent_route(self):
        skill = (PLUGIN / "skills" / "default-video-generation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("one `generate_video` call", skill)
        self.assertIn("video_count", skill)
        self.assertIn("Codex_DT batch entrypoint", skill)
        self.assertNotIn("create a pending queue and keep up to `min(6, runtime_available_child_slots)` child agents", skill)
        self.assertNotIn("For two or more independent media tasks, create a pending queue", skill)

    def test_test_channel_is_documented_as_a_cancellable_submission_probe(self):
        skill = (PLUGIN / "skills" / "default-video-generation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("ten hours or longer", skill)
        self.assertIn("real but reversible submission probe", skill)
        self.assertIn("does not prove completion, output correctness, or visual quality", skill)
        self.assertIn("supports exactly one task", skill)
        self.assertIn("must never run concurrently", skill)
        self.assertIn("consumed credits are returned", skill)

    def test_submitted_video_is_a_non_error_response(self):
        submitted = {"status": "submitted", "submit_id": "task-123", "model_id": "seedance2.0"}
        with mock.patch.object(server, "execute", return_value=submitted):
            reply = server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "test", "video_execution_mode": "test_submit_only", "video_test_confirmation": "confirmed"}}})
        result = reply["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"], submitted)

    def test_public_mcp_rejects_reserved_production_submit_only(self):
        with mock.patch.object(server, "execute") as execute:
            reply = server.handle({"jsonrpc": "2.0", "id": 71, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "reviewed prompt", "video_execution_mode": "production_submit_only"}}})
        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertIn("reserved", result["structuredContent"]["safe_reason"])
        execute.assert_not_called()

    def test_public_mcp_requires_explicit_test_confirmation(self):
        with mock.patch.object(server, "execute") as execute:
            reply = server.handle({"jsonrpc": "2.0", "id": 72, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "test", "video_execution_mode": "test_submit_only"}}})
        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertIn("video_test_confirmation", result["structuredContent"]["safe_reason"])
        execute.assert_not_called()

    def test_successful_image_returns_renderable_content_and_file_uri(self):
        png = b"\x89PNG\r\n\x1a\n" + b"offline-image"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "图片 output.png"
            output.write_bytes(png)
            generated = {"status": "success", "output_path": str(output), "provider_id": "fake", "model_id": "fake-image"}
            with mock.patch.object(server, "execute", return_value=generated):
                reply = server.handle({"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "generate_image", "arguments": {"prompt": "test", "image_ratio": "9:16"}}})

        result = reply["result"]
        self.assertFalse(result["isError"])
        self.assertEqual([item["type"] for item in result["content"]], ["text", "image", "resource_link"])
        image = result["content"][1]
        self.assertEqual(image["mimeType"], "image/png")
        self.assertEqual(base64.b64decode(image["data"]), png)
        self.assertFalse(image["data"].startswith("data:"))
        resource = result["content"][2]
        self.assertEqual(resource["uri"], output.resolve().as_uri())
        self.assertNotIn("\\", resource["uri"])
        self.assertIn("%20", resource["uri"])
        self.assertIn("%E5%9B%BE%E7%89%87", resource["uri"])
        self.assertEqual(result["structuredContent"]["output_uri"], resource["uri"])

    def test_invalid_successful_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "broken.png"
            output.write_bytes(b"not-an-image")
            generated = {"status": "success", "output_path": str(output)}
            with mock.patch.object(server, "execute", return_value=generated):
                reply = server.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "generate_image", "arguments": {"prompt": "test", "image_ratio": "9:16"}}})

        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["status"], "failed")
        self.assertEqual(result["structuredContent"]["safe_reason"], "invalid_image_output")
        self.assertEqual([item["type"] for item in result["content"]], ["text"])

    def test_missing_image_ratio_is_rejected_before_provider_execution(self):
        with mock.patch.object(server, "execute", wraps=server.execute) as execute:
            reply = server.handle({"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "generate_image", "arguments": {"prompt": "test"}}})
        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["failure_class"], "input_error")
        self.assertIn("image_ratio is required", result["structuredContent"]["safe_reason"])
        execute.assert_called_once()

    def test_explicit_image_provider_is_forwarded(self):
        failed = {"status": "failed", "failure_class": "auth_unavailable"}
        with mock.patch.object(server, "execute", return_value=failed) as execute:
            server.handle({"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "generate_image", "arguments": {"prompt": "test", "image_ratio": "1:1", "image_provider": "dreamina-image"}}})
        self.assertEqual(execute.call_args.kwargs["image_provider"], "dreamina-image")

    def test_image_resolution_is_forwarded(self):
        failed = {"status": "failed", "failure_class": "auth_unavailable"}
        with mock.patch.object(server, "execute", return_value=failed) as execute:
            server.handle({"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {"name": "generate_image", "arguments": {"prompt": "test", "image_ratio": "1:1", "image_resolution": "4K"}}})
        self.assertEqual(execute.call_args.kwargs["image_resolution"], "4K")

    def test_successful_video_returns_file_resource_with_normalized_uri(self):
        mp4 = b"\x00\x00\x00\x18ftypisom" + b"offline-video"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "视频 output.mp4"
            output.write_bytes(mp4)
            generated = {"status": "success", "output_path": str(output), "provider_id": "fake", "model_id": "fake-video"}
            with mock.patch.object(server, "execute", return_value=generated):
                reply = server.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "test"}}})

        result = reply["result"]
        self.assertFalse(result["isError"])
        self.assertEqual([item["type"] for item in result["content"]], ["text", "resource_link"])
        resource = result["content"][1]
        self.assertEqual(resource["mimeType"], "video/mp4")
        self.assertEqual(resource["size"], len(mp4))
        self.assertEqual(resource["uri"], output.resolve().as_uri())
        self.assertNotIn("\\", resource["uri"])
        self.assertIn("%20", resource["uri"])
        self.assertIn("%E8%A7%86%E9%A2%91", resource["uri"])
        self.assertEqual(result["structuredContent"]["output_uri"], resource["uri"])

    def test_invalid_successful_video_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "broken.mp4"
            output.write_bytes(b"not-a-video")
            generated = {"status": "success", "output_path": str(output)}
            with mock.patch.object(server, "execute", return_value=generated):
                reply = server.handle({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "generate_video", "arguments": {"prompt": "test"}}})

        result = reply["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["status"], "failed")
        self.assertEqual(result["structuredContent"]["safe_reason"], "invalid_video_output")
        self.assertEqual([item["type"] for item in result["content"]], ["text"])


if __name__ == "__main__":
    unittest.main()
