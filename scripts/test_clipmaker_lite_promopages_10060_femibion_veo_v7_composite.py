import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_promopages_10060_femibion_veo_v7_composite as composite


class FemibionVeoV7CompositeTest(unittest.TestCase):
    def test_immutable_receipt_and_media_validate(self) -> None:
        receipt = composite.validate_composite(composite.ROOT)

        self.assertEqual(
            receipt["receipt_role"],
            "clipmaker-lite-deterministic-video-composite",
        )
        self.assertEqual(
            receipt["logical_key"],
            {
                "article_slug": "07-femibion-gotovites-k-beremennosti",
                "image_id": "06",
                "model_id": "google/veo-3.1-lite",
            },
        )
        self.assertFalse(receipt["classification"]["provider_output"])
        self.assertTrue(receipt["classification"]["derived_from_provider_output"])
        self.assertFalse(receipt["classification"]["new_provider_submission"])
        self.assertEqual(receipt["output"]["sha256"], composite.COMPOSITE_SHA256)
        self.assertEqual(receipt["output"]["bytes"], composite.COMPOSITE_BYTES)
        self.assertTrue(receipt["output"]["mp4_atoms"]["faststart"])
        self.assertEqual(receipt["output"]["media"]["pixel_format"], "yuv420p")
        self.assertEqual(receipt["output"]["media"]["frames"], 96)
        self.assertFalse(receipt["output"]["media"]["has_audio"])

    def test_provider_and_lite_provenance_are_pinned(self) -> None:
        receipt = composite.receipt_document()
        raw = receipt["inputs"]["raw_v7_provider_video"]
        planning = receipt["inputs"]["verified_lite_planning"]

        self.assertEqual(raw["provider_job_id"], "c4pO6Fw8YaEz0vPon3wH")
        self.assertEqual(raw["request_sha256"], composite.V7_REQUEST_SHA256)
        self.assertEqual(raw["sha256"], composite.RAW_VIDEO_SHA256)
        self.assertEqual(planning["result_sha256"], composite.PLANNING_RESULT_SHA256)
        self.assertTrue(planning["provenance"]["verified"])
        self.assertEqual(planning["provenance"]["contract_version"], "2.0.8")
        self.assertEqual(planning["provenance"]["agent_id"], "clipmaker-lite")
        self.assertEqual(planning["provenance"]["models"], ["google/veo-3.1-lite"])

    def test_recipe_geometry_color_range_and_encoder_are_frozen(self) -> None:
        receipt = composite.receipt_document()
        derivation = receipt["derivation"]

        self.assertEqual(
            derivation["patch"]["scale"],
            {"width": 800, "height": 450, "flags": "lanczos"},
        )
        self.assertEqual(
            derivation["alpha_mask"]["drawbox"],
            {
                "x": 55,
                "y": 150,
                "width": 300,
                "height": 230,
                "color": "0xD0D0D0",
                "mode": "fill",
            },
        )
        self.assertEqual(derivation["alpha_mask"]["gaussian_blur_sigma"], 32)
        self.assertEqual(derivation["overlay"], {"x": 1120, "y": 250, "format": "auto"})
        self.assertIn("scale=in_range=pc:out_range=tv", composite.FILTERGRAPH)
        self.assertIn("format=yuv420p,setparams=range=tv[out]", composite.FILTERGRAPH)
        self.assertEqual(
            derivation["encoder"],
            {
                "codec": "libx264",
                "preset": "slow",
                "crf": 18,
                "fps": 24,
                "duration_seconds": 4,
                "audio": False,
                "movflags": "+faststart",
            },
        )
        self.assertEqual(
            derivation["ffmpeg_arguments"],
            composite.ffmpeg_arguments("<output>"),
        )

    def test_reproduce_is_byte_identical_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "06.mp4"
            result = composite.reproduce(output, composite.ROOT)

            self.assertEqual(result["sha256"], composite.COMPOSITE_SHA256)
            self.assertEqual(result["bytes"], composite.COMPOSITE_BYTES)
            self.assertEqual(composite.sha256_file(output), composite.COMPOSITE_SHA256)
            self.assertEqual(output.stat().st_size, composite.COMPOSITE_BYTES)
            with self.assertRaisesRegex(composite.CompositeError, "Refusing to overwrite"):
                composite.reproduce(output, composite.ROOT)

    def test_input_digest_tamper_fails_closed(self) -> None:
        real_sha256 = composite.sha256_file

        def tampered(path: Path) -> str:
            if path == composite.ROOT / composite.BASE_V4_REL:
                return "0" * 64
            return real_sha256(path)

        with mock.patch.object(composite, "sha256_file", side_effect=tampered):
            with self.assertRaisesRegex(composite.CompositeError, "digest changed"):
                composite.validate_inputs(composite.ROOT)


if __name__ == "__main__":
    unittest.main()
