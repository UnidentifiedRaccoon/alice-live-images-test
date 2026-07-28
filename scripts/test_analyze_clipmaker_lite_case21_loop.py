import argparse
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

from scripts import analyze_clipmaker_lite_case21_loop as loop


def metadata(frame_count: int = 6) -> dict:
    return {
        "width": 1440,
        "height": 1440,
        "frame_rate": Fraction(30, 1),
        "frame_count": frame_count,
        "duration_seconds": frame_count / 30,
        "container": "mov,mp4,m4a,3gp,3g2,mj2",
        "codec": "h264",
        "pixel_format": "yuv420p",
        "has_audio": True,
        "bytes": 1234,
    }


def solid_frame(size: int, value: int = 100) -> bytearray:
    return bytearray([value] * (size * size * 3))


def set_offsets(frame: bytearray, offsets, value: int) -> None:
    for offset in offsets:
        frame[offset] = value
        frame[offset + 1] = value
        frame[offset + 2] = value


def good_frames(size: int = 64) -> dict[int, bytes]:
    region_offsets, _ = loop.build_region_offsets(size)
    all_region_offsets = sorted(
        {offset for offsets in region_offsets.values() for offset in offsets}
    )
    values = (100, 120, 135, 65, 80, 100)
    result = {}
    for index, value in enumerate(values):
        frame = solid_frame(size)
        if index not in (0, 5):
            set_offsets(frame, all_region_offsets, value)
        result[index] = bytes(frame)
    return result


class Case21LoopAnalyzerTest(unittest.TestCase):
    def test_good_synthetic_loop_detects_all_regions_and_passes(self) -> None:
        size = 64
        frames = good_frames(size)

        result = loop.analyze_decoded_frames(
            metadata(),
            list(frames),
            frames,
            size=size,
        )

        self.assertEqual(result["seam_status"], "pass")
        self.assertTrue(result["seam"]["position_closed"])
        self.assertTrue(
            result["seam"]["motion_discontinuity_proxy"]["motion_continuous"]
        )
        self.assertEqual(result["requested_region_count"], 7)
        self.assertEqual(result["regions_with_detected_motion"], 7)
        self.assertEqual(result["missing_motion_regions"], [])
        self.assertTrue(all(item["detected_motion"] for item in result["regions"]))
        self.assertEqual(
            result["collateral_activity"]["fidelity_status"], "pass"
        )
        self.assertEqual(result["fidelity_status"], "pass")

    def test_motion_proxy_rejects_direction_reversal_at_closed_seam(self) -> None:
        size = 64
        first = bytes(solid_frame(size, 100))
        second = bytes(solid_frame(size, 120))
        penultimate = bytes(solid_frame(size, 120))
        last = bytes(solid_frame(size, 100))

        result = loop.seam_metrics(
            first,
            second,
            penultimate,
            last,
            size=size,
        )

        self.assertTrue(result["position_closed"])
        self.assertEqual(result["first_vs_last"]["changed_pixel_ratio"], 0.0)
        self.assertFalse(
            result["motion_discontinuity_proxy"]["motion_continuous"]
        )
        self.assertEqual(
            result["motion_discontinuity_proxy"]["direction_conflict_ratio"],
            1.0,
        )
        self.assertEqual(result["seam_status"], "fail")
        self.assertEqual(result["failed_checks"], ["boundary-motion-continuity"])

    def test_missing_motion_bad_seam_and_collateral_motion_fail_fidelity(self) -> None:
        size = 64
        region_offsets, outside_offsets = loop.build_region_offsets(size)
        frames = {index: bytes(solid_frame(size)) for index in range(6)}
        mutable = {index: bytearray(frame) for index, frame in frames.items()}
        for index, value in ((1, 130), (2, 160), (3, 70), (4, 80), (5, 130)):
            set_offsets(mutable[index], region_offsets["battery"], value)
        set_offsets(mutable[2], outside_offsets[:128], 200)
        frames = {index: bytes(frame) for index, frame in mutable.items()}

        result = loop.analyze_decoded_frames(
            metadata(),
            list(frames),
            frames,
            size=size,
        )

        self.assertEqual(result["seam_status"], "fail")
        self.assertIn("first-last-position", result["seam"]["failed_checks"])
        self.assertTrue(
            next(
                item for item in result["regions"] if item["region_id"] == "battery"
            )["detected_motion"]
        )
        self.assertIn("ovaries", result["missing_motion_regions"])
        self.assertEqual(
            result["collateral_activity"]["fidelity_status"], "fail"
        )
        self.assertIn("collateral-motion", result["failed_checks"])
        self.assertEqual(result["fidelity_status"], "fail")

    def test_probe_video_reports_media_and_audio(self) -> None:
        response = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1440,
                    "height": 1440,
                    "pix_fmt": "yuv420p",
                    "avg_frame_rate": "30/1",
                    "nb_frames": "150",
                    "nb_read_frames": "150",
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {
                "duration": "5.000000",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "size": "456789",
            },
        }
        with mock.patch.object(loop, "_run", return_value=json.dumps(response).encode()):
            result = loop.probe_video(Path("fixture.mp4"), "ffprobe")

        self.assertEqual(result["width"], 1440)
        self.assertEqual(result["height"], 1440)
        self.assertEqual(result["frame_rate"], Fraction(30, 1))
        self.assertEqual(result["frame_count"], 150)
        self.assertEqual(result["duration_seconds"], 5.0)
        self.assertTrue(result["has_audio"])
        self.assertEqual(result["bytes"], 456789)

    def test_analyze_video_binds_metadata_frames_and_digest(self) -> None:
        size = 64
        frames = good_frames(size)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("videos/variant.mp4")
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fixture")
            with (
                mock.patch.object(loop, "probe_video", return_value=metadata()),
                mock.patch.object(
                    loop,
                    "analysis_frame_indices",
                    return_value=list(frames),
                ),
                mock.patch.object(
                    loop,
                    "extract_normalized_frames",
                    return_value=frames,
                ),
            ):
                result = loop.analyze_video(
                    loop.VideoSpec("variant-a", relative),
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    sample_count=6,
                    size=size,
                    root=root,
                )

        self.assertEqual(result["video_id"], "variant-a")
        self.assertEqual(result["path"], "videos/variant.mp4")
        self.assertEqual(
            result["sha256"],
            "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d",
        )
        self.assertEqual(result["media"]["frame_rate"], "30")
        self.assertEqual(result["sampling"]["frame_indices"], list(frames))
        self.assertEqual(result["seam_status"], "pass")
        self.assertEqual(result["fidelity_status"], "pass")

    def test_report_schema_and_counts_are_explicit(self) -> None:
        analyzed = {
            "video_id": "a",
            "seam_status": "pass",
            "fidelity_status": "fail",
        }
        with (
            mock.patch.object(loop, "analyze_video", return_value=analyzed),
            mock.patch.object(loop, "_tool_version", return_value="tool 1.0"),
        ):
            report = loop.build_report(
                [loop.VideoSpec("a", Path("a.mp4"))],
                ffmpeg="ffmpeg",
                ffprobe="ffprobe",
                sample_count=17,
                size=256,
            )

        self.assertEqual(report["schema_version"], loop.SCHEMA_VERSION)
        self.assertEqual(report["case"]["image_id"], "04")
        self.assertEqual(report["video_count"], 1)
        self.assertEqual(report["seam_pass_count"], 1)
        self.assertEqual(report["fidelity_pass_count"], 0)
        self.assertEqual(len(report["method"]["requested_regions"]), 7)
        self.assertEqual(report["videos"], [analyzed])

    def test_sampling_and_cli_paths_fail_closed(self) -> None:
        self.assertEqual(loop.analysis_frame_indices(10, 5), [0, 1, 2, 4, 7, 8, 9])
        with self.assertRaisesRegex(loop.LoopAnalysisError, "at least 5"):
            loop.evenly_spaced_frame_indices(10, 4)
        with self.assertRaisesRegex(loop.LoopAnalysisError, "Cannot take"):
            loop.evenly_spaced_frame_indices(4, 5)

        spec = loop.parse_video_spec("variant-a=videos/a.mp4")
        self.assertEqual(spec, loop.VideoSpec("variant-a", Path("videos/a.mp4")))
        for value in (
            "missing-equals.mp4",
            "Bad ID=videos/a.mp4",
            "a=../videos/a.mp4",
            "a=/tmp/a.mp4",
            "a=videos/a.mov",
        ):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    loop.parse_video_spec(value)


if __name__ == "__main__":
    unittest.main()
