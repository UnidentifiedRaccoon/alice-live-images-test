#!/usr/bin/env python3
"""Build the immutable final Femibion two-output recovery selection.

This is a local evidence compositor, not a generation coordinator.  It reads
the frozen original/retry receipts, all eight paid V1..V7 recovery attempts,
the verified V7 deterministic-composite receipt, and the accepted V1 08/05
provider MP4.  It never calls a provider, uploads media, or edits the canonical
PROMOPAGES-10060 manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
MODEL_ID = "google/veo-3.1-lite"
SELECTION_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v7-"
    "all-attempts-selection"
)
SELECTION_ROOT_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-femibion-veo-recovery-20260810-v7"
)
SELECTION_MANIFEST_REL = SELECTION_ROOT_REL / "all-attempts-selection-manifest.json"
COMPOSITE_RECEIPT_REL = SELECTION_ROOT_REL / (
    "composite/videos/07-femibion-gotovites-k-beremennosti/"
    "veo-3.1-lite/06.receipt.json"
)
COMPOSITE_VIDEO_REL = SELECTION_ROOT_REL / (
    "composite/videos/07-femibion-gotovites-k-beremennosti/"
    "veo-3.1-lite/06.mp4"
)
COMPOSITE_VIDEO_SHA256 = (
    "d058fe8556e2f3badaa436745b1aa6e30ff0e726ef1648134225508e5917e13c"
)
COMPOSITE_VIDEO_BYTES = 552_368
COMPOSITE_RECEIPT_SHA256 = (
    "80e90a4cf753be47d5ddb5e36874e321991ffa50f4e041b9807725614a2e09e4"
)

ARTICLE_07 = "07-femibion-gotovites-k-beremennosti"
ARTICLE_08 = "08-femibion-grudnoe-vskarmlivanie"
SAMPLE_07 = f"{ARTICLE_07}-06"
SAMPLE_08 = f"{ARTICLE_08}-05"
CANONICAL_SOURCE_07 = (
    "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
    "07-femibion-gotovites-k-beremennosti/06.jpeg"
)
CANONICAL_SOURCE_08 = (
    "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
    "08-femibion-grudnoe-vskarmlivanie/05.jpeg"
)
ORIGINAL_SUPERSEDES_07 = pipeline.FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[
    (ARTICLE_07, "06", MODEL_ID)
]
ORIGINAL_SUPERSEDES_08 = pipeline.FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[
    (ARTICLE_08, "05", MODEL_ID)
]

FILTER_MARKER = (
    "Video generation completed with no output (content may have been filtered)"
)
CURRENT_CONTRACT_VERSION = "2.0.8"


class SelectionError(RuntimeError):
    """A fail-closed final-selection evidence error."""


@dataclass(frozen=True)
class AttemptSpec:
    iteration: int
    image_id: str
    article_slug: str
    planning_run_id: str
    source_path: str
    source_sha256: str
    context_sha256: str
    result_sha256: str
    provider_job_id: str
    request_sha256: str
    generation_sha256: str
    prompt_sha256: str
    run_sha256: str
    expected_status: str

    @property
    def recovery_id(self) -> str:
        return (
            "promopages-10060-femibion-veo-recovery-20260810-"
            f"v{self.iteration}"
        )

    @property
    def provider_run_id(self) -> str:
        sample_id = f"{self.article_slug}-{self.image_id}"
        return f"{self.recovery_id}-provider-{sample_id}-veo-3-1-lite"

    @property
    def root_rel(self) -> Path:
        return Path("clipmaker-lite-test/runs") / self.recovery_id

    @property
    def generation_rel(self) -> Path:
        return self.root_rel / "generation-manifest.json"

    @property
    def prompt_rel(self) -> Path:
        return self.root_rel / (
            f"videos/{self.article_slug}/veo-3.1-lite/{self.image_id}.prompt.json"
        )

    @property
    def run_rel(self) -> Path:
        return self.root_rel / (
            f"videos/{self.article_slug}/veo-3.1-lite/{self.image_id}.run.json"
        )

    @property
    def result_rel(self) -> Path:
        return pipeline.ARTIFACT_NAMESPACE / self.planning_run_id / "result.json"


ATTEMPTS = (
    AttemptSpec(
        1,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v1-"
        "07-femibion-gotovites-k-beremennosti-06",
        CANONICAL_SOURCE_07,
        "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12",
        "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c",
        "191d1c07e35b8421e862d807402d0da6b17e17e2cba3d9bc6c2f750640525a1e",
        "SwdH1eVdnIzgLHeXaTIg",
        "d80e38498bd48c2318efda51a5335e2a5fd51f0bbf6f2d418a2c594f873fb6e1",
        "096d1f16ee8bb0f550c356ed32f6edc6e7f779edfabb54e236042d9635b44dd1",
        "e46bad806f4d9811967702e23862bd8dbfc033ec3171b3b56ab65348a6d1e7dc",
        "2946444b1ca4cbd603e728c9de4df4349c1254cea4243e896fdc20e884346da7",
        "provider-failed",
    ),
    AttemptSpec(
        1,
        "05",
        ARTICLE_08,
        "promopages-10060-femibion-veo-recovery-20260810-v1-"
        "08-femibion-grudnoe-vskarmlivanie-05",
        CANONICAL_SOURCE_08,
        "e29ddb18cc961dff4595222d7a18f030a457e910a0b477cdc897adf7426af06a",
        "33548f66e701ed12073d2cd1b3471ac7ae8fe34a3ae5b1587ba9092d27fef6ce",
        "0c7013982e35d54a66343545afd16b52ad8a41e5980851063b0639e2ac6f666f",
        "8FDZycf6v5wTtzPmNYwF",
        "5c8113b87eac0f2a4d849f8ab279068dac5f9627b2adcc9b7ce72e7e0d2129b6",
        "096d1f16ee8bb0f550c356ed32f6edc6e7f779edfabb54e236042d9635b44dd1",
        "635e3485693a7882525e383105991d04fe6ac47c83b9ec4eefdaea73ffef1dc2",
        "969dcb6420437ce76abd1dce477cf3a89756a7dedb78cf83aaf0db52b79183b6",
        "succeeded",
    ),
    AttemptSpec(
        2,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v2-"
        "07-femibion-gotovites-k-beremennosti-06",
        CANONICAL_SOURCE_07,
        "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12",
        "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c",
        "47a3579def0b40bf845609604e342fee3f5bf49d6cf8b223ed4e72590a3ff944",
        "axgyuIecP85mwRLo7d13",
        "3e82fe9aa019bea8225c28f0e8fbaef1a621d2e80fd4d60ed88eae9e268115fc",
        "161afc67e957dcd433eab519d2bf369c0aa4fa703360fe380b7cd2b37b6192b8",
        "ad358837f0b256d41bcd08b35d7c0d31092b4a6f3a2f8c89441a489bf94547cf",
        "f796052a0573350ee9611d0f4d59375d201411d73b94440d99352cb3ebb1acde",
        "provider-failed",
    ),
    AttemptSpec(
        3,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v2-"
        "07-femibion-gotovites-k-beremennosti-06",
        CANONICAL_SOURCE_07,
        "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12",
        "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c",
        "47a3579def0b40bf845609604e342fee3f5bf49d6cf8b223ed4e72590a3ff944",
        "5UTHzBnYIH5XkaGt7kJj",
        "0fc4588d29046e5a6d40a7c74e0711dea4f8ce1e8b801f7e64575eedb3cc4b2a",
        "33d36a5cf40008b250bf9f96673ce8f39e95f1b8b7726fa13b4769597fd4afab",
        "1c5783aef5bdc2ebf5e692b58366b7155006bc51b711d87bc58d4cb9c3fdd4a3",
        "2f60a081e3779214de61f6b8ef3fd1b14f6e93eae5f1029c06601fe1970de247",
        "provider-failed",
    ),
    AttemptSpec(
        4,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v4-"
        "07-femibion-gotovites-k-beremennosti-06",
        "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v4/articles/"
        "07-femibion-gotovites-k-beremennosti/06.jpeg",
        "f3eac13ca2c71c7cec3a1a860c701caea68728a3f9dc9e77c1d05b2455143ce9",
        "d1c65a16f8d24e2bde20704f82376b4167211fa8d62fccd19ed75f2def0105ca",
        "bead524d13e018c0905be09440226c5367d6ae0c40122a19dc270d3b13b49d35",
        "ph4kAnk1VL2vETZwBiSo",
        "e469d1aef96cb0a1fd96506a8af4e558590934049b5c4ad4b7ee5d5a4594568d",
        "069c04ecc7ac488bd421384bb66924f02a4d81841bd735b62448c3f8a188fad4",
        "904ec62f1c11e24e9abf1b97f0e90271ab284e58434c81534b35fb6f3ce14f87",
        "cccbbf73288ee1379906bd46e9d782ef456c0ee9e392712e66e2f7b8571ecffc",
        "provider-failed",
    ),
    AttemptSpec(
        5,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v5b-"
        "07-femibion-gotovites-k-beremennosti-06",
        CANONICAL_SOURCE_07,
        "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12",
        "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c",
        "95022eb555ae4d6474471c682b36b1c50f6cc44664f49a142ef673497d6697eb",
        "c2wwhmzoBtXaxBRuDKl3",
        "f7c89bf386a5d160d4731fb4a1372c2817797f24ea708dd7988bd2dbfe889031",
        "2f062d6e425890d4151e0dcd34f1fa56f5e09b8c221c6da4d7c87971cdf50088",
        "7c99494cd2d6b0b72efc85cfebe9ab921173c9ad449401f22010dd4eed64323a",
        "0cfd06f0e75f729ecb487f3b9e037c12284d08b4706cca4aa54bfab4722036ad",
        "provider-failed",
    ),
    AttemptSpec(
        6,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v6-"
        "07-femibion-gotovites-k-beremennosti-06",
        "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v6/articles/"
        "07-femibion-gotovites-k-beremennosti/06.jpeg",
        "74764f50e6a2b6c307817c2862df40c8ed50367aa9f5e191106f22772397bb88",
        "998f1567400275e9115b979e13550fb68901d06df030313ebf29c818e2e6a3a9",
        "95ae631ee8a365bc902270aa1ceb5d7958d99d2bc7e823493621beafb040c1a3",
        "rxIfCOzWeIJTt0yhb7wB",
        "b6bcc541ad18e332e1adbadf3e1df7d43b3bca45b0e4042f06bc4e0d1310b0d6",
        "ad55d6a7cf222f67f898b057456dba2df19fd934a12022ab8e71ffd8e64235ec",
        "a9c983375ca098418e4bdc6c549ce0306b9e26a04067dac94fa946b7d6313394",
        "05140dbae8cef3ce1d3d69690c10e656fe1ca74ed0584b3eec93ee53ad3bf5bb",
        "provider-failed",
    ),
    AttemptSpec(
        7,
        "06",
        ARTICLE_07,
        "promopages-10060-femibion-veo-recovery-20260810-v7-"
        "07-femibion-gotovites-k-beremennosti-06",
        "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v7/articles/"
        "07-femibion-gotovites-k-beremennosti/06.jpeg",
        "31672c5832458e9698f2a5710a159b10cbb99febf55c7f1b0906393f977cb88e",
        "3db3fbc0a8ad5d263fd445df6add5ad5343e9eaf67529aba787ebc6e096452f8",
        "73f878a18d9f063a4ed674efd6601c140ff5e406700f619bbc4acb065f75d1b0",
        "c4pO6Fw8YaEz0vPon3wH",
        "e6c5a3b9586df1f116846afcae103e9475de69883add0330e7a4804922daf522",
        "1c449be1e1438d181909db15ed571b51ccf0edc35cd0b942da68efeb04c779b6",
        "3bcac53a27768f16fd640ae79b6f6229ad8baea6e3a6170a234ec95cba70a208",
        "dff03db2df123899a9990f915b4eb993de47865a6e93e1d8a01eeeea94f636d7",
        "succeeded",
    ),
)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectionError(f"Cannot read JSON {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    try:
        return pipeline.sha256_file(path)
    except pipeline.PipelineError as exc:
        raise SelectionError(str(exc)) from exc


def _regular(root: Path, relative: Path, expected_sha256: str | None = None) -> Path:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise SelectionError(f"Missing or unsafe immutable evidence: {relative}")
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise SelectionError(f"Immutable evidence digest changed: {relative}")
    return path


def _safe_relative(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SelectionError(f"{label} is missing")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise SelectionError(f"{label} is unsafe: {value}")
    return Path(*parsed.parts)


def _planning_record(spec: AttemptSpec, root: Path) -> dict[str, Any]:
    result_path = _regular(root, spec.result_rel, spec.result_sha256)
    summary = pipeline.planning_provenance_summary(root, spec.planning_run_id)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != CURRENT_CONTRACT_VERSION
        or summary.get("models") != [MODEL_ID]
        or summary.get("result_path") != spec.result_rel.as_posix()
        or summary.get("source_image_sha256") != spec.source_sha256
        or summary.get("article_context_sha256") != spec.context_sha256
    ):
        raise SelectionError(
            f"Recovery Lite provenance differs: v{spec.iteration}/{spec.image_id}"
        )
    result = read_json(result_path)
    models = result.get("models") if isinstance(result, dict) else None
    if (
        result.get("job_id") != spec.planning_run_id
        or not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != MODEL_ID
    ):
        raise SelectionError(f"Recovery Lite result differs: {spec.planning_run_id}")
    return {
        "planning_run_id": spec.planning_run_id,
        "result_path": spec.result_rel.as_posix(),
        "result_sha256": spec.result_sha256,
        "provenance": summary,
    }


def _attempt_record(spec: AttemptSpec, root: Path) -> dict[str, Any]:
    generation_path = _regular(root, spec.generation_rel, spec.generation_sha256)
    prompt_path = _regular(root, spec.prompt_rel, spec.prompt_sha256)
    run_path = _regular(root, spec.run_rel, spec.run_sha256)
    generation = read_json(generation_path)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    matches = [
        output
        for output in outputs
        if isinstance(output, dict)
        and output.get("provider_run_id") == spec.provider_run_id
    ] if isinstance(outputs, list) else []
    prompt = read_json(prompt_path)
    run = read_json(run_path)
    source = prompt.get("source") if isinstance(prompt, dict) else None
    source_rel = _safe_relative(
        source.get("path") if isinstance(source, dict) else None,
        label=f"v{spec.iteration} source path",
    )
    source_path = _regular(root, source_rel, spec.source_sha256)
    try:
        source_format, actual_width, actual_height = (
            pipeline._encoded_image_dimensions(source_path.read_bytes())
        )
    except (OSError, pipeline.PipelineError) as exc:
        raise SelectionError(f"Cannot inspect recovery source: {source_rel}") from exc
    if (
        generation.get("ticket") != TICKET
        or generation.get("agent_id") != AGENT_ID
        or generation.get("batch_id") != f"{spec.recovery_id}-provider"
        or len(matches) != 1
        or prompt.get("provider_run_id") != spec.provider_run_id
        or prompt.get("lite_run_id") != spec.planning_run_id
        or prompt.get("model_id") != MODEL_ID
        or not isinstance(source, dict)
        or source.get("path") != spec.source_path
        or source.get("sha256") != spec.source_sha256
        or run.get("provider_run_id") != spec.provider_run_id
        or run.get("provider_job_id") != spec.provider_job_id
        or run.get("lite_run_id") != spec.planning_run_id
        or run.get("model_id") != MODEL_ID
        or run.get("status") != spec.expected_status
        or run.get("provider_may_be_active") is not False
        or run.get("request_sha256") != spec.request_sha256
    ):
        raise SelectionError(
            f"Recovery provider evidence differs: v{spec.iteration}/{spec.image_id}"
        )
    selected = matches[0]
    if (
        selected.get("sample_id") != f"{spec.article_slug}-{spec.image_id}"
        or selected.get("source_path") != spec.source_path
        or selected.get("model_id") != MODEL_ID
        or selected.get("recorded_status") != spec.expected_status
        or selected.get("prompt_path") != spec.prompt_rel.as_posix()
        or selected.get("run_path") != spec.run_rel.as_posix()
    ):
        raise SelectionError(
            f"Recovery generation projection differs: v{spec.iteration}/{spec.image_id}"
        )
    output_rel = _safe_relative(run.get("output_path"), label="provider output path")
    media = run.get("media")
    contract_check = run.get("contract_check")
    if spec.expected_status == "succeeded":
        output_path = _regular(root, output_rel)
        if (
            selected.get("status") != "succeeded"
            or selected.get("video_path") != output_rel.as_posix()
            or selected.get("media") != media
            or selected.get("contract_check") != contract_check
            or not isinstance(media, dict)
            or media.get("sha256") != sha256_file(output_path)
            or media.get("bytes") != output_path.stat().st_size
            or not isinstance(contract_check, dict)
            or contract_check.get("conforms") is not True
        ):
            raise SelectionError(
                f"Accepted provider media differs: v{spec.iteration}/{spec.image_id}"
            )
    elif (
        selected.get("status") != "provider-failed"
        or media is not None
        or contract_check is not None
        or (root / output_rel).exists()
        or FILTER_MARKER not in str(run.get("error"))
    ):
        raise SelectionError(
            f"Filtered provider evidence differs: v{spec.iteration}/{spec.image_id}"
        )
    planning = _planning_record(spec, root)
    return {
        "iteration": spec.iteration,
        "logical_key": {
            "article_slug": spec.article_slug,
            "image_id": spec.image_id,
            "model_id": MODEL_ID,
        },
        "provider_run_id": spec.provider_run_id,
        "provider_job_id": spec.provider_job_id,
        "status": (
            "succeeded" if spec.expected_status == "succeeded" else "provider-filtered"
        ),
        "recorded_status": spec.expected_status,
        "request_sha256": spec.request_sha256,
        "source": {
            "path": source_rel.as_posix(),
            "sha256": sha256_file(source_path),
            "recorded_dimensions": {
                "width": source.get("width"),
                "height": source.get("height"),
            },
            "actual_local_dimensions": {
                "format": source_format,
                "width": actual_width,
                "height": actual_height,
            },
            "receipt_metadata_discrepancy": (
                source.get("width") != actual_width
                or source.get("height") != actual_height
            ),
        },
        "generation_manifest_path": spec.generation_rel.as_posix(),
        "generation_manifest_sha256": spec.generation_sha256,
        "prompt_path": spec.prompt_rel.as_posix(),
        "prompt_sha256": spec.prompt_sha256,
        "run_path": spec.run_rel.as_posix(),
        "run_sha256": spec.run_sha256,
        "video_path": output_rel.as_posix() if spec.expected_status == "succeeded" else None,
        "media": media,
        "contract_check": contract_check,
        "error": run.get("error"),
        "planning": planning,
    }


def _old_failed_attempts(root: Path) -> list[dict[str, Any]]:
    specifications = (
        {
            "article_slug": ARTICLE_07,
            "image_id": "06",
            "attempt": "primary",
            "provider_job_id": "Hfvx2OaGO9vsyrcs6AMf",
            "provider_run_id": (
                "promopages-10060-lite-all-images-20260805-v2-"
                "07-femibion-gotovites-k-beremennosti-06-veo-3-1-lite"
            ),
            "request_sha256": (
                "f7f0c0c20f702b1deb1b5ee3a8e28d2487c8c3988653792518b03a223afa7a01"
            ),
            "prompt": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/videos/"
                "07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"
            ),
            "prompt_sha256": (
                "2f28a4279c77fc93df39914fdb995441b370d210767a3a17276fda20a909a9a1"
            ),
            "run": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/videos/"
                "07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
            ),
            "run_sha256": (
                "9a4527b55d846de60f52d4a4cbf54f600c748919c7d75babcc2d2059d6861c3f"
            ),
        },
        {
            "article_slug": ARTICLE_07,
            "image_id": "06",
            "attempt": "terminal-retry-v1",
            "provider_job_id": "dqjE7PrI5frFAFW7Y2Aa",
            "provider_run_id": ORIGINAL_SUPERSEDES_07,
            "request_sha256": (
                "f7f0c0c20f702b1deb1b5ee3a8e28d2487c8c3988653792518b03a223afa7a01"
            ),
            "prompt": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/"
                "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/videos/"
                "veo-3.1-lite/06.prompt.json"
            ),
            "prompt_sha256": (
                "5d4438188907c6f45bcd4925709962b0f2a6e49ef5007a769145aa4c6035583d"
            ),
            "run": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/"
                "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/videos/"
                "veo-3.1-lite/06.run.json"
            ),
            "run_sha256": (
                "b4f6561f1bc0084c81ecd3c47c3c6158a1bc08f0049fa286875da091daa3bc8d"
            ),
        },
        {
            "article_slug": ARTICLE_08,
            "image_id": "05",
            "attempt": "primary",
            "provider_job_id": "6QIWOmo7PJgVMK4qECeg",
            "provider_run_id": (
                "promopages-10060-lite-all-images-20260805-v2-"
                "08-femibion-grudnoe-vskarmlivanie-05-veo-3-1-lite"
            ),
            "request_sha256": (
                "30df775a691ff4814b67252784630c3d241cdc22a083b8ac297dd85415d93955"
            ),
            "prompt": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/videos/"
                "08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.prompt.json"
            ),
            "prompt_sha256": (
                "2bb8bcf4182d1926b4877649d67953573d8bcf0e2cd008b7c83fe447469add92"
            ),
            "run": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/videos/"
                "08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.run.json"
            ),
            "run_sha256": (
                "c39046d9f6d452c9bd735bcb49ed7c337028eee9f0215bf24f39bcda16aa340d"
            ),
        },
        {
            "article_slug": ARTICLE_08,
            "image_id": "05",
            "attempt": "terminal-retry-v1",
            "provider_job_id": "tpePxKfkVlYvoc1nVeS0",
            "provider_run_id": ORIGINAL_SUPERSEDES_08,
            "request_sha256": (
                "30df775a691ff4814b67252784630c3d241cdc22a083b8ac297dd85415d93955"
            ),
            "prompt": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/"
                "terminal-provider-retries-v1/0cc5261325a58f1785ee/videos/"
                "veo-3.1-lite/05.prompt.json"
            ),
            "prompt_sha256": (
                "fc8684b051d2b92d98cebf3323e1f361c08d1bd2fd714ca1b722894ea15efd95"
            ),
            "run": Path(
                "clipmaker-lite-test/runs/"
                "promopages-10060-lite-all-images-20260805-v2/"
                "terminal-provider-retries-v1/0cc5261325a58f1785ee/videos/"
                "veo-3.1-lite/05.run.json"
            ),
            "run_sha256": (
                "60b797369bc0f64c686ecf310b575cb086a99e2f46715b77daa0e71127c99b4e"
            ),
        },
    )
    records: list[dict[str, Any]] = []
    for spec in specifications:
        prompt_path = _regular(root, spec["prompt"], spec["prompt_sha256"])
        run_path = _regular(root, spec["run"], spec["run_sha256"])
        run = read_json(run_path)
        if (
            run.get("provider_run_id") != spec["provider_run_id"]
            or run.get("provider_job_id") != spec["provider_job_id"]
            or run.get("request_sha256") != spec["request_sha256"]
            or run.get("status") != "provider-failed"
            or run.get("provider_may_be_active") is not False
            or run.get("media") is not None
            or FILTER_MARKER not in str(run.get("error"))
        ):
            raise SelectionError(f"Old filtered evidence differs: {spec['attempt']}")
        records.append(
            {
                "logical_key": {
                    "article_slug": spec["article_slug"],
                    "image_id": spec["image_id"],
                    "model_id": MODEL_ID,
                },
                "attempt": spec["attempt"],
                "provider_run_id": spec["provider_run_id"],
                "provider_job_id": spec["provider_job_id"],
                "status": "provider-filtered",
                "recorded_status": "provider-failed",
                "request_sha256": spec["request_sha256"],
                "prompt_path": spec["prompt"].as_posix(),
                "prompt_sha256": sha256_file(prompt_path),
                "run_path": spec["run"].as_posix(),
                "run_sha256": sha256_file(run_path),
                "error": run.get("error"),
                "provider_may_be_active": False,
            }
        )
    return records


def _composite_document(root: Path) -> dict[str, Any]:
    try:
        from scripts import (  # noqa: PLC0415
            clipmaker_lite_promopages_10060_femibion_veo_v7_composite as composite,
        )
    except ImportError as exc:
        raise SelectionError("V7 composite validator is not available") from exc
    try:
        document = composite.validate_composite(root=root)
    except Exception as exc:  # validator owns its precise fail-closed errors
        raise SelectionError(f"V7 composite validation failed: {exc}") from exc
    receipt_path = _regular(
        root,
        COMPOSITE_RECEIPT_REL,
        COMPOSITE_RECEIPT_SHA256,
    )
    video_path = _regular(root, COMPOSITE_VIDEO_REL, COMPOSITE_VIDEO_SHA256)
    output = document.get("output") if isinstance(document, dict) else None
    media = output.get("media") if isinstance(output, dict) else None
    derivation = document.get("derivation") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or not isinstance(output, dict)
        or document.get("receipt_role")
        != "clipmaker-lite-deterministic-video-composite"
        or document.get("logical_key")
        != {
            "article_slug": ARTICLE_07,
            "image_id": "06",
            "model_id": MODEL_ID,
        }
        or output.get("path") != COMPOSITE_VIDEO_REL.as_posix()
        or output.get("sha256") != COMPOSITE_VIDEO_SHA256
        or output.get("bytes") != COMPOSITE_VIDEO_BYTES
        or not isinstance(media, dict)
        or media.get("sha256") != COMPOSITE_VIDEO_SHA256
        or media.get("bytes") != COMPOSITE_VIDEO_BYTES
        or video_path.stat().st_size != COMPOSITE_VIDEO_BYTES
        or not isinstance(derivation, dict)
        or derivation.get("kind") != "deterministic-composite"
        or derivation.get("provider_output") is not False
        or not isinstance(document.get("classification"), dict)
        or document["classification"].get("provider_output") is not False
        or document["classification"].get("derived_from_provider_output") is not True
        or document["classification"].get("eligible_as_derived_demo_media") is not True
    ):
        raise SelectionError("V7 composite receipt/output identity differs")
    return {
        "path": COMPOSITE_RECEIPT_REL.as_posix(),
        "sha256": sha256_file(receipt_path),
        "document": document,
    }


def _selected_output(
    attempt: dict[str, Any],
    *,
    canonical_source_path: str,
    supersedes_for_demo: str,
    selected_attempt: str,
    composite: dict[str, Any] | None,
    failed_chain: list[dict[str, Any]],
    root: Path,
) -> dict[str, Any]:
    planning = attempt["planning"]
    result = read_json(root / planning["result_path"])
    model = result["models"][0]
    if composite is None:
        video_path = attempt["video_path"]
        media = attempt["media"]
        contract_check = attempt["contract_check"]
    else:
        composite_output = composite["document"]["output"]
        video_path = composite_output["path"]
        media = composite_output["media"]
        # The receipt independently proves the final composite's exact media
        # invariants.  Re-evaluate the same locked runtime contract that the
        # accepted raw V7 receipt used instead of pretending the deterministic
        # derivative was another provider output.
        contract_check = attempt["contract_check"]
        if (
            not isinstance(media, dict)
            or media.get("duration_seconds") != 4.0
            or media.get("width") != 1920
            or media.get("height") != 1080
            or media.get("has_audio") is not False
            or media.get("codec") != "h264"
            or media.get("pixel_format") != "yuv420p"
        ):
            raise SelectionError("Composite media violates the locked Veo runtime")
    if not isinstance(contract_check, dict) or contract_check.get("conforms") is not True:
        raise SelectionError("Selected recovery output does not conform")
    return {
        "article_slug": attempt["logical_key"]["article_slug"],
        "image_id": attempt["logical_key"]["image_id"],
        "source_path": canonical_source_path,
        "sample_id": (
            f"{attempt['logical_key']['article_slug']}-"
            f"{attempt['logical_key']['image_id']}"
        ),
        "lite_run_id": planning["planning_run_id"],
        "provider_run_id": attempt["provider_run_id"],
        "provider_job_id": attempt["provider_job_id"],
        "model_id": MODEL_ID,
        "scene_plan": model.get("scene_plan"),
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "status": "succeeded",
        "recorded_status": "succeeded",
        "provider_may_be_active": False,
        "prompt_path": attempt["prompt_path"],
        "run_path": attempt["run_path"],
        "video_path": video_path,
        "media": media,
        "contract_check": contract_check,
        "error": None,
        "selected_attempt": selected_attempt,
        "supersedes_for_demo": supersedes_for_demo,
        "recovery": {
            "selection_id": SELECTION_ID,
            "source_iteration": attempt["iteration"],
            "supersedes_for_demo": supersedes_for_demo,
            "selected_provider_attempt": attempt,
            "composite_receipt": composite,
            "failed_attempt_chain": failed_chain,
            "automatic_retry": False,
            "fallback": False,
        },
    }


def accounting_document() -> dict[str, Any]:
    return {
        "currency": "USD",
        "baseline_paid_submissions": 281,
        "baseline_reserved_usd": 98.35,
        "recovery_paid_submissions": 8,
        "recovery_submissions_by_iteration": {
            "v1": 2,
            "v2": 1,
            "v3": 1,
            "v4": 1,
            "v5": 1,
            "v6": 1,
            "v7": 1,
        },
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 2.8,
        "aggregate_paid_submissions": 289,
        "aggregate_reserved_usd": 101.15,
        "operator_budget_cap_usd": 101.15,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 3.6,
        "authorized_additional_budget_usd": 5.0,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }


def selection_document(
    root: Path = ROOT,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    route = pipeline._femibion_recovery_route_snapshot(root)
    contract = pipeline._femibion_recovery_contract_snapshot(root)
    old_failed = _old_failed_attempts(root)
    attempts = [_attempt_record(spec, root) for spec in ATTEMPTS]
    if len(attempts) != 8:
        raise SelectionError("Recovery paid-attempt count changed")
    discrepancies = [
        record
        for record in attempts
        if record["source"]["receipt_metadata_discrepancy"]
    ]
    if (
        len(discrepancies) != 1
        or discrepancies[0]["iteration"] != 5
        or discrepancies[0]["logical_key"]
        != {
            "article_slug": ARTICLE_07,
            "image_id": "06",
            "model_id": MODEL_ID,
        }
        or discrepancies[0]["source"]["recorded_dimensions"]
        != {"width": 1920, "height": 1080}
        or discrepancies[0]["source"]["actual_local_dimensions"]
        != {"format": "JPEG", "width": 2400, "height": 1600}
    ):
        raise SelectionError(
            "Known V5 source receipt metadata discrepancy changed"
        )
    attempt_07 = [record for record in attempts if record["logical_key"]["image_id"] == "06"]
    attempt_08 = [record for record in attempts if record["logical_key"]["image_id"] == "05"]
    failed_recoveries = [record for record in attempt_07 if record["status"] == "provider-filtered"]
    accepted_07 = [record for record in attempt_07 if record["status"] == "succeeded"]
    accepted_08 = [record for record in attempt_08 if record["status"] == "succeeded"]
    if (
        len(failed_recoveries) != 6
        or len(accepted_07) != 1
        or accepted_07[0]["iteration"] != 7
        or len(accepted_08) != 1
        or accepted_08[0]["iteration"] != 1
    ):
        raise SelectionError("Final accepted/failed attempt selection changed")
    old_failed_07 = [
        record
        for record in old_failed
        if record["logical_key"]["article_slug"] == ARTICLE_07
    ]
    old_failed_08 = [
        record
        for record in old_failed
        if record["logical_key"]["article_slug"] == ARTICLE_08
    ]
    if len(old_failed_07) != 2 or len(old_failed_08) != 2:
        raise SelectionError("Original/retry-v1 failure chain is incomplete")
    failed_chain = old_failed + failed_recoveries
    composite = _composite_document(root)
    selected_07 = _selected_output(
        accepted_07[0],
        canonical_source_path=CANONICAL_SOURCE_07,
        supersedes_for_demo=ORIGINAL_SUPERSEDES_07,
        selected_attempt="content-filter-recovery-v7-composite",
        composite=composite,
        failed_chain=old_failed_07 + failed_recoveries,
        root=root,
    )
    selected_08 = _selected_output(
        accepted_08[0],
        canonical_source_path=CANONICAL_SOURCE_08,
        supersedes_for_demo=ORIGINAL_SUPERSEDES_08,
        selected_attempt="content-filter-recovery-v1",
        composite=None,
        failed_chain=old_failed_08,
        root=root,
    )
    outputs = [selected_07, selected_08]
    return {
        "schema_version": 1,
        "manifest_role": "promopages-10060-femibion-veo-all-attempts-selection",
        "ticket": TICKET,
        "selection_id": SELECTION_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or pipeline.transport.utc_now(),
        "expected_outputs": 2,
        "accepted_output_count": 2,
        "ready_for_merge": True,
        "summary": {"succeeded": 2, "provider-filtered": 0},
        "route": route,
        "contract": contract,
        "accounting": accounting_document(),
        "attempt_evidence": attempts,
        "failed_attempt_chain": failed_chain,
        "composite_receipt": composite,
        "selection": [
            {
                "logical_key": output["recovery"]["selected_provider_attempt"]["logical_key"],
                "source_iteration": output["recovery"]["source_iteration"],
                "provider_run_id": output["provider_run_id"],
                "provider_job_id": output["provider_job_id"],
                "video_path": output["video_path"],
                "supersedes_for_demo": output["supersedes_for_demo"],
            }
            for output in outputs
        ],
        "supersedes_for_demo": [
            {
                "logical_key": output["recovery"]["selected_provider_attempt"]["logical_key"],
                "old_provider_run_id": output["supersedes_for_demo"],
                "new_provider_run_id": output["provider_run_id"],
            }
            for output in outputs
        ],
        "planning": [
            output["recovery"]["selected_provider_attempt"]["planning"]
            for output in outputs
        ],
        "source_transformations": {
            "attempt_sources": [
                {
                    "iteration": record["iteration"],
                    "logical_key": record["logical_key"],
                    "source": record["source"],
                }
                for record in attempts
            ],
            "receipt_metadata_discrepancies": [
                {
                    "iteration": record["iteration"],
                    "logical_key": record["logical_key"],
                    "source": record["source"],
                }
                for record in discrepancies
            ],
            "final_composite": composite["document"]["derivation"],
        },
        "merge_contract": {
            "target_manifest": pipeline.FINAL_MANIFEST_REL.as_posix(),
            "logical_key": ["article_slug", "image_id", "model_id"],
            "replace_only_status": "provider-filtered",
            "replace_exactly": 2,
            "requires_ready_for_merge": True,
            "preserve_all_other_outputs": True,
            "all_or_nothing": True,
            "demo_selection_field": "supersedes_for_demo",
        },
        "outputs": outputs,
    }


def write_selection_manifest(root: Path = ROOT) -> dict[str, Any]:
    path = root / SELECTION_MANIFEST_REL
    if path.is_file() and not path.is_symlink():
        current = read_json(path)
        updated_at = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(updated_at, str) and updated_at:
            expected = selection_document(root, updated_at=updated_at)
            if current == expected:
                return current
            raise SelectionError(f"Immutable all-attempts selection changed: {path}")
    if path.exists():
        raise SelectionError(f"Unsafe all-attempts selection target: {path}")
    document = selection_document(root)
    pipeline.transport.atomic_write_json(path, document)
    return document


def validate_selection(root: Path = ROOT) -> dict[str, Any]:
    path = root / SELECTION_MANIFEST_REL
    if not path.is_file() or path.is_symlink():
        raise SelectionError(f"Missing all-attempts selection manifest: {path}")
    actual = read_json(path)
    updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
    if not isinstance(updated_at, str) or not updated_at:
        raise SelectionError("All-attempts selection updated_at is missing")
    expected = selection_document(root, updated_at=updated_at)
    if actual != expected:
        raise SelectionError("All-attempts selection differs from immutable evidence")
    if actual.get("ready_for_merge") is not True or actual.get("accepted_output_count") != 2:
        raise SelectionError("All-attempts selection is not ready")
    return actual


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("write")
    commands.add_parser("validate")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document = (
            write_selection_manifest(ROOT)
            if args.command == "write"
            else validate_selection(ROOT)
        )
    except (SelectionError, pipeline.PipelineError, OSError) as exc:
        print(f"error: {pipeline.transport.safe_error(exc)}", file=sys.stderr)
        return 1
    print(
        f"selection manifest: {SELECTION_MANIFEST_REL.as_posix()} "
        f"ready_for_merge={str(document['ready_for_merge']).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
