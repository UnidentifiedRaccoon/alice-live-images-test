from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts import clipmaker_lite_tune_compositor as compositor


class ClipmakerLiteTuneCompositorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plans, cls.targets = compositor.load_targets()

    def test_exact_frozen_matrix_and_model_durations(self) -> None:
        self.assertEqual(len(self.targets), 22)
        self.assertEqual(
            Counter(target.model_id for target in self.targets),
            Counter(compositor.EXPECTED_BY_MODEL),
        )
        self.assertEqual(len({target.key for target in self.targets}), 22)
        for target in self.targets:
            with self.subTest(key=target.key):
                self.assertEqual(
                    target.duration_seconds,
                    compositor.MODEL_DURATIONS[target.model_id],
                )
                self.assertEqual(
                    target.expected_frames,
                    target.duration_seconds * compositor.FPS,
                )

    def test_source_bitmaps_are_sha_bound_and_never_outputs(self) -> None:
        source_paths = {target.source_path for target in self.targets}
        self.assertEqual(len(source_paths), 11)
        for target in self.targets:
            with self.subTest(key=target.key):
                source = compositor.ROOT / target.source_path
                self.assertTrue(source.is_file())
                self.assertFalse(source.is_symlink())
                self.assertEqual(compositor.sha256_file(source), target.source_sha256)
                self.assertNotEqual(target.source_path, target.output_path)
                self.assertTrue(
                    target.output_path.as_posix().startswith(
                        compositor.VIDEO_ROOT_REL.as_posix() + "/"
                    )
                )

    def test_only_allowlisted_camera_and_verified_bounded_overlays(self) -> None:
        primitives = Counter(target.plan["primitive"] for target in self.targets)
        self.assertEqual(
            primitives,
            Counter({"camera_push": 14, "glint": 4, "highlight": 3, "pulse": 1}),
        )
        for target in self.targets:
            plan = target.plan
            self.assertIn(plan["primitive"], compositor.ALLOWED_PRIMITIVES)
            if plan["primitive"] in {"pulse", "highlight", "glint"}:
                self.assertEqual(plan["region_confidence"], "visual-verified")
                x, y, width, height = compositor.region(
                    plan["region"], label="test region"
                )
                self.assertLessEqual(x + width, 1)
                self.assertLessEqual(y + height, 1)
                self.assertLessEqual(plan["opacity"], 0.14)

    def test_rejects_unsupported_primitive_and_unsafe_region(self) -> None:
        with self.assertRaisesRegex(compositor.TuneCompositorError, "Unsupported"):
            compositor.validate_plan(
                {"primitive": "generative-fill"}, duration=5, label="bad"
            )
        bad = {
            "primitive": "glint",
            "region": {"x": 0.9, "y": 0.1, "width": 0.2, "height": 0.2},
            "region_confidence": "visual-verified",
            "direction": "left-to-right",
            "band_fraction": 0.1,
            "opacity": 0.05,
            "color": "soft-white",
            "timing": {"start": 0.1, "end": 4.7, "fade_in": 0.4, "fade_out": 0.7},
            "protected_content": ["text"],
            "rationale": "test",
        }
        with self.assertRaisesRegex(compositor.TuneCompositorError, "safe normalized bbox"):
            compositor.validate_plan(bad, duration=5, label="bad")

    def test_rejects_unsafe_paths_and_source_sha_change(self) -> None:
        for path in ("../source.png", "/tmp/source.png", "source\\image.png"):
            with self.subTest(path=path):
                with self.assertRaises(compositor.TuneCompositorError):
                    compositor.safe_relative(path, label="source")
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            self.skipTest("ffmpeg/ffprobe are required by the compositor contract")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.ppm"
            source.write_bytes(self.ppm(64, 48))
            target = self.synthetic_target(root, source)
            source.write_bytes(self.ppm(64, 48, rgb=(20, 40, 60)))
            with self.assertRaisesRegex(compositor.TuneCompositorError, "Source SHA"):
                compositor.render_target(
                    target, root=root, ffmpeg=ffmpeg, ffprobe=ffprobe
                )

    def test_fit_dimensions_never_upscales_and_are_yuv420_safe(self) -> None:
        self.assertEqual(compositor.fit_dimensions(773, 239), (773, 239, 774, 240))
        scaled_w, scaled_h, output_w, output_h = compositor.fit_dimensions(5039, 3359)
        self.assertLessEqual(scaled_w, 1920)
        self.assertLessEqual(scaled_h, 1080)
        self.assertEqual(output_w % 2, 0)
        self.assertEqual(output_h % 2, 0)

    def test_commands_are_local_no_audio_and_exact_frame_bounded(self) -> None:
        for target in self.targets:
            with self.subTest(key=target.key):
                command, _width, _height = compositor.command_for_target(
                    target,
                    compositor.ROOT / target.source_path,
                    Path("output.mp4"),
                    "/usr/bin/ffmpeg",
                )
                joined = " ".join(command)
                self.assertNotIn("http://", joined)
                self.assertNotIn("https://", joined)
                self.assertNotIn("s3", joined.lower())
                self.assertIn("-an", command)
                self.assertEqual(
                    command[command.index("-frames:v") + 1],
                    str(target.expected_frames),
                )
                self.assertEqual(command[command.index("-c:v") + 1], "libx264")

    def test_local_renderer_is_deterministic_exact_duration_and_no_audio(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if not ffmpeg or not ffprobe:
            self.skipTest("ffmpeg/ffprobe are required by the compositor contract")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.ppm"
            source.write_bytes(self.ppm(64, 48))
            target = self.synthetic_target(root, source)
            before = source.read_bytes()
            first = compositor.render_target(
                target, root=root, ffmpeg=ffmpeg, ffprobe=ffprobe
            )
            second = compositor.render_target(
                target, root=root, ffmpeg=ffmpeg, ffprobe=ffprobe
            )
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(first["media"], second["media"])
            self.assertEqual(first["media"]["duration_seconds"], 1.0)
            self.assertEqual(first["media"]["frames"], 30)
            self.assertEqual(first["media"]["audio_streams"], 0)
            self.assertTrue(all(first["contract_check"].values()))

    @staticmethod
    def ppm(width: int, height: int, rgb: tuple[int, int, int] = (90, 110, 130)) -> bytes:
        return f"P6\n{width} {height}\n255\n".encode() + bytes(rgb) * width * height

    @staticmethod
    def synthetic_target(root: Path, source: Path) -> compositor.Target:
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        return compositor.Target(
            case_id="test#01",
            model_id="google/veo-3.1-lite",
            duration_seconds=1,
            source_path=source.relative_to(root),
            source_sha256=source_sha,
            source_width=64,
            source_height=48,
            planning_run_id="test-run",
            planning_result_path="artifacts/test/result.json",
            scene_plan_sha256="0" * 64,
            output_path=Path("outputs/test.mp4"),
            plan={
                "primitive": "camera_push",
                "zoom_start": 1.0,
                "zoom_end": 1.02,
                "focal_point": {"x": 0.5, "y": 0.5},
                "ease": "smoothstep",
                "protected_content": ["fixture"],
                "rationale": "determinism test",
            },
        )


if __name__ == "__main__":
    unittest.main()
