from __future__ import annotations

import json
import os
import sys
import subprocess
import socket
import struct
import tempfile
import threading
import time
import unittest
import wave
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "CLI" / "Media-Router"))

from media_router.concurrency import SlotLease
from media_router.config import load_config
from media_router.errors import FailureClass, MediaRouterError
from media_router.image_router import ImageRouter
from media_router.image_inputs import prepare_provider_images
from media_router.output_validation import atomic_write_bytes, is_valid_image, is_valid_video
from media_router.provider_runtime import ProviderRuntime
from media_router.safe_logging import prompt_metadata, safe_text, write_json
from media_router.scheduler import rolling_map
from media_router.schemas import MediaRequest, ProviderResult, Readiness, TaskContext
from media_router.task_store import TaskStore
from media_router.video_router import (
    build_video_arguments,
    _prompt_preferences,
    select_video_command,
    VideoRouter,
)
from media_router.service import dated_video_group, execute, normalize_video_duration, validate_prompt_completeness
from media_router.providers import comfly_common
from media_router.providers.command_adapter import DreaminaAdapter, PythonImageAdapter, _run
from media_router.providers.comfly_adapter import ComflyAdapter
from media_router.providers.registry import build_registry

PNG = b"\x89PNG\r\n\x1a\n" + b"offline-image"


class FakeProvider:
    capability = "image"
    max_concurrency = 6

    def __init__(self, provider_id, model_id, result, calls, ready=True):
        self.provider_id, self.model_id, self.result, self.calls = provider_id, model_id, result, calls
        self.capacity_key, self.ready = provider_id, ready

    def check_readiness(self):
        return Readiness(self.ready, None if self.ready else "missing auth")

    def execute(self, request, context):
        self.calls.append(self.provider_id)
        if self.result == "success":
            output = context.output_dir / f"{self.provider_id}.png"
            atomic_write_bytes(output, PNG)
            return ProviderResult(self.provider_id, self.model_id, "success", output_path=str(output), output_bytes=len(PNG))
        failure = FailureClass(self.result)
        status = "needs_review" if failure == FailureClass.INDETERMINATE_SUBMISSION else "failed"
        return ProviderResult(self.provider_id, self.model_id, status, failure_class=failure, safe_reason="offline failure")


def router_config(ids):
    return {
        "image_timeouts": {"provider_seconds": 120, "task_seconds": 300},
        "media_inputs": {"max_image_long_edge": 1920},
        "providers": {provider_id: {"enabled": True, "priority": index, "max_concurrency": 6} for index, provider_id in enumerate(ids, 1)},
    }


def write_solid_png(path: Path, width: int, height: int) -> None:
    def chunk(name: bytes, value: bytes) -> bytes:
        return struct.pack(">I", len(value)) + name + value + struct.pack(">I", zlib.crc32(name + value) & 0xFFFFFFFF)

    row = b"\x00" + (b"\x33\x66\x99" * width)
    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(row * height, 9))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def png_dimensions(path: Path) -> tuple[int, int]:
    value = path.read_bytes()[:24]
    return struct.unpack(">II", value[16:24])


class ImageRouterTests(unittest.TestCase):
    def run_router(self, outcomes):
        calls, registry = [], {}
        for index, outcome in enumerate(outcomes, 1):
            provider_id = f"p{index}"
            registry[provider_id] = FakeProvider(provider_id, f"m{index}", outcome, calls)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        store = TaskStore(Path(temporary.name))
        result = ImageRouter(router_config(registry), registry, store).execute(MediaRequest("secret prompt", image_ratio="9:16"))
        return result, calls

    def test_strict_order_stops_after_success(self):
        result, calls = self.run_router([FailureClass.DEFINITE_PROVIDER_FAILURE, "success", "success"])
        self.assertEqual(result.status, "success")
        self.assertEqual(calls, ["p1", "p2"])

    def test_explicit_image_provider_runs_only_requested_adapter(self):
        calls = []
        registry = {
            "p1": FakeProvider("p1", "m1", "success", calls),
            "p2": FakeProvider("p2", "m2", "success", calls),
        }
        config = router_config(registry)
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_provider="p2", image_ratio="4:3"))
        self.assertEqual(result.status, "success")
        self.assertEqual(calls, ["p2"])

    def test_unknown_image_provider_is_input_error(self):
        calls = []
        registry = {"p1": FakeProvider("p1", "m1", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_provider="missing", image_ratio="4:3"))
        self.assertEqual(result.failure_class, FailureClass.INPUT_ERROR.value)
        self.assertIn("Unsupported image_provider", result.safe_reason)
        self.assertEqual(calls, [])

    def test_disabled_explicit_image_provider_is_input_error(self):
        calls = []
        registry = {"p1": FakeProvider("p1", "m1", "success", calls)}
        config = router_config(registry)
        config["providers"]["p1"]["enabled"] = False
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_provider="p1", image_ratio="4:3"))
        self.assertEqual(result.failure_class, FailureClass.INPUT_ERROR.value)
        self.assertIn("disabled", result.safe_reason)
        self.assertEqual(calls, [])

    def test_six_failures_are_recorded_in_order(self):
        result, calls = self.run_router([FailureClass.DEFINITE_PROVIDER_FAILURE] * 6)
        self.assertEqual(result.status, "failed")
        self.assertEqual(calls, [f"p{i}" for i in range(1, 7)])
        self.assertEqual([attempt["provider_id"] for attempt in result.attempts], calls)

    def test_non_fallback_failures_stop(self):
        for failure, status in ((FailureClass.POLICY_REJECTION, "failed"), (FailureClass.INDETERMINATE_SUBMISSION, "needs_review")):
            with self.subTest(failure=failure):
                result, calls = self.run_router([failure, "success"])
                self.assertEqual(result.status, status)
                self.assertEqual(calls, ["p1"])

    def test_missing_ratio_is_input_error_and_never_calls_provider(self):
        calls = []
        registry = {"p1": FakeProvider("p1", "m1", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt"))
        self.assertEqual(result.failure_class, FailureClass.INPUT_ERROR.value)
        self.assertIn("image_ratio is required", result.safe_reason)
        self.assertEqual(calls, [])

    def test_unsupported_ratio_is_input_error_and_never_calls_provider(self):
        calls = []
        registry = {"p1": FakeProvider("p1", "m1", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_ratio="5:7"))
        self.assertEqual(result.failure_class, FailureClass.INPUT_ERROR.value)
        self.assertEqual(calls, [])

    def test_unexpected_adapter_error_stops_as_needs_review(self):
        calls = []
        provider = FakeProvider("p1", "m1", "success", calls)
        provider.execute = lambda request, context: (_ for _ in ()).throw(RuntimeError("unknown outcome"))
        registry = {"p1": provider, "p2": FakeProvider("p2", "m2", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_ratio="1:1"))
        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.failure_class, FailureClass.INDETERMINATE_SUBMISSION.value)
        self.assertEqual(calls, [])

    def test_provider_timeout_falls_back_in_order(self):
        calls = []

        class DeadlineProvider(FakeProvider):
            def execute(self, request, context):
                calls.append(self.provider_id)
                while time.monotonic() < context.provider_deadline:
                    time.sleep(0.002)
                return ProviderResult(self.provider_id, self.model_id, "failed", failure_class=FailureClass.PROVIDER_TIMEOUT)

        registry = {
            "p1": DeadlineProvider("p1", "m1", "success", calls),
            "p2": FakeProvider("p2", "m2", "success", calls),
        }
        config = router_config(registry)
        config["image_timeouts"] = {"provider_seconds": 0.04, "task_seconds": 0.3}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_ratio="3:2"))
        self.assertEqual(result.status, "success")
        self.assertEqual(calls, ["p1", "p2"])
        self.assertEqual(result.attempts[0]["failure_class"], FailureClass.PROVIDER_TIMEOUT.value)

    def test_success_before_provider_timeout_stops_fallback(self):
        calls = []

        class FastProvider(FakeProvider):
            def execute(self, request, context):
                time.sleep(0.01)
                return super().execute(request, context)

        registry = {"p1": FastProvider("p1", "m1", "success", calls), "p2": FakeProvider("p2", "m2", "success", calls)}
        config = router_config(registry)
        config["image_timeouts"] = {"provider_seconds": 0.08, "task_seconds": 0.3}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt", image_ratio="3:2"))
        self.assertEqual(result.status, "success")
        self.assertEqual(calls, ["p1"])

    def test_task_timeout_is_terminal_and_persisted(self):
        calls = []

        class DeadlineProvider(FakeProvider):
            def execute(self, request, context):
                calls.append(self.provider_id)
                self.observed_budget = context.provider_deadline - time.monotonic()
                while time.monotonic() < context.provider_deadline:
                    time.sleep(0.002)
                return ProviderResult(self.provider_id, self.model_id, "failed", failure_class=FailureClass.PROVIDER_TIMEOUT)

        first = DeadlineProvider("p1", "m1", "success", calls)
        registry = {"p1": first, "p2": FakeProvider("p2", "m2", "success", calls)}
        config = router_config(registry)
        config["image_timeouts"] = {"provider_seconds": 0.2, "task_seconds": 0.05}
        with tempfile.TemporaryDirectory() as temporary:
            store = TaskStore(Path(temporary))
            started = time.monotonic()
            result = ImageRouter(config, registry, store).execute(MediaRequest("prompt", image_ratio="3:2"))
            elapsed = time.monotonic() - started
            state_files = list(Path(temporary).rglob("state.json"))
            result_files = list(Path(temporary).rglob("result.json"))
            state = json.loads(state_files[0].read_text(encoding="utf-8"))
            persisted = json.loads(result_files[0].read_text(encoding="utf-8"))
        self.assertLess(elapsed, 0.2)
        self.assertLessEqual(first.observed_budget, 0.06)
        self.assertEqual(calls, ["p1"])
        self.assertEqual(result.failure_class, FailureClass.TASK_TIMEOUT.value)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(persisted["failure_class"], FailureClass.TASK_TIMEOUT.value)

    def test_command_timeout_kills_process_before_it_writes_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "late.txt"
            log = root / "log.json"
            command = [sys.executable, "-B", "-c", "import pathlib,sys,time; time.sleep(1); pathlib.Path(sys.argv[1]).write_text('late')", str(marker)]
            with self.assertRaises(MediaRouterError) as caught:
                _run(command, 0.05, log, timeout_failure=FailureClass.PROVIDER_TIMEOUT)
            self.assertEqual(caught.exception.failure_class, FailureClass.PROVIDER_TIMEOUT)
            time.sleep(0.15)
            self.assertFalse(marker.exists())


class ProviderImageInputTests(unittest.TestCase):
    def test_oversized_image_is_resized_to_1920_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "wide.png"
            write_solid_png(source, 3840, 2160)
            original = source.read_bytes()
            store = TaskStore(root / "private")
            request = MediaRequest("prompt", (source,), image_ratio="16:9")
            context = store.create(request)

            prepared = prepare_provider_images(request, context, 1920)

            self.assertEqual(source.read_bytes(), original)
            self.assertNotEqual(prepared.images[0], source.resolve())
            self.assertTrue(str(prepared.images[0]).startswith(str(context.job_dir / "inputs")))
            self.assertEqual(png_dimensions(prepared.images[0]), (1920, 1080))

    def test_image_at_limit_is_sent_from_original_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "at-limit.png"
            write_solid_png(source, 1920, 1080)
            store = TaskStore(root / "private")
            request = MediaRequest("prompt", (source,), image_ratio="16:9")
            context = store.create(request)

            prepared = prepare_provider_images(request, context, 1920)

            self.assertEqual(prepared.images, (source.resolve(),))
            self.assertFalse((context.job_dir / "inputs" / "image-1.png").exists())

    def test_image_under_1920_but_over_byte_limit_is_reencoded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "large.png"
            from PIL import Image

            Image.effect_noise((1920, 1440), 100).convert("RGB").save(source, format="PNG")
            store = TaskStore(root / "private")
            request = MediaRequest("prompt", (source,), image_ratio="3:4")
            context = store.create(request)
            prepared = prepare_provider_images(request, context, 1920)
            self.assertNotEqual(prepared.images[0], source.resolve())
            self.assertLessEqual(prepared.images[0].stat().st_size, 4_500_000)

    def test_image_router_passes_only_normalized_images_to_provider(self):
        received = []

        class InspectingProvider(FakeProvider):
            def execute(self, request, context):
                received.extend(request.images)
                return super().execute(request, context)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "portrait.png"
            write_solid_png(source, 1500, 3000)
            calls = []
            provider = InspectingProvider("p1", "m1", "success", calls)
            result = ImageRouter(router_config({"p1": provider}), {"p1": provider}, TaskStore(root / "private")).execute(MediaRequest("prompt", (source,), image_ratio="9:16"))

            self.assertEqual(result.status, "success")
            self.assertEqual(png_dimensions(received[0]), (960, 1920))
            self.assertNotEqual(received[0], source.resolve())


class ImageRatioAdapterTests(unittest.TestCase):
    def context(self, root: Path) -> TaskContext:
        job = root / "job"
        (job / "outputs").mkdir(parents=True)
        (job / "logs").mkdir()
        prompt = job / "prompt.txt"
        prompt.write_text("prompt", encoding="utf-8")
        return TaskContext("batch", "task", job, job / "outputs", prompt, job / "cancel")

    def test_comfly_receives_structured_ratio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            context = self.context(root)
            adapter = ComflyAdapter("comfly-gemini-lite", "gemini-3.1-flash-image-preview", size_profile="gemini-resolution")

            def execute_once(model, prompt, images, output, **options):
                atomic_write_bytes(output, PNG)
                self.assertEqual(options["size"], "9:16")
                self.assertEqual(options["resolution"], "2K")
                self.assertEqual(model, "gemini-3.1-flash-image-preview-2k")
                return {"request_id": "offline", "output_bytes": output.stat().st_size}

            with mock.patch("media_router.providers.comfly_adapter.comfly_common.execute_once", side_effect=execute_once):
                adapter.models_by_resolution = {"2K": "gemini-3.1-flash-image-preview-2k"}
                result = adapter.execute(MediaRequest("prompt", image_ratio="9:16", image_resolution="2K"), context)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.model_id, "gemini-3.1-flash-image-preview-2k")

    def test_comfly_routes_apply_provider_defaults_when_resolution_is_omitted(self):
        cases = (
            ("comfly-gemini-lite", "gemini-3.1-flash-image-preview", "2K", "gemini-3.1-flash-image-preview-2k"),
            ("comfly-gpt-image-2", "gpt-image-2", "4K", "gpt-image-2"),
        )
        for provider_id, model_id, expected_resolution, expected_model in cases:
            with self.subTest(provider=provider_id), tempfile.TemporaryDirectory() as temporary:
                context = self.context(Path(temporary))
                adapter = ComflyAdapter(provider_id, model_id, size_profile="gemini-resolution" if "gemini" in provider_id else None)
                adapter.models_by_resolution = {"2K": "gemini-3.1-flash-image-preview-2k"} if "gemini" in provider_id else {}

                def execute_once(model, prompt, images, output, **options):
                    self.assertEqual(options["resolution"], expected_resolution)
                    self.assertEqual(model, expected_model)
                    atomic_write_bytes(output, PNG)
                    return {"request_id": "offline", "output_bytes": output.stat().st_size}

                with mock.patch("media_router.providers.comfly_adapter.comfly_common.execute_once", side_effect=execute_once):
                    result = adapter.execute(MediaRequest("prompt", image_ratio="9:16"), context)
                self.assertEqual(result.status, "success")

    def test_registry_uses_configured_comfly_model_and_profile(self):
        config = load_config(private_path=Path("missing-private-config.json"))
        registry = build_registry(config)
        adapter = registry["comfly-gemini-lite"]
        self.assertEqual(adapter.model_id, "gemini-3.1-flash-image-preview")
        self.assertEqual(adapter.size_profile, "gemini-resolution")
        self.assertEqual(adapter.models_by_resolution["4K"], "gemini-3.1-flash-image-preview-4k")

    def test_private_config_can_override_comfly_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / "media-router.json"
            private.write_text(json.dumps({"providers": {"comfly-gemini-lite": {"model": "replacement-model"}}}), encoding="utf-8")
            config = load_config(private_path=private)
            self.assertEqual(build_registry(config)["comfly-gemini-lite"].model_id, "replacement-model")

    def test_python_image_adapters_receive_structured_ratio(self):
        cases = (
            ("apimart-gpt-image-2", "gpt-image-2", ROOT / "CLI" / "Gpt-API" / "gpt_api.py", "APIMART_API_KEY", "--size"),
            ("google-gemini-image", "gemini-3.1-flash-image", ROOT / "CLI" / "Gemini-API" / "gemini_api.py", "GEMINI_API_KEY", "--aspect-ratio"),
        )
        for provider_id, model_id, script, key_name, flag in cases:
            with self.subTest(provider=provider_id), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                context = self.context(root)
                adapter = PythonImageAdapter(provider_id, model_id, script, key_name)

                def run(command, timeout, log_path, **options):
                    self.assertEqual(command[command.index(flag) + 1], "3:4")
                    resolution_flag = "--resolution" if provider_id == "apimart-gpt-image-2" else "--image-size"
                    expected_resolution = "4k" if provider_id == "apimart-gpt-image-2" else "4K"
                    self.assertEqual(command[command.index(resolution_flag) + 1], expected_resolution)
                    atomic_write_bytes(context.output_dir / f"{provider_id}.png", PNG)
                    return subprocess.CompletedProcess(command, 0, "", "")

                with mock.patch("media_router.providers.command_adapter._run", side_effect=run):
                    result = adapter.execute(MediaRequest("prompt", image_ratio="3:4", image_resolution="4K"), context)
                self.assertEqual(result.status, "success")

    def test_python_image_routes_apply_provider_defaults_when_resolution_is_omitted(self):
        cases = (
            ("apimart-gpt-image-2", "gpt-image-2", ROOT / "CLI" / "Gpt-API" / "gpt_api.py", "APIMART_API_KEY", "--resolution", "4k"),
            ("google-gemini-image", "gemini-3.1-flash-image", ROOT / "CLI" / "Gemini-API" / "gemini_api.py", "GEMINI_API_KEY", "--image-size", "2K"),
        )
        for provider_id, model_id, script, key_name, resolution_flag, expected_resolution in cases:
            with self.subTest(provider=provider_id), tempfile.TemporaryDirectory() as temporary:
                context = self.context(Path(temporary))
                adapter = PythonImageAdapter(provider_id, model_id, script, key_name)

                def run(command, timeout, log_path, **options):
                    self.assertEqual(command[command.index(resolution_flag) + 1], expected_resolution)
                    atomic_write_bytes(context.output_dir / f"{provider_id}.png", PNG)
                    return subprocess.CompletedProcess(command, 0, "", "")

                with mock.patch("media_router.providers.command_adapter._run", side_effect=run):
                    result = adapter.execute(MediaRequest("prompt", image_ratio="3:4"), context)
                self.assertEqual(result.status, "success")

    def test_dreamina_receives_structured_ratio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            context = self.context(root)
            adapter = DreaminaAdapter("dreamina-image", "image", "4.0")
            with mock.patch.object(adapter, "execute_command", return_value=ProviderResult("dreamina-image", "4.0", "failed")) as execute_command:
                adapter.execute(MediaRequest("prompt", image_ratio="2:3"), context)
            arguments = execute_command.call_args.args[1]
        self.assertEqual(arguments[arguments.index("--ratio") + 1], "2:3")


class VideoRouterTests(unittest.TestCase):
    def test_video_duration_normalizes_unit_bearing_values(self):
        for value in (5, "5", "5s", "5 s", "5sec", "5seconds", "5秒"):
            with self.subTest(value=value):
                self.assertEqual(normalize_video_duration(value), "5")

    def test_video_duration_rejects_non_seconds_or_out_of_range(self):
        for value in (True, "5ms", "five", "3s", "31秒"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_video_duration(value)

    def test_execute_normalizes_duration_and_confirmation_before_router(self):
        with mock.patch("media_router.service.load_config", return_value={"providers": {}}), mock.patch("media_router.service.build_registry", return_value={"dreamina-video": object()}), mock.patch("media_router.service.VideoRouter") as router_type:
            router_type.return_value.execute.return_value = type("Result", (), {"to_dict": lambda self: {"status": "failed"}})()
            execute("generate_video", "motion", video_duration="5s", video_confirmation_duration="5秒")
            request = router_type.return_value.execute.call_args.args[0]
            self.assertEqual(request.video_duration, "5")
            self.assertEqual(request.video_confirmation_duration, "5")

    def test_video_group_gets_local_date_prefix_outside_base_limit(self):
        from datetime import date

        base = "华为 Mate 80_产品视频"
        self.assertLessEqual(len(base), 20)
        self.assertEqual(dated_video_group(base, date(2026, 8, 20)), "2026_08_20-华为 Mate 80_产品视频")

    def test_video_group_rejects_base_over_twenty_characters(self):
        with self.assertRaisesRegex(ValueError, "1-20"):
            dated_video_group("一" * 21)

    def test_terminal_wrapped_prompt_is_rejected(self):
        prompt = "Exit code: 0\nWall time: 0.7 seconds\nOutput:\n画面比例：9:16，视频时长：20秒。"
        with self.assertRaisesRegex(ValueError, "terminal execution metadata"):
            validate_prompt_completeness(prompt)

    def test_shared_boundary_does_not_apply_project_specific_prompt_rules(self):
        validate_prompt_completeness("画面比例9:16，视频时长20秒。每个5秒镜头使用对应图片。0-5秒对应图片2。")
        validate_prompt_completeness("JH_11，10-20秒。")
    def test_duration_parser_ignores_terminal_wall_time(self):
        prompt = "Exit code: 0\nWall time: 0.6 seconds\nOutput:\n画面比例：9:16 视频时长：20秒"
        self.assertEqual(_prompt_preferences(prompt), ("9:16", "20", None))

    def request(self, root, prompt="motion", images=0, videos=0, audios=0):
        paths = []
        for index in range(images + videos + audios):
            path = root / f"media-{index}.bin"
            path.write_bytes(b"x")
            paths.append(path)
        return MediaRequest(prompt, tuple(paths[:images]), tuple(paths[images:images+videos]), tuple(paths[images+videos:]))

    def test_command_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = [
                (self.request(root), "text2video"),
                (self.request(root, images=1), "multimodal2video"),
                (self.request(root, prompt="使用首尾帧", images=2), "frames2video"),
                (self.request(root, images=3), "multimodal2video"),
                (self.request(root, videos=1), "multimodal2video"),
                (self.request(root, images=1, audios=1), "multimodal2video"),
                (self.request(root, videos=1, audios=1), "multimodal2video"),
                (self.request(root, audios=1), "multimodal2video"),
            ]
            for request, expected in cases:
                self.assertEqual(select_video_command(request), expected)

    def test_audio_only_rejected_for_non_seedance_25_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary), audios=1)
            request = MediaRequest(request.prompt, request.images, request.videos, request.audios, video_model="seedance2.0_vip", video_model_selection_source="user_explicit")
            with self.assertRaises(ValueError):
                select_video_command(request)

    def test_legacy_multiframe_command_is_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary), images=3)
            request = MediaRequest(request.prompt, request.images, video_command="multiframe2video")
            with self.assertRaisesRegex(ValueError, "disabled legacy"):
                select_video_command(request)
            with self.assertRaisesRegex(ValueError, "disabled legacy"):
                build_video_arguments("multiframe2video", request)

    def test_supported_commands_default_to_seedance_25_480p(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary))
            args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--model_version") + 1], "seedance2.5")
        self.assertEqual(args[args.index("--video_resolution") + 1], "480p")
        self.assertEqual(args[args.index("--poll") + 1], "180")

    def test_video_session_is_forwarded_to_cli(self):
        request = MediaRequest("motion", video_session_id="19641853702412")
        args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--session") + 1], "19641853702412")

    def test_dreamina_session_parser_requires_exact_group_name(self):
        table = "ID NAME PINNED UPDATED_AT\n19641853702412 项目A No 2026-08-18 20:56\n19625962609164 项目AB No 2026-08-18 17:27"
        self.assertEqual(DreaminaAdapter._session_id(table, "项目A"), "19641853702412")
        self.assertIsNone(DreaminaAdapter._session_id(table, "项目"))
        self.assertEqual(DreaminaAdapter._session_id('{"session_id": "19641853702412"}'), "19641853702412")

    def test_prompt_resolution_words_do_not_override_default(self):
        request = MediaRequest("画面细节参考 4K，禁止 720p 输出")
        args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--video_resolution") + 1], "480p")

    def test_formal_submission_requires_matching_confirmation(self):
        router = VideoRouter({}, type("Provider", (), {})())
        with self.assertRaisesRegex(ValueError, "requires confirmation"):
            router.validate(MediaRequest("motion", video_duration="5"))
        request = MediaRequest("motion", video_duration="5", video_confirmation_model="seedance2.5", video_confirmation_resolution="480p", video_confirmation_duration="5")
        self.assertEqual(router.validate(request), "text2video")

    def test_seedance_25_accepts_1080p(self):
        router = VideoRouter({}, type("Provider", (), {})())
        request = MediaRequest("motion", video_duration="5", video_resolution="1080p", video_confirmation_model="seedance2.5", video_confirmation_resolution="1080p", video_confirmation_duration="5")
        self.assertEqual(router.validate(request), "text2video")

    def test_seedance_25_rejects_4k(self):
        router = VideoRouter({}, type("Provider", (), {})())
        request = MediaRequest("motion", video_duration="5", video_resolution="4k", video_confirmation_model="seedance2.5", video_confirmation_resolution="4k", video_confirmation_duration="5")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            router.validate(request)

    def test_test_channel_forces_non_vip_seedance_20_720p_without_polling(self):
        request = MediaRequest(
            "motion",
            video_command="text2video",
            video_model="seedance2.5",
            video_resolution="480p",
            video_execution_mode="test_submit_only",
        )
        args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--model_version") + 1], "seedance2.0")
        self.assertEqual(args[args.index("--video_resolution") + 1], "720p")
        self.assertEqual(args[args.index("--poll") + 1], "0")

    def test_trusted_production_submit_only_keeps_model_and_disables_polling(self):
        request = MediaRequest(
            "motion",
            video_command="text2video",
            video_model="seedance2.5",
            video_resolution="480p",
            video_execution_mode="production_submit_only",
        )
        args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--model_version") + 1], "seedance2.5")
        self.assertEqual(args[args.index("--video_resolution") + 1], "480p")
        self.assertEqual(args[args.index("--poll") + 1], "0")

    def test_internal_batch_mode_submits_without_cli_polling(self):
        request = MediaRequest(
            "motion",
            video_command="text2video",
            video_model="seedance2.5",
            video_resolution="480p",
            video_execution_mode="production_batch",
            video_duration="5",
            video_confirmation_model="seedance2.5",
            video_confirmation_resolution="480p",
            video_confirmation_duration="5",
        )
        args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--poll") + 1], "0")
        self.assertEqual(VideoRouter({}, type("Provider", (), {})()).validate(request), "text2video")

    def test_test_channel_does_not_require_user_explicit_model_source(self):
        router = VideoRouter({}, type("Provider", (), {})())
        request = MediaRequest("motion", video_command="text2video", video_execution_mode="test_submit_only")
        self.assertEqual(router.validate(request), "text2video")

    def test_test_channel_also_rejects_legacy_multiframe_command(self):
        router = VideoRouter({}, type("Provider", (), {})())
        request = MediaRequest("motion", video_command="multiframe2video", video_execution_mode="test_submit_only")
        with self.assertRaisesRegex(ValueError, "disabled legacy"):
            router.validate(request)

    def test_test_channel_rejects_duration_over_15_seconds(self):
        router = VideoRouter({}, type("Provider", (), {})())
        request = MediaRequest("视频时长：20秒", video_command="text2video", video_execution_mode="test_submit_only")
        with self.assertRaisesRegex(ValueError, "4-15"):
            router.validate(request)

    def test_test_channel_rejects_multiple_tasks(self):
        with self.assertRaisesRegex(ValueError, "exactly one task"):
            execute("generate_video", "motion", video_execution_mode="test_submit_only", video_count=2, video_group="纸飞机_功能测试")

    def test_test_channel_requires_group_before_submission(self):
        with self.assertRaisesRegex(ValueError, "requires video_group"):
            execute("generate_video", "motion", video_execution_mode="test_submit_only")

    def test_test_adapter_returns_submitted_without_querying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / "job"
            output = job / "outputs"
            logs = job / "logs"
            output.mkdir(parents=True)
            logs.mkdir()
            prompt = job / "prompt.txt"
            prompt.write_text("motion", encoding="utf-8")
            context = TaskContext("batch", "task", job, output, prompt, job / "cancel")
            request = MediaRequest("motion", video_execution_mode="test_submit_only")
            adapter = DreaminaAdapter("dreamina-video", "video", "seedance2.5")
            completed = subprocess.CompletedProcess([], 0, 'submit_id=task_XY-9\ngen_status=querying', "")
            with mock.patch("media_router.providers.command_adapter._run", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "", ""), completed]), mock.patch.object(adapter, "_query_and_download") as query:
                result = adapter.execute_command("text2video", ["--prompt", "motion", "--model_version", "seedance2.0", "--poll", "0"], request, context)
            self.assertEqual(result.status, "submitted")
            self.assertEqual(result.submit_id, "task_XY-9")
            self.assertEqual(result.model_id, "seedance2.0")
            self.assertEqual(result.provider_status, "querying")
            self.assertFalse(result.polling_performed)
            query.assert_not_called()

    def test_download_selection_is_bound_to_submit_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / "job"
            output = job / "outputs"
            target = output / "dreamina-video"
            target.mkdir(parents=True)
            (job / "logs").mkdir()
            prompt = job / "prompt.txt"
            prompt.write_text("motion", encoding="utf-8")
            wrong = target / "other-task_video_1.mp4"
            expected = target / "wanted-task_video_1.mp4"
            wrong.write_bytes(b"video")
            expected.write_bytes(b"video")
            context = TaskContext("batch", "task", job, output, prompt, job / "cancel")
            adapter = DreaminaAdapter("dreamina-video", "video", "seedance2.5")
            completed = subprocess.CompletedProcess([], 0, 'submit_id=wanted-task\ngen_status=success', "")
            with mock.patch("media_router.providers.command_adapter._run", return_value=completed), mock.patch("media_router.providers.command_adapter.is_valid_video", return_value=True):
                selected = adapter._query_and_download("wanted-task", context, "video")
            self.assertEqual(selected, expected)

    def test_production_submit_only_returns_submitted_without_querying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / "job"
            (job / "outputs").mkdir(parents=True)
            (job / "logs").mkdir()
            prompt = job / "prompt.txt"
            prompt.write_text("motion", encoding="utf-8")
            context = TaskContext("batch", "task", job, job / "outputs", prompt, job / "cancel")
            request = MediaRequest("motion", video_execution_mode="production_submit_only")
            adapter = DreaminaAdapter("dreamina-video", "video", "seedance2.5")
            completed = subprocess.CompletedProcess([], 0, 'submit_id=prod-task\ngen_status=success', "")
            with mock.patch("media_router.providers.command_adapter._run", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "", ""), completed]), mock.patch.object(adapter, "_query_and_download") as query:
                result = adapter.execute_command("text2video", ["--model_version", "seedance2.5", "--poll", "0"], request, context)
            self.assertEqual(result.status, "submitted")
            self.assertEqual(result.model_id, "seedance2.5")
            self.assertEqual(result.submit_id, "prod-task")
            query.assert_not_called()

    def test_test_adapter_rejects_provider_failure_and_missing_submit_id(self):
        cases = [
            ('gen_status=fail\nfail_reason=moderation rejected', "failed"),
            ('gen_status=querying', "needs_review"),
        ]
        for transcript, expected in cases:
            with self.subTest(transcript=transcript), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                job = root / "job"
                (job / "outputs").mkdir(parents=True)
                (job / "logs").mkdir()
                prompt = job / "prompt.txt"
                prompt.write_text("motion", encoding="utf-8")
                context = TaskContext("batch", "task", job, job / "outputs", prompt, job / "cancel")
                adapter = DreaminaAdapter("dreamina-video", "video", "seedance2.5")
                completed = subprocess.CompletedProcess([], 0, transcript, "")
                with mock.patch("media_router.providers.command_adapter._run", side_effect=[subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 0, "", ""), completed]), mock.patch.object(adapter, "_query_and_download") as query:
                    result = adapter.execute_command("text2video", ["--model_version", "seedance2.0", "--poll", "0"], MediaRequest("motion", video_execution_mode="test_submit_only"), context)
                self.assertEqual(result.status, expected)
                query.assert_not_called()

    def test_explicit_video_preferences_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary))
            request = MediaRequest(
                request.prompt,
                video_command="text2video",
                video_model="seedance2.0mini",
                video_model_selection_source="user_explicit",
                video_ratio="9:16",
                video_duration="8",
                video_resolution="1080p",
                video_confirmation_model="seedance2.0mini",
                video_confirmation_resolution="1080p",
                video_confirmation_duration="8",
            )
            self.assertEqual(select_video_command(request), "text2video")
            args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--model_version") + 1], "seedance2.0mini")
        self.assertEqual(args[args.index("--ratio") + 1], "9:16")
        self.assertEqual(args[args.index("--duration") + 1], "8")
        self.assertEqual(args[args.index("--video_resolution") + 1], "1080p")

    def test_seedance_20_requires_explicit_user_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = MediaRequest("motion", images=(root / "image.png",), video_model="seedance2.0_vip")
            (root / "image.png").write_bytes(b"image")
            router = VideoRouter({}, type("Provider", (), {})())
            with self.assertRaisesRegex(ValueError, "user_explicit"):
                router.validate(request)

    def test_structured_video_preferences_override_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = MediaRequest(
                "Exit code: 0\nWall time: 0.6 seconds\nOutput:\n画面比例：16:9 视频时长：6秒",
                images=(root / "image.png",),
                video_duration="20",
                video_ratio="9:16",
                video_model="seedance2.5",
                video_resolution="480p",
                video_confirmation_model="seedance2.5",
                video_confirmation_resolution="480p",
                video_confirmation_duration="20",
            )
            args = build_video_arguments("multimodal2video", request)
        self.assertEqual(args[args.index("--duration") + 1], "20")
        self.assertEqual(args[args.index("--ratio") + 1], "9:16")

    def test_limits_and_audio_duration(self):
        class Provider:
            pass
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, images=1, audios=1)
            router = VideoRouter({"providers": {}}, Provider(), TaskStore(root / "private"), duration_probe=lambda _: 1.9)
            with self.assertRaises(ValueError):
                router.validate(request)

    def test_video_router_passes_resized_image_to_cli_arguments(self):
        received = {}

        class Provider:
            capacity_key = "seedance-cli"
            max_concurrency = 6
            provider_id = "dreamina-video"
            model_id = "seedance2.5"

            def check_readiness(self):
                return Readiness(True)

            def execute_command(self, command, arguments, request, context):
                received.update(command=command, arguments=arguments, images=request.images)
                output = context.output_dir / "video.mp4"
                output.write_bytes(b"\x00\x00\x00\x18ftypoffline")
                return ProviderResult(self.provider_id, self.model_id, "success", output_path=str(output), output_bytes=output.stat().st_size)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "wide.png"
            write_solid_png(source, 3840, 2160)
            config = {"media_inputs": {"max_image_long_edge": 1920}, "providers": {}}
            result = VideoRouter(config, Provider(), TaskStore(root / "private")).execute(MediaRequest("motion", (source,), video_duration="5", video_confirmation_model="seedance2.5", video_confirmation_resolution="480p", video_confirmation_duration="5"))

            self.assertEqual(result.status, "success")
            self.assertEqual(received["command"], "multimodal2video")
            self.assertEqual(png_dimensions(received["images"][0]), (1920, 1080))
            image_argument = received["arguments"][received["arguments"].index("--image") + 1]
            self.assertEqual(Path(image_argument), received["images"][0])

    def test_multimodal_images_are_repeated_in_input_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, images=3)
            args = build_video_arguments("multimodal2video", request)
            image_values = [args[index + 1] for index, value in enumerate(args) if value == "--image"]
            self.assertEqual([Path(value) for value in image_values], list(request.images))
            self.assertEqual(args[args.index("--prompt") + 1], request.prompt)

    def test_multimodal_prompt_is_not_prefixed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, images=1, videos=1, audios=1)
            args = build_video_arguments("multimodal2video", request)
            prompt = args[args.index("--prompt") + 1]
            self.assertNotIn("参考引用规则", prompt)
            self.assertNotIn("--image", prompt)
            self.assertNotIn("@Image 1", prompt)

    def test_seedance_25_multimodal_allows_50_total_references(self):
        class Provider:
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, images=30, videos=10, audios=10)
            request = MediaRequest(request.prompt, request.images, request.videos, request.audios, video_duration="4", video_confirmation_model="seedance2.5", video_confirmation_resolution="480p", video_confirmation_duration="4")
            router = VideoRouter({"providers": {}}, Provider(), TaskStore(root / "private"), duration_probe=lambda _: 2)
            self.assertEqual(router.validate(request), "multimodal2video")

    def test_seedance_25_multimodal_rejects_over_50_total_references(self):
        class Provider:
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = self.request(root, images=30, videos=10, audios=11)
            router = VideoRouter({"providers": {}}, Provider(), TaskStore(root / "private"), duration_probe=lambda _: 2)
            with self.assertRaises(ValueError):
                router.validate(request)


class ConcurrencyTests(unittest.TestCase):
    def test_seventh_waits_then_acquires(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            leases = [SlotLease(root, "provider", f"task-{i}", wait_timeout=2).acquire() for i in range(6)]
            acquired = threading.Event()

            def seventh():
                with SlotLease(root, "provider", "task-7", wait_timeout=2):
                    acquired.set()

            thread = threading.Thread(target=seventh)
            thread.start()
            time.sleep(0.15)
            self.assertFalse(acquired.is_set())
            leases[0].release()
            self.assertTrue(acquired.wait(1))
            thread.join(1)
            for lease in leases[1:]:
                lease.release()

    def test_seedance_capacity_key_is_shared(self):
        config = load_config()
        self.assertEqual(config["providers"]["dreamina-image"]["capacity_key"], "seedance-cli")
        self.assertEqual(config["providers"]["dreamina-video"]["capacity_key"], "seedance-cli")

    def test_stale_dead_pid_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as temporary:
            lock_dir = Path(temporary) / "provider"
            lock_dir.mkdir()
            lock = lock_dir / "slot-1.lock"
            lock.write_text(json.dumps({"pid": 99999999}), encoding="utf-8")
            old = time.time() - 100
            os.utime(lock, (old, old))
            with SlotLease(Path(temporary), "provider", "new", slots=1, wait_timeout=1, stale_after=1) as lease:
                self.assertEqual(lease.path, lock)

    def test_cross_process_seventh_waits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = ROOT / "tests" / "fixtures" / "hold_provider_slot.py"
            environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            processes = [subprocess.Popen([sys.executable, "-B", str(helper), str(root), f"p-{i}", "1.2"], stdout=subprocess.PIPE, text=True, env=environment) for i in range(6)]
            try:
                for process in processes:
                    self.assertEqual(process.stdout.readline().strip(), "acquired")
                seventh = subprocess.Popen([sys.executable, "-B", str(helper), str(root), "p-7", "0"], stdout=subprocess.PIPE, text=True, env=environment)
                time.sleep(0.15)
                self.assertIsNone(seventh.poll())
                processes[0].terminate()
                processes[0].wait(2)
                self.assertEqual(seventh.stdout.readline().strip(), "acquired")
                self.assertEqual(seventh.wait(2), 0)
                seventh.stdout.close()
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(2)
                    if process.stdout:
                        process.stdout.close()


class SchedulerTests(unittest.TestCase):
    def test_rolling_six_and_runtime_three(self):
        for runtime_slots, expected_peak in ((6, 6), (3, 3)):
            active = peak = 0
            gate = threading.Lock()

            def runner(value):
                nonlocal active, peak
                with gate:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.04)
                with gate:
                    active -= 1
                return value

            self.assertEqual(rolling_map(range(8), runner, runtime_slots), list(range(8)))
            self.assertEqual(peak, expected_peak)

    def test_timed_out_image_task_releases_slot_for_next_task(self):
        started = []

        def runner(value):
            started.append((value, time.monotonic()))
            if value == 0:
                time.sleep(0.05)
                return FailureClass.TASK_TIMEOUT.value
            return "success"

        results = rolling_map(range(3), runner, runtime_slots=1)
        self.assertEqual(results, [FailureClass.TASK_TIMEOUT.value, "success", "success"])
        self.assertGreaterEqual(started[1][1] - started[0][1], 0.045)


class SafetyTests(unittest.TestCase):
    def test_logs_redact_prompt_and_secrets(self):
        prompt = "complete private prompt"
        record = {"prompt": prompt_metadata(prompt), "error": safe_text("Authorization: Bearer secret Cookie=private")}
        text = json.dumps(record)
        self.assertNotIn(prompt, text)
        self.assertNotIn("secret", text)
        self.assertNotIn("private", record["error"].lower())

    def test_safe_text_redacts_oauth_codes_and_tokens(self):
        value = safe_text("access_token=secret refresh_token=private device_code=abc user_code=xyz ordinary failure")
        for secret in ("secret", "private", "abc", "xyz"):
            self.assertNotIn(secret, value)
        self.assertIn("ordinary failure", value)

    def test_failed_command_logs_safe_stderr_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "failed.json"
            with self.assertRaisesRegex(MediaRouterError, "upload connection failed"):
                _run([sys.executable, "-B", "-c", "import sys; sys.stderr.write('upload connection failed'); raise SystemExit(1)"], 5, log)
            record = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(record["stderr_summary"], "upload connection failed")

    def test_atomic_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output.png"
            output.write_bytes(b"existing")
            with self.assertRaises(TypeError):
                atomic_write_bytes(output, None)
            self.assertEqual(output.read_bytes(), b"existing")

    def test_comfly_utf8_json_and_multipart_contract(self):
        prompt = "一只戴红围巾的猫"
        body = comfly_common.json_body("fixed-model", prompt, "1024x1024")
        self.assertEqual(json.loads(body.decode("utf-8"))["prompt"], prompt)
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / "a.png", Path(temporary) / "b.jpg"
            first.write_bytes(b"first-private")
            second.write_bytes(b"second-private")
            multipart, content_type = comfly_common.multipart_body("fixed-model", prompt, "1024x1024", (first, second), "OfflineBoundary")
        self.assertEqual(multipart.count(b'name="image"'), 2)
        self.assertIn(prompt.encode("utf-8"), multipart)
        self.assertEqual(content_type, "multipart/form-data; boundary=OfflineBoundary")
        self.assertEqual(comfly_common.DOWNLOAD_HEADERS["Referer"], "https://ai.comfly.org/")
        self.assertIn("image/", comfly_common.DOWNLOAD_HEADERS["Accept"])

    def test_comfly_gemini_normalizes_ratio_for_each_resolution(self):
        self.assertEqual(comfly_common.normalize_size("gemini-3.1-flash-image-preview", "1:1", "gemini-resolution", "1K"), "1024x1024")
        self.assertEqual(comfly_common.normalize_size("gemini-3.1-flash-image-preview-2k", "3:4", "gemini-resolution", "2K"), "1792x2400")
        self.assertEqual(comfly_common.normalize_size("gemini-3.1-flash-image-preview-4k", "16:9", "gemini-resolution", "4K"), "5504x3072")

    def test_comfly_gpt_image_2_maps_ratio_and_resolution_to_documented_size(self):
        self.assertEqual(comfly_common.normalize_size("gpt-image-2", "9:16", resolution="1K"), "720x1280")
        self.assertEqual(comfly_common.normalize_size("gpt-image-2", "9:16", resolution="2K"), "1152x2048")
        self.assertEqual(comfly_common.normalize_size("gpt-image-2", "9:16", resolution="4K"), "2160x3840")

    def test_comfly_gpt_image_2_request_uses_pixel_size_without_resolution_field(self):
        payload = json.loads(comfly_common.json_body("gpt-image-2", "prompt", "9:16", resolution="4K"))
        self.assertEqual(payload["size"], "2160x3840")
        self.assertNotIn("resolution", payload)
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "source.png"
            image.write_bytes(b"private")
            multipart, _ = comfly_common.multipart_body("gpt-image-2", "prompt", "9:16", (image,), "OfflineBoundary", resolution="4K")
        self.assertIn(b'name="size"\r\n\r\n2160x3840', multipart)
        self.assertNotIn(b'name="resolution"', multipart)

    def test_comfly_gpt_image_2_sizes_satisfy_provider_constraints(self):
        for resolution, sizes in comfly_common.GPT_IMAGE_2_SIZES.items():
            for ratio, size in sizes.items():
                width, height = (int(value) for value in size.split("x"))
                self.assertLessEqual(max(width, height), 3840, (resolution, ratio, size))
                self.assertEqual(width % 16, 0, (resolution, ratio, size))
                self.assertEqual(height % 16, 0, (resolution, ratio, size))
                self.assertLessEqual(max(width, height) / min(width, height), 3, (resolution, ratio, size))
                self.assertGreaterEqual(width * height, 655_360, (resolution, ratio, size))
                self.assertLessEqual(width * height, 8_294_400, (resolution, ratio, size))

    def test_comfly_timeout_detection_does_not_reclassify_other_network_errors(self):
        self.assertTrue(comfly_common._is_timeout_error(TimeoutError()))
        self.assertTrue(comfly_common._is_timeout_error(__import__("urllib.error").error.URLError(socket.timeout())))
        self.assertFalse(comfly_common._is_timeout_error(__import__("urllib.error").error.URLError("connection refused")))

    def test_media_signatures_reject_wrong_riff_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wav = root / "not-image.webp"
            wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVEpayload")
            webp = root / "image.webp"
            webp.write_bytes(b"RIFF\x00\x00\x00\x00WEBPpayload")
            avi = root / "video.avi"
            avi.write_bytes(b"RIFF\x00\x00\x00\x00AVI payload")
            self.assertFalse(is_valid_image(wav))
            self.assertTrue(is_valid_image(webp))
            self.assertTrue(is_valid_video(avi))


class RecoveryAndRuntimeTests(unittest.TestCase):
    def test_terminal_and_running_recovery_never_duplicate_submit(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = TaskStore(Path(temporary))
            job = Path(temporary) / "job"
            job.mkdir()
            for status, action in (("submitted", "do_not_retry"), ("failed", "do_not_retry"), ("needs_review", "do_not_retry"), ("cancelled", "do_not_retry")):
                write_json(job / "state.json", {"status": status})
                self.assertEqual(store.recovery_action(job)["action"], action)
            write_json(job / "state.json", {"status": "running"})
            self.assertEqual(store.recovery_action(job)["action"], "needs_review")
            write_json(job / "state.json", {"status": "running", "submit_id": "safe-id"})
            self.assertEqual(store.recovery_action(job)["action"], "resume_query")

    def test_provider_circuit_is_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = ProviderRuntime(root, "first", failure_threshold=2, cooldown_seconds=60)
            second = ProviderRuntime(root, "second", failure_threshold=2, cooldown_seconds=60)
            first.record(False)
            first.record(False)
            self.assertFalse(first.readiness()[0])
            self.assertTrue(second.readiness()[0])


class ConfigTests(unittest.TestCase):
    def test_default_image_timeouts(self):
        config = load_config()
        self.assertEqual(config["image_timeouts"], {"provider_seconds": 120, "task_seconds": 300})

    def test_image_timeouts_require_positive_integers(self):
        base = {"scheduler": {"max_child_agents": 1}, "providers": {}, "image_timeouts": {"provider_seconds": 120, "task_seconds": 300}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "absent.json"
            for name, value in (("provider_seconds", 0), ("provider_seconds", 1.5), ("task_seconds", True)):
                config = json.loads(json.dumps(base))
                config["image_timeouts"][name] = value
                default = root / f"{name}-{value}.json"
                default.write_text(json.dumps(config), encoding="utf-8")
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    load_config(default, private)

    def test_provider_image_limit_cannot_exceed_1920(self):
        base = {
            "scheduler": {"max_child_agents": 1},
            "providers": {},
            "image_timeouts": {"provider_seconds": 120, "task_seconds": 300},
            "media_inputs": {"max_image_long_edge": 1921},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            default = root / "config.json"
            default.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(default, root / "absent.json")


if __name__ == "__main__":
    unittest.main()
