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
from media_router.schemas import MediaRequest, ProviderResult, Readiness
from media_router.task_store import TaskStore
from media_router.video_router import build_video_arguments, select_video_command, VideoRouter
from media_router.providers import comfly_common
from media_router.providers.command_adapter import _run

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
        result = ImageRouter(router_config(registry), registry, store).execute(MediaRequest("secret prompt"))
        return result, calls

    def test_strict_order_stops_after_success(self):
        result, calls = self.run_router([FailureClass.DEFINITE_PROVIDER_FAILURE, "success", "success"])
        self.assertEqual(result.status, "success")
        self.assertEqual(calls, ["p1", "p2"])

    def test_seven_failures_are_recorded_in_order(self):
        result, calls = self.run_router([FailureClass.DEFINITE_PROVIDER_FAILURE] * 7)
        self.assertEqual(result.status, "failed")
        self.assertEqual(calls, [f"p{i}" for i in range(1, 8)])
        self.assertEqual([attempt["provider_id"] for attempt in result.attempts], calls)

    def test_non_fallback_failures_stop(self):
        for failure, status in ((FailureClass.POLICY_REJECTION, "failed"), (FailureClass.INDETERMINATE_SUBMISSION, "needs_review")):
            with self.subTest(failure=failure):
                result, calls = self.run_router([failure, "success"])
                self.assertEqual(result.status, status)
                self.assertEqual(calls, ["p1"])

    def test_input_error_never_calls_provider(self):
        calls = []
        registry = {"p1": FakeProvider("p1", "m1", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("", (Path("missing.png"),)))
        self.assertEqual(result.failure_class, FailureClass.INPUT_ERROR.value)
        self.assertEqual(calls, [])

    def test_unexpected_adapter_error_stops_as_needs_review(self):
        calls = []
        provider = FakeProvider("p1", "m1", "success", calls)
        provider.execute = lambda request, context: (_ for _ in ()).throw(RuntimeError("unknown outcome"))
        registry = {"p1": provider, "p2": FakeProvider("p2", "m2", "success", calls)}
        with tempfile.TemporaryDirectory() as temporary:
            result = ImageRouter(router_config(registry), registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt"))
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
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt"))
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
            result = ImageRouter(config, registry, TaskStore(Path(temporary))).execute(MediaRequest("prompt"))
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
            result = ImageRouter(config, registry, store).execute(MediaRequest("prompt"))
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
            request = MediaRequest("prompt", (source,))
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
            request = MediaRequest("prompt", (source,))
            context = store.create(request)

            prepared = prepare_provider_images(request, context, 1920)

            self.assertEqual(prepared.images, (source.resolve(),))
            self.assertFalse((context.job_dir / "inputs" / "image-1.png").exists())

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
            result = ImageRouter(router_config({"p1": provider}), {"p1": provider}, TaskStore(root / "private")).execute(MediaRequest("prompt", (source,)))

            self.assertEqual(result.status, "success")
            self.assertEqual(png_dimensions(received[0]), (960, 1920))
            self.assertNotEqual(received[0], source.resolve())


class VideoRouterTests(unittest.TestCase):
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
                (self.request(root, images=1), "image2video"),
                (self.request(root, prompt="使用首尾帧", images=2), "frames2video"),
                (self.request(root, images=3), "multiframe2video"),
                (self.request(root, videos=1), "multimodal2video"),
                (self.request(root, images=1, audios=1), "multimodal2video"),
                (self.request(root, videos=1, audios=1), "multimodal2video"),
            ]
            for request, expected in cases:
                self.assertEqual(select_video_command(request), expected)

    def test_audio_only_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                select_video_command(self.request(Path(temporary), audios=1))

    def test_multiframe_has_no_model_or_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary), images=3)
            args = build_video_arguments("multiframe2video", request)
        self.assertNotIn("--model_version", args)
        self.assertNotIn("--video_resolution", args)

    def test_supported_commands_default_to_seedance_2_vip(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary))
            args = build_video_arguments("text2video", request)
        self.assertEqual(args[args.index("--model_version") + 1], "seedance2.0_vip")
        self.assertEqual(args[args.index("--video_resolution") + 1], "720p")

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
            model_id = "seedance2.0_vip"

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
            result = VideoRouter(config, Provider(), TaskStore(root / "private")).execute(MediaRequest("motion", (source,)))

            self.assertEqual(result.status, "success")
            self.assertEqual(received["command"], "image2video")
            self.assertEqual(png_dimensions(received["images"][0]), (1920, 1080))
            image_argument = received["arguments"][received["arguments"].index("--image") + 1]
            self.assertEqual(Path(image_argument), received["images"][0])


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
            for status, action in (("failed", "do_not_retry"), ("needs_review", "do_not_retry"), ("cancelled", "do_not_retry")):
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
