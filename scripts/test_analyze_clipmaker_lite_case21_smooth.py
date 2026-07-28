import argparse
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

from scripts import analyze_clipmaker_lite_case21_loop as loop
from scripts import analyze_clipmaker_lite_case21_smooth as smooth


def metadata(frame_count: int = 12) -> dict:
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


def requested_offsets(size: int) -> tuple[int, ...]:
    region_offsets, _ = loop.build_region_offsets(size)
    return tuple(
        sorted({offset for offsets in region_offsets.values() for offset in offsets})
    )


def linear_frames(size: int = 64, frame_count: int = 12) -> list[bytes]:
    offsets = requested_offsets(size)
    frames = []
    for index in range(frame_count):
        frame = solid_frame(size)
        set_offsets(frame, offsets, 80 + index * 8)
        frames.append(bytes(frame))
    return frames


def jerky_frames(size: int = 64) -> list[bytes]:
    offsets = requested_offsets(size)
    values = (100, 102, 104, 106, 108, 110, 180, 114, 116, 118, 120, 122)
    frames = []
    for value in values:
        frame = solid_frame(size)
        set_offsets(frame, offsets, value)
        frames.append(bytes(frame))
    return frames


def ranked_video(
    video_id: str,
    *,
    coverage: int,
    abrupt_ratio: float,
    normalized_acceleration: float,
    spike_ratio: float,
    collateral: float,
) -> dict:
    return {
        "video_id": video_id,
        "motion_coverage": {
            "regions_with_detected_motion": coverage,
            "coverage_ratio": round(coverage / 7, 8),
        },
        "requested_union_smoothness": {
            "motion_energy_mae_rgb": {
                "spike_count": int(spike_ratio * 100),
                "spike_ratio": spike_ratio,
            },
            "acceleration_proxy_mae_rgb": {
                "abrupt_transition_count": int(abrupt_ratio * 100),
                "abrupt_transition_ratio": abrupt_ratio,
                "normalized_p95_by_motion_p95": normalized_acceleration,
            },
        },
        "collateral_activity": {
            "max_changed_pixel_ratio_from_first": collateral,
        },
    }


class Case21SmoothAnalyzerTest(unittest.TestCase):
    def test_linear_motion_has_full_coverage_without_temporal_spikes(self) -> None:
        size = 64
        frames = linear_frames(size)

        result = smooth.analyze_decoded_frames(
            metadata(),
            frames,
            size=size,
            coverage_sample_count=7,
        )

        self.assertEqual(result["analysis_status"], "measured")
        self.assertEqual(result["frame_analysis"]["decoded_frame_count"], 12)
        self.assertEqual(
            result["motion_coverage"]["regions_with_detected_motion"], 7
        )
        self.assertEqual(result["motion_coverage"]["missing_motion_regions"], [])
        temporal = result["requested_union_smoothness"]
        self.assertEqual(temporal["motion_energy_mae_rgb"]["spike_count"], 0)
        self.assertEqual(
            temporal["acceleration_proxy_mae_rgb"]["abrupt_transition_count"],
            0,
        )
        self.assertEqual(
            temporal["acceleration_proxy_mae_rgb"]["p95"],
            0.0,
        )
        self.assertEqual(
            result["collateral_activity"]["max_changed_pixel_ratio_from_first"],
            0.0,
        )
        self.assertTrue(all("fidelity_status" not in region for region in result["regions"]))
        battery = next(
            region for region in result["regions"] if region["region_id"] == "battery"
        )
        self.assertEqual(
            battery["expected_motion"],
            "monotonic fill through yellow to green, staying green",
        )

    def test_spike_and_second_difference_detect_abrupt_motion(self) -> None:
        result = smooth.analyze_decoded_frames(
            metadata(),
            jerky_frames(),
            size=64,
            coverage_sample_count=7,
        )

        temporal = result["requested_union_smoothness"]
        self.assertGreater(temporal["motion_energy_mae_rgb"]["spike_count"], 0)
        self.assertGreater(
            temporal["acceleration_proxy_mae_rgb"]["abrupt_transition_count"],
            0,
        )
        self.assertIn(6, temporal["motion_energy_mae_rgb"]["spike_frame_indices"])
        self.assertGreater(
            temporal["acceleration_proxy_mae_rgb"][
                "normalized_p95_by_motion_p95"
            ],
            0,
        )

    def test_missing_regions_and_collateral_are_reported_without_acceptance(self) -> None:
        size = 64
        region_offsets, outside_offsets = loop.build_region_offsets(size)
        frames = []
        for index in range(12):
            frame = solid_frame(size)
            set_offsets(frame, region_offsets["battery"], 80 + index * 8)
            if index == 6:
                set_offsets(frame, outside_offsets[: len(outside_offsets) // 4], 200)
            frames.append(bytes(frame))

        result = smooth.analyze_decoded_frames(
            metadata(),
            frames,
            size=size,
            coverage_sample_count=7,
        )

        self.assertEqual(
            result["motion_coverage"]["regions_with_detected_motion"], 1
        )
        self.assertEqual(
            result["motion_coverage"]["missing_motion_regions"],
            [
                "ovaries",
                "progesterone_formula",
                "antique_balance",
                "bathroom_scale",
                "water_drops",
                "irritability_lines",
            ],
        )
        self.assertGreater(
            result["collateral_activity"]["max_changed_pixel_ratio_from_first"],
            0.20,
        )
        serialized = json.dumps(result)
        self.assertNotIn("fidelity_status", serialized)
        self.assertNotIn("seam_status", serialized)

    def test_analyze_video_binds_all_frames_media_and_digest(self) -> None:
        frames = linear_frames()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("videos/variant.mp4")
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fixture")
            with (
                mock.patch.object(smooth, "probe_video", return_value=metadata()),
                mock.patch.object(
                    smooth,
                    "extract_all_normalized_frames",
                    return_value=frames,
                ),
            ):
                result = smooth.analyze_video(
                    smooth.VideoSpec("variant-a", relative),
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    size=64,
                    coverage_sample_count=7,
                    root=root,
                )

        self.assertEqual(result["video_id"], "variant-a")
        self.assertEqual(result["path"], "videos/variant.mp4")
        self.assertEqual(
            result["sha256"],
            "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d",
        )
        self.assertEqual(result["media"]["frame_rate"], "30")
        self.assertEqual(result["frame_analysis"]["decoded_frame_count"], 12)
        self.assertNotIn("proxy_rank", result)

    def test_ranking_prioritizes_coverage_then_smoothness_proxies(self) -> None:
        videos = [
            ranked_video(
                "less-coverage",
                coverage=6,
                abrupt_ratio=0.0,
                normalized_acceleration=0.1,
                spike_ratio=0.0,
                collateral=0.0,
            ),
            ranked_video(
                "smoothest-full",
                coverage=7,
                abrupt_ratio=0.01,
                normalized_acceleration=0.5,
                spike_ratio=0.02,
                collateral=0.01,
            ),
            ranked_video(
                "jerkier-full",
                coverage=7,
                abrupt_ratio=0.05,
                normalized_acceleration=0.2,
                spike_ratio=0.0,
                collateral=0.0,
            ),
        ]

        result = smooth.ranking_document(videos)

        self.assertEqual(
            [entry["video_id"] for entry in result["entries"]],
            ["smoothest-full", "jerkier-full", "less-coverage"],
        )
        self.assertEqual(
            set(result["entries"][0]),
            {
                "rank",
                "video_id",
                "regions_with_detected_motion",
                "coverage_ratio",
                "abrupt_transition_count",
                "abrupt_transition_ratio",
                "motion_energy_spike_count",
                "motion_energy_spike_ratio",
                "normalized_acceleration_p95",
                "collateral_max_changed_pixel_ratio_from_first",
            },
        )

    def test_report_schema_is_proxy_only_and_assigns_matching_ranks(self) -> None:
        analyzed = ranked_video(
            "a",
            coverage=7,
            abrupt_ratio=0.01,
            normalized_acceleration=0.3,
            spike_ratio=0.02,
            collateral=0.01,
        )
        with (
            mock.patch.object(smooth, "analyze_video", return_value=analyzed),
            mock.patch.object(smooth, "_tool_version", return_value="tool 1.0"),
        ):
            report = smooth.build_report(
                [smooth.VideoSpec("a", Path("a.mp4"))],
                ffmpeg="ffmpeg",
                ffprobe="ffprobe",
                size=96,
                coverage_sample_count=17,
            )

        self.assertEqual(report["schema_version"], smooth.SCHEMA_VERSION)
        self.assertEqual(
            report["analyzer"]["script"],
            "scripts/analyze_clipmaker_lite_case21_smooth.py",
        )
        self.assertEqual(report["video_count"], 1)
        self.assertEqual(report["videos"][0]["proxy_rank"], 1)
        self.assertEqual(len(report["method"]["requested_regions"]), 7)
        serialized = json.dumps(report)
        self.assertNotIn("seam_status", serialized)
        self.assertNotIn("fidelity_status", serialized)
        self.assertNotIn("semantic_status", serialized)

    def test_extract_all_frames_fails_on_count_mismatch(self) -> None:
        frame_bytes = 64 * 64 * 3
        with mock.patch.object(smooth, "_run", return_value=b"\x00" * (frame_bytes * 3)):
            with self.assertRaisesRegex(smooth.SmoothAnalysisError, "Expected 4"):
                smooth.extract_all_normalized_frames(
                    Path("video.mp4"),
                    ffmpeg="ffmpeg",
                    size=64,
                    expected_frame_count=4,
                )

    def test_cli_paths_fail_closed_and_defaults_are_workspace_relative(self) -> None:
        spec = smooth.parse_video_spec("variant-a=videos/a.mp4")
        self.assertEqual(spec, smooth.VideoSpec("variant-a", Path("videos/a.mp4")))
        for value in (
            "missing-equals.mp4",
            "Bad ID=videos/a.mp4",
            "a=../videos/a.mp4",
            "a=/tmp/a.mp4",
            "a=videos/a.mov",
        ):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    smooth.parse_video_spec(value)
        self.assertEqual(len(smooth.DEFAULT_VIDEOS), 5)
        self.assertEqual(
            smooth.DEFAULT_VIDEO_SHA256["staggered-ease-retry1"],
            "a5a8bcf4f1ea388ef7a8117d98509662c5ed2c251fc97e7ff7e6365a88360572",
        )
        self.assertTrue(
            all(
                not item.path.is_absolute() and item.path.suffix == ".mp4"
                for item in smooth.DEFAULT_VIDEOS
            )
        )

    def test_default_video_digest_is_fail_closed(self) -> None:
        spec = smooth.DEFAULT_VIDEOS[0]
        smooth.verify_default_video_digest(
            spec,
            smooth.DEFAULT_VIDEO_SHA256[spec.video_id],
        )
        with self.assertRaisesRegex(
            smooth.SmoothAnalysisError,
            "Immutable default video digest changed",
        ):
            smooth.verify_default_video_digest(spec, "0" * 64)
        custom = smooth.VideoSpec(spec.video_id, Path("custom/video.mp4"))
        smooth.verify_default_video_digest(custom, "0" * 64)


if __name__ == "__main__":
    unittest.main()
