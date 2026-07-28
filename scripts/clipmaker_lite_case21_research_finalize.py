#!/usr/bin/env python3
"""Finalize the case-21 research sidecar without hiding fidelity failures.

This is a read-only verifier plus one local JSON write.  It does not call a
provider, discover a route, retry an entry, or fetch a URL.  The original seven
research MP4s remain unchanged and unaccepted.  When the separately budgeted
Wan 2.7 loop experiment is complete, its available MP4s and full attempt
history are exposed in a distinct top-level section with exact receipt binding.
The separately budgeted canonical first-frame smooth series is exposed as an
optional sibling only after all five attempts have exact review receipts; four
human-selected MP4s are published while the excluded attempt stays in history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_case21_loop_experiment as loop_experiment  # noqa: E402
from scripts import clipmaker_lite_case21_pipeline as case21  # noqa: E402
from scripts import clipmaker_lite_case21_smooth_experiment as smooth_experiment  # noqa: E402
from scripts import clipmaker_lite_case21_smooth_retry as smooth_retry  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
AGENT_ID = "clipmaker-lite"
FINAL_BATCH_ID = "promopages-9930-case21-failure-aware-20260727-v1"
FINAL_MANIFEST_PATH = Path("clipmaker-lite-test/case-21-manifest.json")
STAGE1_EXPERIMENT_ID = "promopages-9930-case21-prompt-research-20260727-v1"
STAGE2_EXPERIMENT_ID = "promopages-9930-case21-opacity-only-stage2-20260727-v1"
STAGE1_ROOT = Path("clipmaker-lite-test/experiments") / STAGE1_EXPERIMENT_ID
STAGE2_ROOT = Path("clipmaker-lite-test/experiments") / STAGE2_EXPERIMENT_ID
STAGE1_GENERATION_PATH = STAGE1_ROOT / "generation-manifest.json"
STAGE2_GENERATION_PATH = STAGE2_ROOT / "generation-manifest.json"
STAGE1_INVENTORY_PATH = STAGE1_ROOT / "inventory.json"
STAGE2_INVENTORY_PATH = STAGE2_ROOT / "inventory.json"
LOOP_REVIEW_PATH = loop_experiment.EXPERIMENT_ROOT / "loop-review.json"
SMOOTH_REVIEW_PATH = smooth_experiment.EXPERIMENT_ROOT / "smooth-review.json"

LOOP_INCOMPLETE_STATUSES = frozenset(
    {
        "missing",
        "pending",
        "dry-run",
        "preparing",
        "submitting",
        "submitted",
        "running",
        "submit-unknown",
        "stale",
    }
)
LOOP_AVAILABLE_STATUSES = frozenset({"succeeded", "verification-failed"})
LOOP_FRAME_TYPES = ("first_frame", "last_frame")
LOOP_REVIEW_SCHEMA_VERSION = "clipmaker-lite.case21-loop-review.v1"
LOOP_REGION_IDS = (
    "ovaries",
    "progesterone_formula",
    "antique_balance",
    "bathroom_scale",
    "water_drops",
    "irritability_lines",
    "battery",
)
SMOOTH_FRAME_TYPES = ("first_frame",)
SMOOTH_REVIEW_SCHEMA_VERSION = "clipmaker-lite.case21-smooth-review.v1"
SMOOTH_REGION_IDS = LOOP_REGION_IDS
SMOOTH_DISPLAY_OUTPUT_COUNT = 4
SMOOTH_ATTEMPT_COUNT = 5
SMOOTH_RESERVED_USD = 2.5
SMOOTH_REPLACED_VARIANT_ID = "staggered-ease"
SMOOTH_RETRY_VARIANT_ID = "staggered-ease-retry1"
SMOOTH_ACCEPTED_REASON = "smooth-enough-and-fidelity-preserved"
SMOOTH_EXCLUDED_REASON = "object-substitution"
SMOOTH_REVIEWER = "codex-visual-inspection"
SMOOTH_INITIAL_EXCLUSION_NOTE = (
    "Antique two-pan balance morphs into a round clock/dial in later frames."
)
SMOOTH_RETRY_ACCEPTANCE_NOTE = (
    "Antique two-pan balance remains recognizable; motion is accepted for the "
    "four-video smooth demo set."
)
SMOOTH_DEFAULT_ACCEPTANCE_NOTE = (
    "Accepted for the four-video smooth demo set after contact-sheet review."
)
SMOOTH_FEATURED_REVIEW_SCHEMA_VERSION = (
    "clipmaker-lite.case21-smooth-featured-review.v1"
)
SMOOTH_FEATURED_STATUS = "visual-winner"
SMOOTH_FEATURED_LABEL = "Визуальный победитель"
SMOOTH_FEATURED_REVIEWER = "operator-visual-selection"
SMOOTH_FEATURED_SUMMARY = (
    "Визуально самый цельный результат серии: движения остаются плавными и "
    "локальными, а старинные двухчашечные весы, формула, подписи и компоновка "
    "сохраняются. Это визуальный выбор, а не первое место proxy-рейтинга."
)
SMOOTH_FEATURED_PROMPT_DISTINCTION = (
    "По сравнению с исходным staggered-ease, retry разделяет два похожих объекта "
    "и фиксирует их части: exact two-pan balance с locked central stand, где "
    "двигаются только pans; отдельно — needle within its dial у современных "
    "весов. Targeted negative адресно запрещает дефект первой попытки — clock/dial "
    "substitution старинных весов."
)
SMOOTH_FEATURED_PRACTICES = (
    {
        "id": "long-overlapping-eases",
        "title": "Длинные перекрывающиеся переходы",
        "description": (
            "Все действия распределены на пять секунд и мягко перекрываются, "
            "поэтому сцена воспринимается как единая хореография."
        ),
    },
    {
        "id": "bounded-one-shot-motion",
        "title": "Ограниченная амплитуда",
        "description": (
            "Для объектов заданы один пульс, одно неглубокое покачивание и "
            "непрерывные траектории вместо повторяющихся резких жестов."
        ),
    },
    {
        "id": "structural-locks",
        "title": "Part-level invariants",
        "description": (
            "Exact two-pan balance разбит на locked central stand и подвижные "
            "pans; стрелка современных весов отдельно движется within its dial."
        ),
    },
    {
        "id": "failure-specific-negative",
        "title": "Запрет конкретного дефекта",
        "description": (
            "Negative prompt прямо запрещает превращать старинные весы в часы "
            "или циферблат, а также исключает morphing, рывки и layout drift."
        ),
    },
    {
        "id": "held-end-states",
        "title": "Удержание финальных состояний",
        "description": (
            "Батарея последовательно доходит до зелёного и остаётся зелёной, "
            "а аура сжимается и тускнеет без обратного движения и loop."
        ),
    },
)

PUBLIC_RAW_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)

PRIMARY_TREE_DIGEST = (
    "0e7dc0d0fe9461a6c91d91df56aec4a1e49562929c756dc7913fab21e7cfe7a8"
)
RETRY_TREE_DIGEST = (
    "54967ca5b10ef079a21deca6ab0de9835a0b0105da032d57e9364718c914e53b"
)
STAGE1_GENERATION_CORE_DIGEST = (
    "bbb230607f881491635dfab3e9a9d970d49eafdaabdbc1f2582d405076004f51"
)
STAGE2_GENERATION_CORE_DIGEST = (
    "09d7af5f90ed8296f41544b10330f25cc2295af4596f7ae6ad9bc296f0afa54a"
)

AGGREGATE_BUDGET_CAP_USD = 3.0
STAGE1_RESERVED_USD = 2.2
STAGE2_RESERVED_USD = 0.5
AGGREGATE_RESERVED_USD = 2.7


class FinalizeError(RuntimeError):
    """A fail-closed case-21 research-finalization error."""


@dataclass(frozen=True)
class Control:
    path: Path
    digest: str
    exclude_review_material: bool = False


CONTROLS = {
    "primary": Control(case21.BATCH_ROOT, PRIMARY_TREE_DIGEST),
    "retry": Control(case21.RETRY_BATCH_ROOT, RETRY_TREE_DIGEST),
    "stage1_generation_core": Control(
        STAGE1_ROOT,
        STAGE1_GENERATION_CORE_DIGEST,
        exclude_review_material=True,
    ),
    "stage2_generation_core": Control(
        STAGE2_ROOT,
        STAGE2_GENERATION_CORE_DIGEST,
        exclude_review_material=True,
    ),
}


@dataclass(frozen=True)
class DisplaySelection:
    model_id: str
    planning_run_id: str
    planning_result_sha256: str
    planning_model_ids: tuple[str, ...]
    batch_id: str
    generation_path: Path
    sample_id: str
    provider_run_id: str
    prompt_path: Path
    run_path: Path
    video_path: Path
    review_path: Path
    review_sha256: str
    review_evidence_path: Path
    review_evidence_sha256: str
    video_sha256: str
    request_sha256: str
    expected_status: str
    expected_media: dict[str, Any]
    expected_contract_conforms: bool
    expected_contract_warnings: tuple[str, ...]
    activity: str
    experiment_id: str | None = None
    variant_id: str | None = None


PRIMARY_WAN22_BASE = (
    case21.BATCH_ROOT
    / "videos"
    / case21.ARTICLE_SLUG
    / native.MODEL_DIRECTORIES[native.WAN_MODEL_ID]
)
RETRY_WAN27_BASE = (
    case21.RETRY_BATCH_ROOT
    / "videos"
    / case21.ARTICLE_SLUG
    / native.MODEL_DIRECTORIES[native.WAN_27_MODEL_ID]
)
STAGE1_MONOTONIC_WAN27_BASE = (
    STAGE1_ROOT
    / "videos"
    / "monotonic-positive"
    / native.MODEL_DIRECTORIES[native.WAN_27_MODEL_ID]
)
STAGE1_EROSION_WAN22_BASE = (
    STAGE1_ROOT
    / "videos"
    / "erosion-negative"
    / native.MODEL_DIRECTORIES[native.WAN_MODEL_ID]
)
STAGE1_WAN27_BASE = (
    STAGE1_ROOT / "videos" / "erosion-negative" / native.MODEL_DIRECTORIES[native.WAN_27_MODEL_ID]
)
STAGE1_VEO_BASE = (
    STAGE1_ROOT / "videos" / "veo-motion-only" / native.MODEL_DIRECTORIES[native.VEO_31_MODEL_ID]
)
STAGE2_WAN27_BASE = STAGE2_ROOT / "videos" / native.MODEL_DIRECTORIES[native.WAN_27_MODEL_ID]

DISPLAY_SELECTIONS = (
    DisplaySelection(
        model_id=native.WAN_MODEL_ID,
        planning_run_id=case21.PLANNING_RUN_ID,
        planning_result_sha256=(
            "c1a4453979a13ea9291efde8c2ef0491a9e4a08327d615ba4dc6699ce7bf1a39"
        ),
        planning_model_ids=case21.MODEL_IDS,
        batch_id=case21.PROVIDER_BATCH_ID,
        generation_path=case21.GENERATION_MANIFEST_PATH,
        sample_id=case21.SAMPLE_ID,
        provider_run_id=(
            "promopages-9930-case21-maier-runs-20260727-v1-"
            "21-maier-doctor-zolotoe-vremia-04-wan-2-2"
        ),
        prompt_path=PRIMARY_WAN22_BASE / "04.prompt.json",
        run_path=PRIMARY_WAN22_BASE / "04.run.json",
        video_path=PRIMARY_WAN22_BASE / "04.mp4",
        review_path=PRIMARY_WAN22_BASE / "04.review.json",
        review_sha256=(
            "a82bfc1c029c55532a65ca73b4ae737f45ba1b1b03853365f717cfdef0dca246"
        ),
        review_evidence_path=PRIMARY_WAN22_BASE / "04.review.json",
        review_evidence_sha256=(
            "a82bfc1c029c55532a65ca73b4ae737f45ba1b1b03853365f717cfdef0dca246"
        ),
        video_sha256=(
            "98712af3715210cd1d6709deb3b409b81a8ea1d8c8b6f057f0271fabc529a2ec"
        ),
        request_sha256=(
            "6dc36da3ff5093eb8c6e9ea783e3c8fe44b92a38931aa1fba3ce50a5cc633097"
        ),
        expected_status="succeeded",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 3.233,
            "width": 944,
            "height": 944,
            "fps": 30.0,
            "frames": 97,
            "has_audio": False,
            "bytes": 247040,
            "sha256": (
                "98712af3715210cd1d6709deb3b409b81a8ea1d8c8b6f057f0271fabc529a2ec"
            ),
        },
        expected_contract_conforms=True,
        expected_contract_warnings=(),
        activity="baseline-generation",
    ),
    DisplaySelection(
        model_id=native.WAN_27_MODEL_ID,
        planning_run_id="promopages-9930-case21-erosion-negative-20260727-v1",
        planning_result_sha256=(
            "a2934ffa723151b82b869d835934407dbbcea7ac384a270412e3adbe3fc71664"
        ),
        planning_model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-erosion-negative",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-erosion-negative-wan-2-7"
        ),
        prompt_path=STAGE1_WAN27_BASE / "04.prompt.json",
        run_path=STAGE1_WAN27_BASE / "04.run.json",
        video_path=STAGE1_WAN27_BASE / "04.mp4",
        review_path=STAGE1_WAN27_BASE / "04.review.json",
        review_sha256=(
            "47dc0e3e9c3584b17dbb4927507906b748a79eea38bbeebcd6b5ed3f1093fb1c"
        ),
        review_evidence_path=(
            STAGE1_ROOT / "review/contact-sheets/erosion-negative-wan27.png"
        ),
        review_evidence_sha256=(
            "926dc1cd5edb6d4e3b5e65136e537527379b12905179a08e2e37dcc97160eefb"
        ),
        video_sha256=(
            "12f7e4ae07bb607ac5849f14815df9053ae50ff6551ce8ec299c609ffb994b65"
        ),
        request_sha256=(
            "f3d3fb960427ea6122b4c0ba5889ae308298e34656a57c48be32f21a821c2caf"
        ),
        expected_status="verification-failed",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1440,
            "height": 1440,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
            "bytes": 2318997,
            "sha256": (
                "12f7e4ae07bb607ac5849f14815df9053ae50ff6551ce8ec299c609ffb994b65"
            ),
        },
        expected_contract_conforms=False,
        expected_contract_warnings=("audio", "resolution"),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="erosion-negative",
    ),
    DisplaySelection(
        model_id=native.VEO_31_MODEL_ID,
        planning_run_id="promopages-9930-case21-veo-motion-only-20260727-v1",
        planning_result_sha256=(
            "df820159b155a45012f16d43d24c544dc8782882ed6118023118399989c03506"
        ),
        planning_model_ids=(native.VEO_31_MODEL_ID,),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-veo-motion-only",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-veo-motion-only-veo-3-1-lite"
        ),
        prompt_path=STAGE1_VEO_BASE / "04.prompt.json",
        run_path=STAGE1_VEO_BASE / "04.run.json",
        video_path=STAGE1_VEO_BASE / "04.mp4",
        review_path=STAGE1_VEO_BASE / "04.review.json",
        review_sha256=(
            "83dd2a7f078c7b2cfa91fe5e111b6f2b43204c90048a4d1348b79ac37bc51b2b"
        ),
        review_evidence_path=STAGE1_ROOT / "review/contact-sheets/veo-motion-only.png",
        review_evidence_sha256=(
            "d75e9a82f3cef1651ffb8971f92ffb13f6e73da84e5ba8552a3447c7f7535b98"
        ),
        video_sha256=(
            "0c96252e39323c77bcc2853b236e133fdd812b519328d8985d3dd5f626e58574"
        ),
        request_sha256=(
            "dd2c007450f7011981c4a4122fcf7bd5f8c23efc0a36f5f8b629ccba8eb28148"
        ),
        expected_status="succeeded",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "frames": 96,
            "has_audio": False,
            "bytes": 1384917,
            "sha256": (
                "0c96252e39323c77bcc2853b236e133fdd812b519328d8985d3dd5f626e58574"
            ),
        },
        expected_contract_conforms=True,
        expected_contract_warnings=(),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="veo-motion-only",
    ),
)

RESEARCH_SELECTIONS = (
    DisplaySelection(
        model_id=native.WAN_27_MODEL_ID,
        planning_run_id=case21.PLANNING_RUN_ID,
        planning_result_sha256=(
            "c1a4453979a13ea9291efde8c2ef0491a9e4a08327d615ba4dc6699ce7bf1a39"
        ),
        planning_model_ids=case21.MODEL_IDS,
        batch_id=case21.RETRY_PROVIDER_BATCH_ID,
        generation_path=case21.RETRY_GENERATION_MANIFEST_PATH,
        sample_id=case21.SAMPLE_ID,
        provider_run_id=(
            "promopages-9930-case21-maier-retry-wan27-veo-20260727-v1-"
            "21-maier-doctor-zolotoe-vremia-04-wan-2-7"
        ),
        prompt_path=RETRY_WAN27_BASE / "04.prompt.json",
        run_path=RETRY_WAN27_BASE / "04.run.json",
        video_path=RETRY_WAN27_BASE / "04.mp4",
        review_path=RETRY_WAN27_BASE / "04.review.json",
        review_sha256=(
            "c9f1bde94baa12b261a48dd848abe36c87a99dfc26fca94cbae7a7790f90b503"
        ),
        review_evidence_path=(
            STAGE1_ROOT / "review/contact-sheets/baseline-wan27.png"
        ),
        review_evidence_sha256=(
            "0e0f0969a86b3fe13adcd7a01332185e6e2d44c9eb1a5808f788a03baf199d81"
        ),
        video_sha256=(
            "5d7dd8073d77173da5da061e393c5b768533a152ec12a9d6214044a650fdef2a"
        ),
        request_sha256=(
            "d382ee035d4825f6033975681eb126315820965a1e56ca428ce7c40c2ef7d198"
        ),
        expected_status="verification-failed",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1440,
            "height": 1440,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
            "bytes": 2253774,
            "sha256": (
                "5d7dd8073d77173da5da061e393c5b768533a152ec12a9d6214044a650fdef2a"
            ),
        },
        expected_contract_conforms=False,
        expected_contract_warnings=("audio", "resolution"),
        activity="explicit-retry",
    ),
    DisplaySelection(
        model_id=native.WAN_27_MODEL_ID,
        planning_run_id="promopages-9930-case21-monotonic-positive-20260727-v1",
        planning_result_sha256=(
            "addacbc3ef88d516b1a9d4ae564713ed71be5a16cb41623bc8256ec68d9c062a"
        ),
        planning_model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-monotonic-positive",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-monotonic-positive-wan-2-7"
        ),
        prompt_path=STAGE1_MONOTONIC_WAN27_BASE / "04.prompt.json",
        run_path=STAGE1_MONOTONIC_WAN27_BASE / "04.run.json",
        video_path=STAGE1_MONOTONIC_WAN27_BASE / "04.mp4",
        review_path=STAGE1_MONOTONIC_WAN27_BASE / "04.review.json",
        review_sha256=(
            "86563f88b9c942c7f7a684914017b3dbd813d3e227d9af00b09cbbc490dd9768"
        ),
        review_evidence_path=(
            STAGE1_ROOT / "review/contact-sheets/monotonic-positive-wan27.png"
        ),
        review_evidence_sha256=(
            "9e854691dc797c43fd719a6c0059cf5e58b594de20f6d2aeac00c234f4124f0d"
        ),
        video_sha256=(
            "ffadc7aad0077c344ca16e251ec12b41b2222b71061f876dfd701202fbe15277"
        ),
        request_sha256=(
            "f16bcfc1f5e06d7b10b1e336a492c954fcea84a512fd8fc993be4286eefac970"
        ),
        expected_status="verification-failed",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1440,
            "height": 1440,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
            "bytes": 2569300,
            "sha256": (
                "ffadc7aad0077c344ca16e251ec12b41b2222b71061f876dfd701202fbe15277"
            ),
        },
        expected_contract_conforms=False,
        expected_contract_warnings=("audio", "resolution"),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="monotonic-positive",
    ),
    DisplaySelection(
        model_id=native.WAN_MODEL_ID,
        planning_run_id="promopages-9930-case21-erosion-negative-20260727-v1",
        planning_result_sha256=(
            "a2934ffa723151b82b869d835934407dbbcea7ac384a270412e3adbe3fc71664"
        ),
        planning_model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-erosion-negative",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-erosion-negative-wan-2-2"
        ),
        prompt_path=STAGE1_EROSION_WAN22_BASE / "04.prompt.json",
        run_path=STAGE1_EROSION_WAN22_BASE / "04.run.json",
        video_path=STAGE1_EROSION_WAN22_BASE / "04.mp4",
        review_path=STAGE1_EROSION_WAN22_BASE / "04.review.json",
        review_sha256=(
            "41e9ae80d9292b2a2fb1b832653344375126e22763ecb567212f5eb4db803b45"
        ),
        review_evidence_path=(
            STAGE1_ROOT / "review/contact-sheets/erosion-negative-wan22.png"
        ),
        review_evidence_sha256=(
            "84e046f4565908cc864533b5eae6d580e845fd3c57e4f607a94e0f0aa446a67e"
        ),
        video_sha256=(
            "8224f815fba75fcc1911496f9442842f68175cbbc6edabfb35d479a27aa0524d"
        ),
        request_sha256=(
            "367df96911f1ae3c473f07b50a837e680a51a14303e5f5f200b69bf06ed144e6"
        ),
        expected_status="succeeded",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 3.233,
            "width": 944,
            "height": 944,
            "fps": 30.0,
            "frames": 97,
            "has_audio": False,
            "bytes": 241667,
            "sha256": (
                "8224f815fba75fcc1911496f9442842f68175cbbc6edabfb35d479a27aa0524d"
            ),
        },
        expected_contract_conforms=True,
        expected_contract_warnings=(),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="erosion-negative",
    ),
    DisplaySelection(
        model_id=native.WAN_27_MODEL_ID,
        planning_run_id="promopages-9930-case21-opacity-only-20260727-v1",
        planning_result_sha256=(
            "57caec79fa7390a07101fbe314dc66b11f448291e271adc5eca8d447332187db"
        ),
        planning_model_ids=(native.WAN_27_MODEL_ID,),
        batch_id="promopages-9930-case21-opacity-only-stage2-20260727-v1",
        generation_path=STAGE2_GENERATION_PATH,
        sample_id="21-maier-04-opacity-only",
        provider_run_id=(
            "promopages-9930-case21-opacity-only-stage2-20260727-v1-"
            "21-maier-04-opacity-only-wan-2-7"
        ),
        prompt_path=STAGE2_WAN27_BASE / "04.prompt.json",
        run_path=STAGE2_WAN27_BASE / "04.run.json",
        video_path=STAGE2_WAN27_BASE / "04.mp4",
        review_path=STAGE2_WAN27_BASE / "04.review.json",
        review_sha256=(
            "8e6e252813ccd77ea46af4b36efdb6a668fb362aea7ab3f09f780d2070c7d325"
        ),
        review_evidence_path=STAGE2_ROOT / "review/contact-sheet.png",
        review_evidence_sha256=(
            "4fb1f05890337d3706e9acdb2a6e18752fe0b408b44913055f7a255b60780a64"
        ),
        video_sha256=(
            "abcaaccf20ee93871db5201c5ab7759285f7dd78b84dd9d2c29999bc7c4f0dd7"
        ),
        request_sha256=(
            "5d3c1ce44ec71281015aa2a6b1911780f7f1e287073c370c9f6f98129bb86929"
        ),
        expected_status="verification-failed",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1440,
            "height": 1440,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
            "bytes": 2614579,
            "sha256": (
                "abcaaccf20ee93871db5201c5ab7759285f7dd78b84dd9d2c29999bc7c4f0dd7"
            ),
        },
        expected_contract_conforms=False,
        expected_contract_warnings=("audio", "resolution"),
        activity="prompt-experiment",
        experiment_id=STAGE2_EXPERIMENT_ID,
        variant_id="opacity-only",
    ),
)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise FinalizeError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FinalizeError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise FinalizeError(f"Required regular file is missing or unsafe: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise FinalizeError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise FinalizeError(f"Path escapes workspace: {path}") from exc


def tree_digest(control: Control, root: Path = ROOT) -> str:
    base = root / control.path
    if not base.is_dir() or base.is_symlink():
        raise FinalizeError(f"Control tree is missing or unsafe: {base}")
    lines: list[str] = []
    for item in sorted(base.rglob("*")):
        if item.is_symlink():
            raise FinalizeError(f"Symlink is forbidden in control tree: {item}")
        if not item.is_file():
            continue
        relative_to_base = item.relative_to(base)
        if control.exclude_review_material and (
            (relative_to_base.parts and relative_to_base.parts[0] == "review")
            or item.name.endswith(".review.json")
        ):
            continue
        lines.append(f"{sha256_file(item)}  {_relative(item, root)}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_controls(root: Path = ROOT) -> dict[str, str]:
    measured = {name: tree_digest(control, root) for name, control in CONTROLS.items()}
    expected = {name: control.digest for name, control in CONTROLS.items()}
    if measured != expected:
        raise FinalizeError(
            f"Case-21 immutable control digests changed: expected {expected}, got {measured}"
        )
    return measured


def _expected_cost() -> dict[str, Any]:
    return {
        "currency": "USD",
        "operator_budget_cap_usd": AGGREGATE_BUDGET_CAP_USD,
        "reserved_stage1_usd": STAGE1_RESERVED_USD,
        "reserved_stage2_usd": STAGE2_RESERVED_USD,
        "reserved_aggregate_usd": AGGREGATE_RESERVED_USD,
        "unreserved_usd": round(
            AGGREGATE_BUDGET_CAP_USD - AGGREGATE_RESERVED_USD, 2
        ),
        "reservation_kind": "conservative-operator-envelope",
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "$2.70 is reserved inside the $3.00 operator cap; provider receipts "
            "do not expose actual billing, so this is not an actual-spend claim."
        ),
    }


def validate_budget_receipts(root: Path = ROOT) -> None:
    stage1 = read_json(root / STAGE1_INVENTORY_PATH)
    stage2 = read_json(root / STAGE2_INVENTORY_PATH)
    stage1_cost = stage1.get("cost") if isinstance(stage1, dict) else None
    stage2_cost = stage2.get("cost") if isinstance(stage2, dict) else None
    if (
        stage1.get("manifest_role") != "case-21-prompt-research-stage1"
        or stage1.get("agent_id") != AGENT_ID
        or stage1.get("controls")
        != {
            "primary": PRIMARY_TREE_DIGEST,
            "retry": RETRY_TREE_DIGEST,
        }
        or not isinstance(stage1_cost, dict)
        or stage1_cost.get("operator_budget_cap_usd") != AGGREGATE_BUDGET_CAP_USD
        or stage1_cost.get("reserved_stage1_usd") != STAGE1_RESERVED_USD
        or stage1_cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Stage-1 budget/control receipt changed")
    if (
        stage2.get("manifest_role") != "case-21-opacity-only-stage2"
        or stage2.get("agent_id") != AGENT_ID
        or stage2.get("controls")
        != {
            "primary": PRIMARY_TREE_DIGEST,
            "retry": RETRY_TREE_DIGEST,
            "stage1_generation_core": STAGE1_GENERATION_CORE_DIGEST,
        }
        or not isinstance(stage2_cost, dict)
        or stage2_cost.get("operator_aggregate_budget_cap_usd")
        != AGGREGATE_BUDGET_CAP_USD
        or stage2_cost.get("reserved_stage1_usd") != STAGE1_RESERVED_USD
        or stage2_cost.get("reserved_stage2_usd") != STAGE2_RESERVED_USD
        or stage2_cost.get("reserved_aggregate_usd") != AGGREGATE_RESERVED_USD
        or stage2_cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Stage-2 aggregate budget/control receipt changed")


def _safe_provenance(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verified": True,
        "verification_scope": summary.get("verification_scope"),
        "cryptographically_signed": summary.get("cryptographically_signed"),
        "agent_id": summary.get("agent_id"),
        "contract_version": summary.get("contract_version"),
        "contract_fingerprint": summary.get("contract_fingerprint"),
        "instruction_bundle_sha256": summary.get("instruction_bundle_sha256"),
        "source_image_sha256": summary.get("source_image_sha256"),
        "article_context_sha256": summary.get("article_context_sha256"),
        "models": summary.get("models"),
    }


def _validated_planning(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    summary = runner.provenance_summary(root, selection.planning_run_id)
    result_relative = (
        case21.ARTIFACT_NAMESPACE / selection.planning_run_id / "result.json"
    ).as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != "2.0.2"
        or summary.get("models") != list(selection.planning_model_ids)
        or summary.get("source_image_sha256") != source.image["sha256"]
        or summary.get("article_context_sha256") != source.context_sha256
        or summary.get("result_path") != result_relative
    ):
        raise FinalizeError(
            f"Lite provenance changed for {selection.planning_run_id}"
        )
    result_path = root / result_relative
    if sha256_file(result_path) != selection.planning_result_sha256:
        raise FinalizeError(f"Lite result changed for {selection.planning_run_id}")
    result = read_json(result_path)
    producer = result.get("producer") if isinstance(result, dict) else None
    inputs = result.get("inputs") if isinstance(result, dict) else None
    result_source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models") if isinstance(result, dict) else None
    analysis = result.get("analysis") if isinstance(result, dict) else None
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        result.get("job_id") != selection.planning_run_id
        or not isinstance(producer, dict)
        or producer.get("agent_id") != AGENT_ID
        or not isinstance(result_source, dict)
        or result_source.get("path") != source.image["source_path"]
        or result_source.get("sha256") != source.image["sha256"]
        or not isinstance(context, dict)
        or context.get("path") != source.context_path
        or context.get("sha256") != source.context_sha256
        or not isinstance(models, list)
        or [item.get("model_id") for item in models if isinstance(item, dict)]
        != list(selection.planning_model_ids)
        or not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(
            not isinstance(intent.get(key), str) or not intent[key].strip()
            for key in runner.STRUCTURED_INTENT_KEYS
        )
    ):
        raise FinalizeError(
            f"Lite result binding changed for {selection.planning_run_id}"
        )
    model = next(
        (
            item
            for item in models
            if isinstance(item, dict) and item.get("model_id") == selection.model_id
        ),
        None,
    )
    contract = read_json(root / case21.CONTRACT_PATH)
    expected_runtime = contract.get("models", {}).get(selection.model_id, {}).get(
        "runtime"
    )
    if (
        not isinstance(model, dict)
        or model.get("runtime") != expected_runtime
        or not isinstance(model.get("positive_prompt"), str)
        or not model["positive_prompt"].strip()
    ):
        raise FinalizeError(
            f"Selected model plan changed for {selection.planning_run_id}"
        )
    return summary, result, model, {
        key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS
    }


def _generation_output(
    selection: DisplaySelection,
    root: Path,
) -> dict[str, Any]:
    manifest = read_json(root / selection.generation_path)
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    expected_counts = {
        case21.GENERATION_MANIFEST_PATH: len(case21.MODEL_IDS),
        case21.RETRY_GENERATION_MANIFEST_PATH: len(case21.RETRY_MODEL_IDS),
        STAGE1_GENERATION_PATH: 5,
        STAGE2_GENERATION_PATH: 1,
    }
    expected_count = expected_counts.get(selection.generation_path)
    if (
        expected_count is None
        or manifest.get("batch_id") != selection.batch_id
        or manifest.get("agent_id") != AGENT_ID
        or manifest.get("expected_outputs") != expected_count
        or not isinstance(outputs, list)
        or len(outputs) != expected_count
    ):
        raise FinalizeError(f"Generation manifest changed: {selection.generation_path}")
    matches = [
        output
        for output in outputs
        if isinstance(output, dict)
        and output.get("provider_run_id") == selection.provider_run_id
    ]
    if len(matches) != 1:
        raise FinalizeError(
            f"Selected provider output is missing or duplicated: "
            f"{selection.provider_run_id}"
        )
    return matches[0]


def _expected_prompt_artifact(
    selection: DisplaySelection,
    summary: dict[str, Any],
    model: dict[str, Any],
    intent: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "ticket": TICKET,
        "batch_id": selection.batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "model_id": selection.model_id,
        "source": {
            "path": case21.SOURCE_PATH.as_posix(),
            "sha256": case21.EXPECTED_SOURCE_SHA256,
            "width": 1024,
            "height": 1024,
        },
        "structured_intent": intent,
        "prompt": {
            "positive": model.get("positive_prompt"),
            "negative": model.get("negative_prompt"),
        },
        "runtime": model.get("runtime"),
        "lite_result": {
            "path": (
                case21.ARTIFACT_NAMESPACE
                / selection.planning_run_id
                / "result.json"
            ).as_posix(),
            "sha256": selection.planning_result_sha256,
            "provenance": _safe_provenance(summary),
        },
    }


def _provider_sample(selection: DisplaySelection) -> dict[str, Any]:
    source_url = (
        PUBLIC_RAW_BASE + quote(case21.SOURCE_PATH.as_posix(), safe="/")
        if selection.activity == "baseline-generation"
        else case21.EXPECTED_ORIG_URL
    )
    return {
        "sample_id": selection.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "image_number": case21.IMAGE_ID,
        "source_path": case21.SOURCE_PATH.as_posix(),
        "source_url": source_url,
        "sha256": case21.EXPECTED_SOURCE_SHA256,
        "width": 1024,
        "height": 1024,
    }


def _provider_prompt(selection: DisplaySelection, model: dict[str, Any]) -> dict[str, Any]:
    prompt = {
        "sample_id": selection.sample_id,
        "model_id": selection.model_id,
        "target_duration_seconds": model["runtime"]["duration_seconds"],
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }
    if selection.model_id == native.WAN_27_MODEL_ID:
        if model["runtime"].get("prompt_expansion") != {
            "parameter": "prompt_extend",
            "value": True,
        }:
            raise FinalizeError("Wan 2.7 prompt-expansion contract changed")
        prompt["prompt_extend"] = True
    return prompt


def _validate_review(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    review_path = root / selection.review_path
    evidence_path = root / selection.review_evidence_path
    if sha256_file(review_path) != selection.review_sha256:
        raise FinalizeError(
            f"Exact visual review changed: {selection.review_path}"
        )
    if sha256_file(evidence_path) != selection.review_evidence_sha256:
        raise FinalizeError(
            f"Exact visual-review evidence changed: {selection.review_evidence_path}"
        )
    review = read_json(review_path)
    expected_keys = {
        "schema_version",
        "ticket",
        "model_id",
        "provider_run_id",
        "lite_run_id",
        "source",
        "artifact",
        "review_method",
        "observations",
        "verdict",
    }
    observations = review.get("observations") if isinstance(review, dict) else None
    verdict = review.get("verdict") if isinstance(review, dict) else None
    if (
        not isinstance(review, dict)
        or set(review) != expected_keys
        or review.get("schema_version") != 1
        or review.get("ticket") != TICKET
        or review.get("model_id") != selection.model_id
        or review.get("provider_run_id") != selection.provider_run_id
        or review.get("lite_run_id") != selection.planning_run_id
        or review.get("source")
        != {
            "path": source.image["source_path"],
            "sha256": source.image["sha256"],
        }
        or review.get("artifact")
        != {
            "path": selection.video_path.as_posix(),
            "sha256": selection.video_sha256,
        }
        or not isinstance(observations, dict)
        or not isinstance(observations.get("invariant_failures"), list)
        or not observations["invariant_failures"]
        or not isinstance(verdict, dict)
        or set(verdict) != {"status", "summary"}
        or verdict.get("status") != "fidelity-failed"
        or not isinstance(verdict.get("summary"), str)
        or not verdict["summary"].strip()
    ):
        raise FinalizeError(
            f"Visual-review identity or failure verdict changed: {selection.review_path}"
        )
    return verdict, {
        "path": selection.review_evidence_path.as_posix(),
        "sha256": selection.review_evidence_sha256,
    }


def validate_display_selection(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary, _result, model, intent = _validated_planning(selection, source, root)
    output = _generation_output(selection, root)
    expected_paths = {
        "prompt_path": selection.prompt_path.as_posix(),
        "run_path": selection.run_path.as_posix(),
        "video_path": selection.video_path.as_posix(),
    }
    expected_identity = {
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "sample_id": selection.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "source_path": source.image["source_path"],
        "model_id": selection.model_id,
        **expected_paths,
    }
    if any(output.get(key) != value for key, value in expected_identity.items()):
        raise FinalizeError(
            f"Aggregate output identity changed: {selection.provider_run_id}"
        )

    prompt_path = root / selection.prompt_path
    run_path = root / selection.run_path
    video_path = root / selection.video_path
    prompt = read_json(prompt_path)
    expected_prompt = _expected_prompt_artifact(selection, summary, model, intent)
    if prompt != expected_prompt:
        raise FinalizeError(
            f"Prompt receipt differs from the verified Lite result: "
            f"{selection.prompt_path}"
        )
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise FinalizeError(f"Run receipt is not an object: {selection.run_path}")
    run_identity = {
        "ticket": TICKET,
        "batch_id": selection.batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "sample_id": selection.sample_id,
        "image_id": case21.IMAGE_ID,
        "model_id": selection.model_id,
        "prompt_path": selection.prompt_path.as_posix(),
        "output_path": selection.video_path.as_posix(),
        "lite_result_sha256": selection.planning_result_sha256,
    }
    if any(run.get(key) != value for key, value in run_identity.items()):
        raise FinalizeError(f"Run identity changed: {selection.run_path}")
    if any(run.get(key) for key in ("retry_of", "retry_count", "attempts")):
        raise FinalizeError(f"Mutable retry metadata is forbidden: {selection.run_path}")

    sample = _provider_sample(selection)
    provider_prompt = _provider_prompt(selection, model)
    expected_request = transport.build_request_preview(sample, provider_prompt)
    request_sha256 = transport.request_fingerprint(expected_request, sample)
    if (
        run.get("request") != expected_request
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
        or run.get("request_sha256") != request_sha256
        or request_sha256 != selection.request_sha256
    ):
        raise FinalizeError(f"Provider request changed: {selection.run_path}")
    effective_status = native.effective_run_status(run)
    mirrored = {
        "recorded_status": run.get("status"),
        "status": effective_status,
        "provider_may_be_active": run.get("provider_may_be_active"),
        "media": run.get("media"),
        "contract_check": run.get("contract_check"),
        "error": run.get("error"),
    }
    if any(output.get(key) != value for key, value in mirrored.items()):
        raise FinalizeError(
            f"Aggregate output differs from run receipt: {selection.provider_run_id}"
        )
    if (
        effective_status != selection.expected_status
        or run.get("provider_may_be_active") is not False
        or run.get("last_worker_failure") is not None
        or run.get("media") != selection.expected_media
        or output.get("media") != selection.expected_media
    ):
        raise FinalizeError(
            f"Selected run status/media changed: {selection.provider_run_id}"
        )
    if (
        sha256_file(video_path) != selection.video_sha256
        or video_path.stat().st_size != selection.expected_media["bytes"]
    ):
        raise FinalizeError(f"Selected MP4 bytes changed: {selection.video_path}")
    contract_check = run.get("contract_check")
    if (
        not isinstance(contract_check, dict)
        or contract_check.get("conforms")
        is not selection.expected_contract_conforms
        or contract_check.get("warnings")
        != list(selection.expected_contract_warnings)
    ):
        raise FinalizeError(
            f"Selected media contract receipt changed: {selection.run_path}"
        )
    verdict, review_evidence = _validate_review(selection, source, root)
    route = transport.route_for_model(selection.model_id)
    final_output = {
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "source_path": source.image["source_path"],
        "sample_id": selection.sample_id,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "model_id": selection.model_id,
        "scene_plan": model.get("scene_plan"),
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "status": effective_status,
        "recorded_status": run.get("status"),
        "available": True,
        "accepted": False,
        "availability_status": "available-for-research-display",
        "acceptance_status": "rejected-visual-fidelity",
        "prompt_path": selection.prompt_path.as_posix(),
        "run_path": selection.run_path.as_posix(),
        "video_path": selection.video_path.as_posix(),
        "delivery": "repository-raw",
        "repository_raw_url": PUBLIC_RAW_BASE
        + quote(selection.video_path.as_posix(), safe="/"),
        "route": {
            "adapter": route["adapter"],
            "transport": route["transport"],
            "provider": route.get("provider_key") or "wan-streamlit",
            "capacity": int(route["capacity"]),
            "route_substitution": False,
        },
        "media": selection.expected_media,
        "contract_check": contract_check,
        "visual_review": verdict,
        "review_path": selection.review_path.as_posix(),
        "review_evidence": review_evidence,
        "selection": {
            "activity": selection.activity,
            "experiment_id": selection.experiment_id,
            "variant_id": selection.variant_id,
            "purpose": "failure-analysis-display",
        },
        "error": run.get("error"),
    }
    planning = {
        "model_id": selection.model_id,
        "run_id": selection.planning_run_id,
        "result_path": summary.get("result_path"),
        "result_sha256": selection.planning_result_sha256,
        "structured_intent": intent,
        "provenance": summary,
    }
    return final_output, planning


def _manifest_attempts(
    manifest_path: Path,
    *,
    activity: str,
    experiment_id: str | None,
    variant_from_sample: bool,
    root: Path,
) -> Iterable[dict[str, Any]]:
    manifest = read_json(root / manifest_path)
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    if not isinstance(outputs, list):
        raise FinalizeError(f"Attempt manifest has no outputs: {manifest_path}")
    primary_ids = {selection.provider_run_id for selection in DISPLAY_SELECTIONS}
    selected_ids = primary_ids | {
        selection.provider_run_id for selection in RESEARCH_SELECTIONS
    }
    for output in outputs:
        if not isinstance(output, dict):
            raise FinalizeError(f"Attempt output is not an object: {manifest_path}")
        run_value = output.get("run_path")
        if not isinstance(run_value, str):
            raise FinalizeError(f"Attempt run_path is missing: {manifest_path}")
        run_path = root / Path(run_value)
        run = read_json(run_path)
        mirrored = {
            "provider_run_id": run.get("provider_run_id"),
            "lite_run_id": run.get("lite_run_id"),
            "model_id": run.get("model_id"),
            "recorded_status": run.get("status"),
            "status": native.effective_run_status(run),
            "provider_may_be_active": run.get("provider_may_be_active"),
            "media": run.get("media"),
            "contract_check": run.get("contract_check"),
            "error": run.get("error"),
        }
        if any(output.get(key) != value for key, value in mirrored.items()):
            raise FinalizeError(f"Attempt aggregate differs from receipt: {run_value}")
        sample_id = output.get("sample_id")
        variant_id = None
        if variant_from_sample:
            if not isinstance(sample_id, str) or not sample_id.startswith("21-maier-04-"):
                raise FinalizeError(f"Experiment sample identity changed: {sample_id}")
            variant_id = sample_id.removeprefix("21-maier-04-")
        provider_run_id = output.get("provider_run_id")
        video_value = output.get("video_path")
        available_video = (
            isinstance(video_value, str)
            and (root / Path(video_value)).is_file()
            and not (root / Path(video_value)).is_symlink()
            and isinstance(output.get("media"), dict)
        )
        yield {
            "activity": activity,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "batch_id": manifest.get("batch_id"),
            "provider_run_id": provider_run_id,
            "lite_run_id": output.get("lite_run_id"),
            "sample_id": sample_id,
            "model_id": output.get("model_id"),
            "status": output.get("status"),
            "recorded_status": output.get("recorded_status"),
            "provider_may_be_active": output.get("provider_may_be_active"),
            "request_sha256": run.get("request_sha256"),
            "provider_job_id": run.get("provider_job_id"),
            "submitted_at": run.get("submitted_at"),
            "completed_at": run.get("completed_at"),
            "prompt_path": output.get("prompt_path"),
            "run_path": run_value,
            "video_path": video_value,
            "available_video": available_video,
            "selected_for_display": provider_run_id in selected_ids,
            "selected_for_primary_display": provider_run_id in primary_ids,
            "selected_for_acceptance": False,
            "error": output.get("error"),
        }


def build_attempt_history(root: Path = ROOT) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    history.extend(
        _manifest_attempts(
            case21.GENERATION_MANIFEST_PATH,
            activity="baseline-generation",
            experiment_id=None,
            variant_from_sample=False,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            case21.RETRY_GENERATION_MANIFEST_PATH,
            activity="explicit-retry",
            experiment_id=None,
            variant_from_sample=False,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            STAGE1_GENERATION_PATH,
            activity="prompt-experiment",
            experiment_id=STAGE1_EXPERIMENT_ID,
            variant_from_sample=True,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            STAGE2_GENERATION_PATH,
            activity="prompt-experiment",
            experiment_id=STAGE2_EXPERIMENT_ID,
            variant_from_sample=True,
            root=root,
        )
    )
    counters: dict[str, int] = {}
    for attempt in history:
        model_id = str(attempt.get("model_id"))
        counters[model_id] = counters.get(model_id, 0) + 1
        attempt["model_attempt_number"] = counters[model_id]
    if (
        len(history) != 11
        or sum(item["activity"] == "prompt-experiment" for item in history) != 6
        or sum(item["available_video"] for item in history) != 7
        or sum(item["selected_for_display"] for item in history) != 7
        or sum(item["selected_for_primary_display"] for item in history) != 3
        or any(item["selected_for_acceptance"] for item in history)
    ):
        raise FinalizeError("Case-21 research attempt history changed")
    return history


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validated_loop_source(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return the exact experiment/inventory pair, or ``None`` when absent.

    A materialized experiment manifest is written before paid generation starts,
    so existence alone does not make it publishable.  We still reconstruct an
    existing document before checking completion; a malformed partial receipt is
    never silently treated as a trustworthy experiment.
    """

    manifest_path = root / loop_experiment.EXPERIMENT_MANIFEST_PATH
    if not manifest_path.exists():
        return None
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise FinalizeError(f"Loop experiment manifest is unsafe: {manifest_path}")
    experiment = read_json(manifest_path)
    if not isinstance(experiment, dict):
        raise FinalizeError("Loop experiment manifest is not an object")
    updated_at = experiment.get("updated_at")
    cost = experiment.get("cost")
    budget = cost.get("operator_budget_cap_usd") if isinstance(cost, dict) else None
    if (
        experiment.get("manifest_role")
        != "case-21-wan27-loop-experiment"
        or experiment.get("ticket") != TICKET
        or experiment.get("experiment_id") != loop_experiment.EXPERIMENT_ID
        or experiment.get("provider_batch_id")
        != loop_experiment.PROVIDER_BATCH_ID
        or experiment.get("agent_id") != AGENT_ID
        or not isinstance(updated_at, str)
        or not updated_at.strip()
        or not isinstance(budget, (int, float))
        or isinstance(budget, bool)
        or float(budget) > float(loop_experiment.HARD_BUDGET_CAP_USD)
    ):
        raise FinalizeError("Loop experiment identity or budget changed")
    expected = loop_experiment._experiment_document(  # noqa: SLF001
        str(budget),
        root,
        updated_at=updated_at,
    )
    if experiment != expected:
        raise FinalizeError(
            "Loop experiment manifest differs from exact inventory and run receipts"
        )
    inventory = read_json(root / loop_experiment.INVENTORY_PATH)
    expected_inventory = loop_experiment.inventory_document(str(budget), root)
    if inventory != expected_inventory:
        raise FinalizeError("Loop inventory differs from exact Lite plans and requests")
    return experiment, inventory


def _loop_is_complete(experiment: dict[str, Any]) -> bool:
    outputs = experiment.get("outputs")
    if (
        not isinstance(outputs, list)
        or len(outputs) != loop_experiment.INITIAL_ENTRY_COUNT
    ):
        raise FinalizeError("Loop experiment output matrix changed")
    statuses = [str(output.get("status", "missing")) for output in outputs]
    return not any(status in LOOP_INCOMPLETE_STATUSES for status in statuses)


def _validated_loop_review(
    root: Path,
    available: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    review_path = root / LOOP_REVIEW_PATH
    if not available:
        if review_path.exists() and (
            not review_path.is_file() or review_path.is_symlink()
        ):
            raise FinalizeError(f"Loop review path is unsafe: {review_path}")
        return {}, sha256_file(review_path) if review_path.is_file() else ""
    if not review_path.is_file() or review_path.is_symlink():
        raise FinalizeError(f"Completed loop MP4s require {LOOP_REVIEW_PATH}")
    review_sha256 = sha256_file(review_path)
    report = read_json(review_path)
    if not isinstance(report, dict):
        raise FinalizeError("Loop review report is not an object")
    case = report.get("case")
    method = report.get("method")
    requested_regions = (
        method.get("requested_regions") if isinstance(method, dict) else None
    )
    videos = report.get("videos")
    if (
        report.get("schema_version") != LOOP_REVIEW_SCHEMA_VERSION
        or case
        != {
            "article_number": "21",
            "article_slug": case21.ARTICLE_SLUG,
            "image_id": case21.IMAGE_ID,
            "model_id": loop_experiment.MODEL_ID,
        }
        or not isinstance(requested_regions, list)
        or tuple(
            item.get("region_id") for item in requested_regions if isinstance(item, dict)
        )
        != LOOP_REGION_IDS
        or report.get("video_count") != len(available)
        or not isinstance(videos, list)
        or len(videos) != len(available)
    ):
        raise FinalizeError("Loop review report identity or requested ROI set changed")

    available_by_variant = {item["variant_id"]: item for item in available}
    if len(available_by_variant) != len(available):
        raise FinalizeError("Available loop variants are duplicated")
    reviewed: dict[str, dict[str, Any]] = {}
    for video in videos:
        if not isinstance(video, dict):
            raise FinalizeError("Loop review video entry is not an object")
        variant_id = video.get("video_id")
        expected = available_by_variant.get(str(variant_id))
        media = video.get("media")
        seam = video.get("seam")
        regions = video.get("regions")
        if (
            expected is None
            or variant_id in reviewed
            or video.get("path") != expected["video_path"]
            or video.get("sha256") != expected["video_sha256"]
            or video.get("seam_status") not in {"pass", "fail"}
            or video.get("fidelity_status") not in {"pass", "fail"}
            or not isinstance(media, dict)
            or not isinstance(seam, dict)
            or seam.get("seam_status") != video.get("seam_status")
            or not isinstance(seam.get("failed_checks"), list)
            or not isinstance(regions, list)
            or tuple(
                item.get("region_id") for item in regions if isinstance(item, dict)
            )
            != LOOP_REGION_IDS
            or any(
                not isinstance(item.get("detected_motion"), bool)
                for item in regions
                if isinstance(item, dict)
            )
        ):
            raise FinalizeError(f"Loop review binding changed for {variant_id!r}")
        run_media = expected["media"]
        try:
            frame_rate = float(Fraction(str(media.get("frame_rate"))))
        except (ValueError, ZeroDivisionError) as exc:
            raise FinalizeError(
                f"Loop review frame rate is invalid for {variant_id}"
            ) from exc
        media_matches = (
            media.get("width") == run_media.get("width")
            and media.get("height") == run_media.get("height")
            and media.get("codec") == run_media.get("codec")
            and media.get("container") == run_media.get("container")
            and media.get("has_audio") == run_media.get("has_audio")
            and media.get("bytes") == run_media.get("bytes")
            and abs(
                float(media.get("duration_seconds") or 0)
                - float(run_media.get("duration_seconds") or 0)
            )
            <= 0.1
            and (
                run_media.get("fps") is None
                or abs(frame_rate - float(run_media["fps"])) <= 0.001
            )
            and (
                run_media.get("frames") is None
                or media.get("frame_count") == run_media.get("frames")
            )
        )
        if not media_matches:
            raise FinalizeError(f"Loop review media changed for {variant_id}")
        reviewed[str(variant_id)] = video
    if set(reviewed) != set(available_by_variant):
        raise FinalizeError("Loop review does not cover every available MP4 exactly once")
    if (
        report.get("seam_pass_count")
        != sum(item.get("seam_status") == "pass" for item in videos)
        or report.get("fidelity_pass_count")
        != sum(item.get("fidelity_status") == "pass" for item in videos)
    ):
        raise FinalizeError("Loop review aggregate counters changed")
    return reviewed, review_sha256


def _loop_seam_summary(review: dict[str, Any]) -> tuple[str, str]:
    seam_status = review["seam_status"]
    if seam_status == "pass":
        return (
            "seam-passed",
            "First/last position and boundary-motion proxy passed deterministic review.",
        )
    failed = review["seam"].get("failed_checks") or ["unspecified seam check"]
    return (
        "seam-failed",
        "Deterministic seam review failed: " + ", ".join(str(item) for item in failed),
    )


def build_loop_experiment(root: Path = ROOT) -> dict[str, Any] | None:
    validated = _validated_loop_source(root)
    if validated is None:
        return None
    experiment, inventory = validated
    if not _loop_is_complete(experiment):
        return None

    route = loop_experiment.validate_route()
    entries_by_variant = {
        item["variant_id"]: item for item in inventory.get("entries", [])
    }
    planning_by_variant = {
        item["variant_id"]: item
        for item in experiment.get("planning_variants", [])
        if isinstance(item, dict) and isinstance(item.get("variant_id"), str)
    }
    if (
        set(entries_by_variant) != set(loop_experiment.VARIANT_BY_ID)
        or set(planning_by_variant) != set(loop_experiment.VARIANT_BY_ID)
    ):
        raise FinalizeError("Loop inventory or planning variant matrix changed")

    attempts: list[dict[str, Any]] = []
    available: list[dict[str, Any]] = []
    with loop_experiment.configured_native(root):
        for attempt_number, raw_output in enumerate(experiment["outputs"], start=1):
            if not isinstance(raw_output, dict):
                raise FinalizeError("Loop generation output is not an object")
            variant_id = raw_output.get("variant_id")
            entry = loop_experiment.ENTRY_BY_VARIANT.get(str(variant_id))
            inventory_entry = entries_by_variant.get(str(variant_id))
            planning_variant = planning_by_variant.get(str(variant_id))
            if (
                entry is None
                or not isinstance(inventory_entry, dict)
                or not isinstance(planning_variant, dict)
            ):
                raise FinalizeError(f"Unknown loop variant: {variant_id!r}")
            job = loop_experiment.load_experiment_job(entry, root)
            paths = loop_experiment.artifact_paths(entry, root)
            expected_paths = {
                "prompt_path": _relative(paths["prompt"], root),
                "run_path": _relative(paths["run"], root),
                "video_path": _relative(paths["video"], root),
            }
            expected_identity = {
                "lite_run_id": entry.planning_run_id,
                "provider_run_id": loop_experiment._provider_run_id(entry),  # noqa: SLF001
                "sample_id": entry.sample.sample_id,
                "article_slug": case21.ARTICLE_SLUG,
                "source_path": case21.SOURCE_PATH.as_posix(),
                "model_id": loop_experiment.MODEL_ID,
                "variant_id": variant_id,
                "stage": inventory_entry.get("stage"),
                **expected_paths,
            }
            if any(raw_output.get(key) != value for key, value in expected_identity.items()):
                raise FinalizeError(f"Loop aggregate identity changed for {variant_id}")

            prompt = read_json(paths["prompt"])
            expected_prompt = loop_experiment.loop_prompt_artifact(job)
            if prompt != expected_prompt:
                raise FinalizeError(f"Loop prompt differs from verified Lite plan: {variant_id}")
            positive = job.positive_prompt
            negative = job.negative_prompt
            if (
                inventory_entry.get("planning_result_sha256") != job.result_sha256
                or planning_variant.get("result_sha256") != job.result_sha256
                or inventory_entry.get("positive_prompt_sha256")
                != _sha256_text(positive)
                or inventory_entry.get("negative_prompt_sha256")
                != (_sha256_text(negative) if negative else None)
            ):
                raise FinalizeError(f"Loop planning or prompt SHA changed for {variant_id}")

            run = read_json(paths["run"])
            initial = loop_experiment.loop_initial_run(job, paths, root)
            immutable_run_keys = (
                "schema_version",
                "ticket",
                "sample_id",
                "image_id",
                "model_id",
                "adapter",
                "prompt_path",
                "output_path",
                "batch_id",
                "agent_id",
                "lite_run_id",
                "provider_run_id",
                "lite_result_sha256",
                "provider_transport_experiment",
            )
            if (
                not isinstance(run, dict)
                or any(run.get(key) != initial.get(key) for key in immutable_run_keys)
                or any(run.get(key) for key in ("retry_of", "retry_count", "attempts"))
            ):
                raise FinalizeError(f"Loop run identity changed for {variant_id}")
            expected_request = loop_experiment.native.provider_request_preview(
                loop_experiment.provider_sample(entry),
                loop_experiment.loop_provider_prompt(job),
            )
            loop_experiment.assert_loop_request(entry, expected_request, job)
            request_sha256 = transport.request_fingerprint(
                expected_request,
                loop_experiment.provider_sample(entry),
            )
            frames = expected_request.get("frame_images")
            frame_types = tuple(
                item.get("frame_type") for item in frames if isinstance(item, dict)
            ) if isinstance(frames, list) else ()
            frame_urls = tuple(
                (item.get("image_url") or {}).get("url")
                for item in frames
                if isinstance(item, dict)
            ) if isinstance(frames, list) else ()
            if (
                run.get("request") != expected_request
                or run.get("request_fingerprint_version")
                != loop_experiment.REQUEST_FINGERPRINT_VERSION
                or run.get("request_sha256") != request_sha256
                or inventory_entry.get("request_sha256") != request_sha256
                or frame_types != LOOP_FRAME_TYPES
                or frame_urls != (loop_experiment.SOURCE_URL, loop_experiment.SOURCE_URL)
                or inventory_entry.get("first_frame_url") != loop_experiment.SOURCE_URL
                or inventory_entry.get("last_frame_url") != loop_experiment.SOURCE_URL
            ):
                raise FinalizeError(f"Loop request or endpoint URL changed for {variant_id}")

            recorded_status = run.get("status")
            status = native.effective_run_status(run)
            if status in LOOP_INCOMPLETE_STATUSES or run.get("provider_may_be_active") is True:
                raise FinalizeError(f"Loop attempt is not terminal: {variant_id} ({status})")
            mirrored = {
                "recorded_status": recorded_status,
                "status": status,
                "provider_may_be_active": run.get("provider_may_be_active"),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
                "provider_transport_experiment": loop_experiment.TRANSPORT_EXPERIMENT,
            }
            if any(raw_output.get(key) != value for key, value in mirrored.items()):
                raise FinalizeError(f"Loop aggregate differs from run receipt: {variant_id}")

            video_path = paths["video"]
            has_available_status = status in LOOP_AVAILABLE_STATUSES
            video_is_safe = video_path.is_file() and not video_path.is_symlink()
            media = run.get("media")
            if has_available_status != (video_is_safe and isinstance(media, dict)):
                raise FinalizeError(f"Loop MP4 availability changed for {variant_id}")
            video_sha256: str | None = None
            if has_available_status:
                video_sha256 = sha256_file(video_path)
                if (
                    media.get("sha256") != video_sha256
                    or media.get("bytes") != video_path.stat().st_size
                ):
                    raise FinalizeError(f"Loop MP4 SHA or byte count changed for {variant_id}")

            attempt = {
                "activity": "loop-closure-experiment",
                "experiment_id": loop_experiment.EXPERIMENT_ID,
                "variant_id": variant_id,
                "stage": raw_output.get("stage"),
                "batch_id": loop_experiment.PROVIDER_BATCH_ID,
                "provider_run_id": run.get("provider_run_id"),
                "lite_run_id": run.get("lite_run_id"),
                "sample_id": run.get("sample_id"),
                "model_id": run.get("model_id"),
                "status": status,
                "recorded_status": recorded_status,
                "provider_may_be_active": run.get("provider_may_be_active"),
                "request_sha256": request_sha256,
                "request_fingerprint_version": loop_experiment.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": run.get("provider_job_id"),
                "submitted_at": run.get("submitted_at"),
                "completed_at": run.get("completed_at"),
                **expected_paths,
                "prompt_sha256": sha256_file(paths["prompt"]),
                "run_sha256": sha256_file(paths["run"]),
                "video_sha256": video_sha256,
                "available_video": has_available_status,
                "selected_for_display": has_available_status,
                "selected_for_acceptance": False,
                "experiment_attempt_number": attempt_number,
                "error": run.get("error"),
            }
            attempts.append(attempt)
            if has_available_status:
                available.append(
                    {
                        "variant_id": variant_id,
                        "entry": entry,
                        "job": job,
                        "raw_output": raw_output,
                        "run": run,
                        "media": media,
                        "video_path": expected_paths["video_path"],
                        "video_sha256": video_sha256,
                        "prompt_path": expected_paths["prompt_path"],
                        "run_path": expected_paths["run_path"],
                        "prompt_sha256": attempt["prompt_sha256"],
                        "run_sha256": attempt["run_sha256"],
                        "request_sha256": request_sha256,
                        "attempt_number": attempt_number,
                        "planning_variant": planning_variant,
                    }
                )

    reviewed, review_sha256 = _validated_loop_review(root, available)
    outputs: list[dict[str, Any]] = []
    for item in available:
        variant_id = item["variant_id"]
        review = reviewed[variant_id]
        seam_status, seam_summary = _loop_seam_summary(review)
        motion_failed = review.get("fidelity_status") != "pass"
        motion_summary = (
            f"Deterministic ROI review detected motion in "
            f"{review.get('regions_with_detected_motion', 0)} of "
            f"{review.get('requested_region_count', len(LOOP_REGION_IDS))} requested regions; "
            "semantic direction and battery color order still require human review."
        )
        run = item["run"]
        outputs.append(
            {
                "article_slug": case21.ARTICLE_SLUG,
                "image_id": case21.IMAGE_ID,
                "source_path": case21.SOURCE_PATH.as_posix(),
                "sample_id": item["entry"].sample.sample_id,
                "lite_run_id": item["entry"].planning_run_id,
                "provider_run_id": run.get("provider_run_id"),
                "model_id": loop_experiment.MODEL_ID,
                "positive_prompt": item["job"].positive_prompt,
                "negative_prompt": item["job"].negative_prompt,
                "status": native.effective_run_status(run),
                "recorded_status": run.get("status"),
                "available": True,
                "accepted": False,
                "availability_status": "available-for-loop-research-display",
                "acceptance_status": "research-only-human-review-required",
                "prompt_path": item["prompt_path"],
                "run_path": item["run_path"],
                "video_path": item["video_path"],
                "delivery": "repository-raw",
                "repository_raw_url": PUBLIC_RAW_BASE
                + quote(item["video_path"], safe="/"),
                "route": {
                    "adapter": route["adapter"],
                    "transport": route["transport"],
                    "provider": route["provider_key"],
                    "capacity": route["capacity"],
                    "route_substitution": False,
                },
                "route_label": "Atlas Cloud · API first/last conditioning",
                "media": item["media"],
                "contract_check": run.get("contract_check"),
                "visual_review": {
                    "status": "fidelity-failed" if motion_failed else "fidelity-passed",
                    "summary": motion_summary,
                    "human_semantic_review_complete": False,
                },
                "review_path": LOOP_REVIEW_PATH.as_posix(),
                "selection": {
                    "activity": "loop-closure-experiment",
                    "experiment_id": loop_experiment.EXPERIMENT_ID,
                    "variant_id": variant_id,
                    "variant_label": item["planning_variant"].get("strategy"),
                    "purpose": "point-animation-and-loop-closure-research",
                },
                "loop_closure": {
                    "request_sha256": item["request_sha256"],
                    "request_fingerprint_version": loop_experiment.REQUEST_FINGERPRINT_VERSION,
                    "frame_types": list(LOOP_FRAME_TYPES),
                    "first_frame_url": loop_experiment.SOURCE_URL,
                    "last_frame_url": loop_experiment.SOURCE_URL,
                    "same_source_for_endpoints": True,
                    "provider_native_loop_parameter": False,
                    "browser_playback_loop": True,
                    "prompt_sha256": item["prompt_sha256"],
                    "run_sha256": item["run_sha256"],
                    "video_sha256": item["video_sha256"],
                    "review_sha256": review_sha256,
                    "seam_review": {
                        "status": seam_status,
                        "summary": seam_summary,
                        "analysis_status": review.get("seam_status"),
                        "failed_checks": review["seam"].get("failed_checks"),
                    },
                    "motion_review": {
                        "status": review.get("fidelity_status"),
                        "requested_region_count": review.get("requested_region_count"),
                        "regions_with_detected_motion": review.get(
                            "regions_with_detected_motion"
                        ),
                        "missing_motion_regions": review.get("missing_motion_regions"),
                    },
                },
                "error": run.get("error"),
            }
        )

    cost = experiment["cost"]
    endpoint_base = route["default_base_url"].rstrip("/")
    return {
        "schema_version": 1,
        "experiment_id": loop_experiment.EXPERIMENT_ID,
        "model_id": loop_experiment.MODEL_ID,
        "agent_id": AGENT_ID,
        "updated_at": experiment["updated_at"],
        "request_contract": {
            "classification": "api-loop-closure-experiment",
            "verified_lite_planning": True,
            "canonical_lite_runtime": False,
            "mechanism": "same-source-first-and-last-frame",
            "request_mechanism": "same-source-first-and-last-frame",
            "last_frame_is_source": True,
            "same_source_for_endpoints": True,
            "provider_native_loop_parameter": False,
            "browser_playback_loop": True,
            "frame_types": list(LOOP_FRAME_TYPES),
            "first_frame_url": loop_experiment.SOURCE_URL,
            "last_frame_url": loop_experiment.SOURCE_URL,
            "provider_api_base_url": route["default_base_url"],
            "provider_submit_url": endpoint_base + route["paths"]["submit"],
            "provider_status_url_template": endpoint_base
            + route["paths"]["status_template"],
            "provider_content_url_template": endpoint_base
            + route["paths"]["content_template"],
        },
        "cost": {
            "currency": "USD",
            "operator_budget_cap_usd": cost["operator_budget_cap_usd"],
            "reserved_usd": cost["initial_reserved_usd"],
            "reservation_per_output_usd": cost[
                "reservation_per_wan27_entry_usd"
            ],
            "automatic_paid_retries": False,
            "actual_billing_available": False,
            "reservation_kind": "conservative-operator-envelope",
            "note": cost["note"],
        },
        "attempt_count": len(attempts),
        "attempts_without_video_count": len(attempts) - len(outputs),
        "available_output_count": len(outputs),
        "accepted_output_count": 0,
        "source": experiment["source"],
        "source_manifests": {
            "inventory": loop_experiment.INVENTORY_PATH.as_posix(),
            "generation": loop_experiment.GENERATION_MANIFEST_PATH.as_posix(),
            "experiment": loop_experiment.EXPERIMENT_MANIFEST_PATH.as_posix(),
            "review": LOOP_REVIEW_PATH.as_posix() if review_sha256 else None,
        },
        "receipt_sha256": {
            "experiment_manifest": sha256_file(
                root / loop_experiment.EXPERIMENT_MANIFEST_PATH
            ),
            "inventory": sha256_file(root / loop_experiment.INVENTORY_PATH),
            "generation": sha256_file(
                root / loop_experiment.GENERATION_MANIFEST_PATH
            ),
            "review": review_sha256 or None,
        },
        "attempt_history": attempts,
        "outputs": outputs,
    }


def _validated_smooth_source(
    root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
] | None:
    """Return exact smooth receipts, or ``None`` when the series is absent."""

    manifest_path = root / smooth_experiment.EXPERIMENT_MANIFEST_PATH
    if not manifest_path.exists():
        return None
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise FinalizeError(f"Smooth experiment manifest is unsafe: {manifest_path}")
    experiment = read_json(manifest_path)
    if not isinstance(experiment, dict):
        raise FinalizeError("Smooth experiment manifest is not an object")
    updated_at = experiment.get("updated_at")
    cost = experiment.get("cost")
    budget = cost.get("operator_budget_cap_usd") if isinstance(cost, dict) else None
    if (
        experiment.get("manifest_role")
        != "case-21-wan27-smooth-experiment"
        or experiment.get("ticket") != TICKET
        or experiment.get("experiment_id") != smooth_experiment.EXPERIMENT_ID
        or experiment.get("provider_batch_id")
        != smooth_experiment.PROVIDER_BATCH_ID
        or experiment.get("agent_id") != AGENT_ID
        or not isinstance(updated_at, str)
        or not updated_at.strip()
        or not isinstance(budget, (int, float))
        or isinstance(budget, bool)
        or float(budget) != float(smooth_experiment.HARD_BUDGET_CAP_USD)
        or not isinstance(cost, dict)
        or cost.get("initial_reserved_usd") != float(smooth_retry.BASE_RESERVED_USD)
        or cost.get("reservation_per_wan27_entry_usd")
        != float(smooth_experiment.RESERVATION_PER_ENTRY_USD)
        or cost.get("admitted_provider_entries")
        != smooth_experiment.INITIAL_ENTRY_COUNT
        or cost.get("contingency_entries_materialized") != 0
        or cost.get("automatic_paid_retries") is not False
        or cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Smooth experiment identity or separate budget changed")
    expected = smooth_experiment._experiment_document(  # noqa: SLF001
        str(budget),
        root,
        updated_at=updated_at,
    )
    if experiment != expected:
        raise FinalizeError(
            "Smooth experiment manifest differs from exact inventory and run receipts"
        )
    inventory_path = root / smooth_experiment.INVENTORY_PATH
    if not inventory_path.is_file() or inventory_path.is_symlink():
        raise FinalizeError(f"Smooth inventory path is unsafe: {inventory_path}")
    inventory = read_json(inventory_path)
    expected_inventory = smooth_experiment.inventory_document(str(budget), root)
    if inventory != expected_inventory:
        raise FinalizeError(
            "Smooth inventory differs from exact Lite plans and first-frame requests"
        )
    retry_manifest_path = root / smooth_retry.EXPERIMENT_MANIFEST_PATH
    if not retry_manifest_path.is_file() or retry_manifest_path.is_symlink():
        raise FinalizeError(
            f"Completed smooth base series requires explicit retry receipt "
            f"{smooth_retry.EXPERIMENT_MANIFEST_PATH}"
        )
    retry = read_json(retry_manifest_path)
    if not isinstance(retry, dict):
        raise FinalizeError("Smooth explicit retry manifest is not an object")
    retry_updated_at = retry.get("updated_at")
    retry_cost = retry.get("cost")
    retry_budget = (
        retry_cost.get("operator_budget_cap_usd")
        if isinstance(retry_cost, dict)
        else None
    )
    if (
        retry.get("manifest_role")
        != "case-21-wan27-smooth-explicit-retry"
        or retry.get("ticket") != TICKET
        or retry.get("retry_id") != smooth_retry.RETRY_ID
        or retry.get("provider_batch_id") != smooth_retry.PROVIDER_BATCH_ID
        or retry.get("agent_id") != AGENT_ID
        or retry.get("retry_of") != smooth_retry.RETRY_OF_PROVIDER_RUN_ID
        or retry.get("supersedes_for_demo")
        != smooth_retry.SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID
        or retry.get("initial_four_receipts_immutable") is not True
        or not isinstance(retry_updated_at, str)
        or not retry_updated_at.strip()
        or not isinstance(retry_budget, (int, float))
        or isinstance(retry_budget, bool)
        or float(retry_budget) != float(smooth_retry.HARD_BUDGET_CAP_USD)
        or not isinstance(retry_cost, dict)
        or retry_cost.get("base_reserved_usd")
        != float(smooth_retry.BASE_RESERVED_USD)
        or retry_cost.get("explicit_retry_reserved_usd")
        != float(smooth_retry.RETRY_RESERVED_USD)
        or retry_cost.get("aggregate_reserved_usd") != SMOOTH_RESERVED_USD
        or retry_cost.get("aggregate_paid_entry_count") != SMOOTH_ATTEMPT_COUNT
        or retry_cost.get("automatic_paid_retries") is not False
        or retry_cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Smooth explicit retry identity or aggregate budget changed")
    expected_retry = smooth_retry._experiment_document(  # noqa: SLF001
        str(retry_budget),
        root,
        updated_at=retry_updated_at,
    )
    if retry != expected_retry:
        raise FinalizeError(
            "Smooth explicit retry differs from exact base and retry receipts"
        )
    retry_inventory_path = root / smooth_retry.INVENTORY_PATH
    if not retry_inventory_path.is_file() or retry_inventory_path.is_symlink():
        raise FinalizeError(f"Smooth retry inventory is unsafe: {retry_inventory_path}")
    retry_inventory = read_json(retry_inventory_path)
    expected_retry_inventory = smooth_retry.inventory_document(
        str(retry_budget), root
    )
    if retry_inventory != expected_retry_inventory:
        raise FinalizeError(
            "Smooth retry inventory differs from exact Lite plan and first-frame request"
        )
    return experiment, inventory, retry, retry_inventory


def _smooth_is_complete(
    experiment: dict[str, Any],
    retry: dict[str, Any],
) -> bool:
    outputs = experiment.get("outputs")
    retry_outputs = retry.get("outputs")
    if (
        not isinstance(outputs, list)
        or len(outputs) != smooth_experiment.INITIAL_ENTRY_COUNT
        or not isinstance(retry_outputs, list)
        or len(retry_outputs) != 1
    ):
        raise FinalizeError("Smooth experiment output matrix changed")
    statuses = [
        str(output.get("status", "missing"))
        for output in [*outputs, *retry_outputs]
    ]
    return not any(status in LOOP_INCOMPLETE_STATUSES for status in statuses)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_temporal_smoothness(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise FinalizeError(f"Smooth review temporal block is missing for {label}")
    energy = value.get("motion_energy_mae_rgb")
    acceleration = value.get("acceleration_proxy_mae_rgb")
    if (
        not isinstance(value.get("transition_count"), int)
        or value["transition_count"] < 1
        or not isinstance(energy, dict)
        or not isinstance(acceleration, dict)
    ):
        raise FinalizeError(f"Smooth review temporal identity changed for {label}")
    energy_numbers = (
        "mean",
        "median",
        "p90",
        "p95",
        "max",
        "mad",
        "spike_threshold",
        "spike_ratio",
    )
    acceleration_numbers = (
        "mean",
        "median",
        "p90",
        "p95",
        "max",
        "mad",
        "abrupt_threshold",
        "abrupt_transition_ratio",
        "normalized_p95_by_motion_p95",
    )
    if (
        any(not _is_number(energy.get(key)) for key in energy_numbers)
        or not isinstance(energy.get("spike_count"), int)
        or not isinstance(energy.get("spike_frame_indices"), list)
        or any(not isinstance(item, int) for item in energy["spike_frame_indices"])
        or any(not _is_number(acceleration.get(key)) for key in acceleration_numbers)
        or not isinstance(acceleration.get("sample_count"), int)
        or not isinstance(acceleration.get("abrupt_transition_count"), int)
        or not isinstance(acceleration.get("abrupt_frame_indices"), list)
        or any(
            not isinstance(item, int)
            for item in acceleration["abrupt_frame_indices"]
        )
        or not 0 <= float(energy["spike_ratio"]) <= 1
        or not 0 <= float(acceleration["abrupt_transition_ratio"]) <= 1
    ):
        raise FinalizeError(f"Smooth review temporal metrics changed for {label}")


def _validated_smooth_review(
    root: Path,
    available: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], str]:
    review_path = root / SMOOTH_REVIEW_PATH
    if len(available) != SMOOTH_ATTEMPT_COUNT:
        raise FinalizeError("Smooth publication requires exactly five available MP4s")
    if not review_path.is_file() or review_path.is_symlink():
        raise FinalizeError(f"Completed smooth MP4s require {SMOOTH_REVIEW_PATH}")
    review_sha256 = sha256_file(review_path)
    report = read_json(review_path)
    if not isinstance(report, dict):
        raise FinalizeError("Smooth review report is not an object")
    case = report.get("case")
    analyzer = report.get("analyzer")
    method = report.get("method")
    requested_regions = (
        method.get("requested_regions") if isinstance(method, dict) else None
    )
    videos = report.get("videos")
    ranking = report.get("ranking")
    ranking_entries = (
        ranking.get("entries") if isinstance(ranking, dict) else None
    )
    if (
        report.get("schema_version") != SMOOTH_REVIEW_SCHEMA_VERSION
        or case
        != {
            "article_number": "21",
            "article_slug": case21.ARTICLE_SLUG,
            "image_id": case21.IMAGE_ID,
            "model_id": smooth_experiment.MODEL_ID,
            "experiment_id": smooth_experiment.EXPERIMENT_ID,
        }
        or not isinstance(analyzer, dict)
        or analyzer.get("script")
        != "scripts/analyze_clipmaker_lite_case21_smooth.py"
        or analyzer.get("analysis_version") != 1
        or not isinstance(method, dict)
        or any(
            key not in method
            for key in (
                "temporal_sampling",
                "coverage_sampling",
                "jerkiness_proxies",
                "collateral_thresholds",
            )
        )
        or not isinstance(requested_regions, list)
        or tuple(
            item.get("region_id")
            for item in requested_regions
            if isinstance(item, dict)
        )
        != SMOOTH_REGION_IDS
        or report.get("video_count") != SMOOTH_ATTEMPT_COUNT
        or not isinstance(videos, list)
        or len(videos) != SMOOTH_ATTEMPT_COUNT
        or not isinstance(ranking, dict)
        or ranking.get("method")
        != "coverage-desc-then-abrupt-acceleration-spikes-collateral-asc"
        or not isinstance(ranking_entries, list)
        or len(ranking_entries) != SMOOTH_ATTEMPT_COUNT
        or not isinstance(report.get("limitations"), list)
        or not report["limitations"]
        or "seam_pass_count" in report
        or "fidelity_pass_count" in report
    ):
        raise FinalizeError("Smooth review report identity or proxy contract changed")

    available_by_variant = {item["variant_id"]: item for item in available}
    if len(available_by_variant) != len(available):
        raise FinalizeError("Available smooth variants are duplicated")
    reviewed: dict[str, dict[str, Any]] = {}
    for video in videos:
        if not isinstance(video, dict):
            raise FinalizeError("Smooth review video entry is not an object")
        variant_id = video.get("video_id")
        expected = available_by_variant.get(str(variant_id))
        media = video.get("media")
        frame_analysis = video.get("frame_analysis")
        motion_coverage = video.get("motion_coverage")
        regions = video.get("regions")
        collateral = video.get("collateral_activity")
        proxy_rank = video.get("proxy_rank")
        if (
            expected is None
            or variant_id in reviewed
            or video.get("path") != expected["video_path"]
            or video.get("sha256") != expected["video_sha256"]
            or video.get("analysis_status") != "measured"
            or not isinstance(media, dict)
            or not isinstance(frame_analysis, dict)
            or not isinstance(motion_coverage, dict)
            or not isinstance(regions, list)
            or tuple(
                item.get("region_id") for item in regions if isinstance(item, dict)
            )
            != SMOOTH_REGION_IDS
            or any(
                not isinstance(item.get("detected_motion"), bool)
                or "temporal_smoothness" not in item
                for item in regions
                if isinstance(item, dict)
            )
            or not isinstance(collateral, dict)
            or not isinstance(proxy_rank, int)
            or isinstance(proxy_rank, bool)
            or not 1 <= proxy_rank <= SMOOTH_ATTEMPT_COUNT
            or "seam" in video
            or "seam_status" in video
            or "fidelity_status" in video
        ):
            raise FinalizeError(f"Smooth review binding changed for {variant_id!r}")
        detected_regions = [
            item["region_id"] for item in regions if item["detected_motion"]
        ]
        missing_regions = [
            item["region_id"] for item in regions if not item["detected_motion"]
        ]
        if (
            motion_coverage.get("requested_region_count") != len(SMOOTH_REGION_IDS)
            or motion_coverage.get("regions_with_detected_motion")
            != len(detected_regions)
            or motion_coverage.get("missing_motion_regions") != missing_regions
            or not _is_number(motion_coverage.get("coverage_ratio"))
            or abs(
                float(motion_coverage["coverage_ratio"])
                - len(detected_regions) / len(SMOOTH_REGION_IDS)
            )
            > 1e-6
            or not isinstance(frame_analysis.get("decoded_frame_count"), int)
            or not _is_number(frame_analysis.get("normalized_width"))
            or not _is_number(frame_analysis.get("normalized_height"))
            or not isinstance(frame_analysis.get("coverage_frame_indices"), list)
            or not isinstance(frame_analysis.get("coverage_timestamps_seconds"), list)
            or len(frame_analysis["coverage_frame_indices"])
            != len(frame_analysis["coverage_timestamps_seconds"])
        ):
            raise FinalizeError(
                f"Smooth review coverage counters changed for {variant_id}"
            )
        for region in regions:
            _validate_temporal_smoothness(
                region["temporal_smoothness"],
                f"{variant_id}/{region['region_id']}",
            )
        _validate_temporal_smoothness(
            video.get("requested_union_smoothness"),
            f"{variant_id}/requested-union",
        )
        _validate_temporal_smoothness(
            collateral.get("temporal_smoothness"),
            f"{variant_id}/collateral",
        )
        if (
            not isinstance(collateral.get("outside_requested_region_pixel_count"), int)
            or not _is_number(collateral.get("max_mae_rgb_from_first"))
            or not _is_number(collateral.get("max_changed_pixel_ratio_from_first"))
            or not isinstance(video.get("square_output"), bool)
        ):
            raise FinalizeError(
                f"Smooth review collateral metrics changed for {variant_id}"
            )
        run_media = expected["media"]
        try:
            frame_rate = float(Fraction(str(media.get("frame_rate"))))
        except (ValueError, ZeroDivisionError) as exc:
            raise FinalizeError(
                f"Smooth review frame rate is invalid for {variant_id}"
            ) from exc
        media_matches = (
            media.get("width") == run_media.get("width")
            and media.get("height") == run_media.get("height")
            and media.get("codec") == run_media.get("codec")
            and media.get("container") == run_media.get("container")
            and media.get("has_audio") == run_media.get("has_audio")
            and media.get("bytes") == run_media.get("bytes")
            and abs(
                float(media.get("duration_seconds") or 0)
                - float(run_media.get("duration_seconds") or 0)
            )
            <= 0.1
            and (
                run_media.get("fps") is None
                or abs(frame_rate - float(run_media["fps"])) <= 0.001
            )
            and (
                run_media.get("frames") is None
                or media.get("frame_count") == run_media.get("frames")
            )
            and frame_analysis.get("decoded_frame_count") == media.get("frame_count")
        )
        if not media_matches:
            raise FinalizeError(f"Smooth review media changed for {variant_id}")
        reviewed[str(variant_id)] = video
    if set(reviewed) != set(available_by_variant):
        raise FinalizeError(
            "Smooth review does not cover every available MP4 exactly once"
        )

    ranking_by_variant: dict[str, dict[str, Any]] = {}
    ranking_keys = {
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
    }
    for entry in ranking_entries:
        if not isinstance(entry, dict):
            raise FinalizeError("Smooth ranking entry is not an object")
        variant_id = entry.get("video_id")
        reviewed_video = reviewed.get(str(variant_id))
        coverage = (
            reviewed_video.get("motion_coverage")
            if isinstance(reviewed_video, dict)
            else None
        )
        union = (
            reviewed_video.get("requested_union_smoothness")
            if isinstance(reviewed_video, dict)
            else None
        )
        energy = union.get("motion_energy_mae_rgb") if isinstance(union, dict) else None
        acceleration = (
            union.get("acceleration_proxy_mae_rgb")
            if isinstance(union, dict)
            else None
        )
        collateral = (
            reviewed_video.get("collateral_activity")
            if isinstance(reviewed_video, dict)
            else None
        )
        if (
            set(entry) != ranking_keys
            or reviewed_video is None
            or variant_id in ranking_by_variant
            or entry.get("rank") != reviewed_video["proxy_rank"]
            or not isinstance(coverage, dict)
            or not isinstance(energy, dict)
            or not isinstance(acceleration, dict)
            or not isinstance(collateral, dict)
            or entry.get("regions_with_detected_motion")
            != coverage.get("regions_with_detected_motion")
            or entry.get("coverage_ratio") != coverage.get("coverage_ratio")
            or entry.get("abrupt_transition_count")
            != acceleration.get("abrupt_transition_count")
            or entry.get("abrupt_transition_ratio")
            != acceleration.get("abrupt_transition_ratio")
            or entry.get("motion_energy_spike_count")
            != energy.get("spike_count")
            or entry.get("motion_energy_spike_ratio")
            != energy.get("spike_ratio")
            or entry.get("normalized_acceleration_p95")
            != acceleration.get("normalized_p95_by_motion_p95")
            or entry.get("collateral_max_changed_pixel_ratio_from_first")
            != collateral.get("max_changed_pixel_ratio_from_first")
        ):
            raise FinalizeError(f"Smooth ranking binding changed for {variant_id!r}")
        ranking_by_variant[str(variant_id)] = entry
    if (
        set(ranking_by_variant) != set(reviewed)
        or {video["proxy_rank"] for video in reviewed.values()}
        != set(range(1, SMOOTH_ATTEMPT_COUNT + 1))
    ):
        raise FinalizeError("Smooth proxy ranking is incomplete or duplicated")
    return reviewed, review_sha256


def build_smooth_experiment(root: Path = ROOT) -> dict[str, Any] | None:
    validated = _validated_smooth_source(root)
    if validated is None:
        return None
    experiment, inventory, retry_experiment, retry_inventory = validated
    if not _smooth_is_complete(experiment, retry_experiment):
        return None

    route = smooth_experiment.validate_route()
    entries_by_variant = {
        item["variant_id"]: item for item in inventory.get("entries", [])
    }
    planning_by_variant = {
        item["variant_id"]: item
        for item in experiment.get("planning_variants", [])
        if isinstance(item, dict) and isinstance(item.get("variant_id"), str)
    }
    expected_variants = tuple(
        variant.variant_id for variant in smooth_experiment.VARIANTS
    )
    if (
        tuple(entries_by_variant) != expected_variants
        or tuple(planning_by_variant) != expected_variants
        or tuple(
            item.get("variant_id")
            for item in experiment["outputs"]
            if isinstance(item, dict)
        )
        != expected_variants
    ):
        raise FinalizeError("Smooth inventory, planning, or output matrix changed")
    if (
        SMOOTH_REPLACED_VARIANT_ID not in entries_by_variant
        or len(expected_variants) != smooth_experiment.INITIAL_ENTRY_COUNT
    ):
        raise FinalizeError("Smooth explicit-retry matrix is incomplete")
    replaced_entry = smooth_experiment.ENTRY_BY_VARIANT[
        SMOOTH_REPLACED_VARIANT_ID
    ]
    replaced_provider_run_id = smooth_experiment._provider_run_id(  # noqa: SLF001
        replaced_entry
    )

    attempts: list[dict[str, Any]] = []
    available: list[dict[str, Any]] = []
    with smooth_experiment.configured_native(root):
        for attempt_number, raw_output in enumerate(experiment["outputs"], start=1):
            if not isinstance(raw_output, dict):
                raise FinalizeError("Smooth generation output is not an object")
            variant_id = raw_output.get("variant_id")
            entry = smooth_experiment.ENTRY_BY_VARIANT.get(str(variant_id))
            inventory_entry = entries_by_variant.get(str(variant_id))
            planning_variant = planning_by_variant.get(str(variant_id))
            if (
                entry is None
                or not isinstance(inventory_entry, dict)
                or not isinstance(planning_variant, dict)
            ):
                raise FinalizeError(f"Unknown smooth variant: {variant_id!r}")
            job = smooth_experiment.load_experiment_job(entry, root)
            paths = smooth_experiment.artifact_paths(entry, root)
            expected_paths = {
                "prompt_path": _relative(paths["prompt"], root),
                "run_path": _relative(paths["run"], root),
                "video_path": _relative(paths["video"], root),
            }
            expected_identity = {
                "lite_run_id": entry.planning_run_id,
                "provider_run_id": smooth_experiment._provider_run_id(entry),  # noqa: SLF001
                "sample_id": entry.sample.sample_id,
                "article_slug": case21.ARTICLE_SLUG,
                "source_path": case21.SOURCE_PATH.as_posix(),
                "model_id": smooth_experiment.MODEL_ID,
                "variant_id": variant_id,
                **expected_paths,
            }
            if any(
                raw_output.get(key) != value
                for key, value in expected_identity.items()
            ):
                raise FinalizeError(f"Smooth aggregate identity changed for {variant_id}")
            selected_for_demo = variant_id != SMOOTH_REPLACED_VARIANT_ID
            if variant_id == SMOOTH_REPLACED_VARIANT_ID:
                expected_human_review = {
                    "reviewer": SMOOTH_REVIEWER,
                    "status": "excluded",
                    "reason_code": SMOOTH_EXCLUDED_REASON,
                    "note": SMOOTH_INITIAL_EXCLUSION_NOTE,
                }
            else:
                expected_human_review = {
                    "reviewer": SMOOTH_REVIEWER,
                    "status": "accepted",
                    "reason_code": SMOOTH_ACCEPTED_REASON,
                    "note": SMOOTH_DEFAULT_ACCEPTANCE_NOTE,
                }
            expected_retry_of = None
            if any(
                raw_output.get(key) is not None
                for key in (
                    "selected_for_demo",
                    "human_review",
                    "retry_of",
                    "supersedes_for_demo",
                )
            ):
                raise FinalizeError(
                    f"Smooth base receipt unexpectedly contains selection data: {variant_id}"
                )

            prompt = read_json(paths["prompt"])
            expected_prompt = smooth_experiment.smooth_prompt_artifact(job)
            if prompt != expected_prompt:
                raise FinalizeError(
                    f"Smooth prompt differs from verified Lite plan: {variant_id}"
                )
            positive = job.positive_prompt
            negative = job.negative_prompt
            if (
                inventory_entry.get("planning_result_sha256") != job.result_sha256
                or planning_variant.get("result_sha256") != job.result_sha256
                or inventory_entry.get("positive_prompt_sha256")
                != _sha256_text(positive)
                or inventory_entry.get("negative_prompt_sha256")
                != (_sha256_text(negative) if negative else None)
            ):
                raise FinalizeError(
                    f"Smooth planning or prompt SHA changed for {variant_id}"
                )

            run = read_json(paths["run"])
            initial = smooth_experiment.smooth_initial_run(job, paths, root)
            immutable_run_keys = (
                "schema_version",
                "ticket",
                "sample_id",
                "image_id",
                "model_id",
                "adapter",
                "prompt_path",
                "output_path",
                "batch_id",
                "agent_id",
                "lite_run_id",
                "provider_run_id",
                "lite_result_sha256",
                "provider_transport_experiment",
            )
            if (
                not isinstance(run, dict)
                or any(run.get(key) != initial.get(key) for key in immutable_run_keys)
                or any(run.get(key) for key in ("retry_of", "retry_count", "attempts"))
            ):
                raise FinalizeError(f"Smooth run identity changed for {variant_id}")
            expected_request = smooth_experiment.native.provider_request_preview(
                smooth_experiment.provider_sample(entry),
                smooth_experiment.smooth_provider_prompt(job),
            )
            smooth_experiment.assert_smooth_request(entry, expected_request, job)
            request_sha256 = transport.request_fingerprint(
                expected_request,
                smooth_experiment.provider_sample(entry),
            )
            frames = expected_request.get("frame_images")
            frame_types = tuple(
                item.get("frame_type")
                for item in frames
                if isinstance(item, dict)
            ) if isinstance(frames, list) else ()
            frame_urls = tuple(
                (item.get("image_url") or {}).get("url")
                for item in frames
                if isinstance(item, dict)
            ) if isinstance(frames, list) else ()
            if (
                run.get("request") != expected_request
                or run.get("request_fingerprint_version")
                != smooth_experiment.REQUEST_FINGERPRINT_VERSION
                or run.get("request_sha256") != request_sha256
                or inventory_entry.get("request_sha256") != request_sha256
                or inventory_entry.get("request_fingerprint_version")
                != smooth_experiment.REQUEST_FINGERPRINT_VERSION
                or inventory_entry.get("frame_inputs") != ["first_frame"]
                or inventory_entry.get("source_url") != smooth_experiment.SOURCE_URL
                or frame_types != SMOOTH_FRAME_TYPES
                or frame_urls != (smooth_experiment.SOURCE_URL,)
                or "loop" in expected_request
                or any(frame_type == "last_frame" for frame_type in frame_types)
            ):
                raise FinalizeError(
                    f"Smooth request is not exact first-frame-only: {variant_id}"
                )

            recorded_status = run.get("status")
            status = native.effective_run_status(run)
            if status in LOOP_INCOMPLETE_STATUSES or run.get("provider_may_be_active") is True:
                raise FinalizeError(
                    f"Smooth attempt is not terminal: {variant_id} ({status})"
                )
            mirrored = {
                "recorded_status": recorded_status,
                "status": status,
                "provider_may_be_active": run.get("provider_may_be_active"),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
                "provider_transport_experiment": dict(
                    smooth_experiment.TRANSPORT_PROFILE
                ),
            }
            if any(raw_output.get(key) != value for key, value in mirrored.items()):
                raise FinalizeError(
                    f"Smooth aggregate differs from run receipt: {variant_id}"
                )

            video_path = paths["video"]
            has_available_status = status in LOOP_AVAILABLE_STATUSES
            video_is_safe = video_path.is_file() and not video_path.is_symlink()
            media = run.get("media")
            if has_available_status != (video_is_safe and isinstance(media, dict)):
                raise FinalizeError(f"Smooth MP4 availability changed for {variant_id}")
            video_sha256: str | None = None
            if has_available_status:
                video_sha256 = sha256_file(video_path)
                if (
                    media.get("sha256") != video_sha256
                    or media.get("bytes") != video_path.stat().st_size
                ):
                    raise FinalizeError(
                        f"Smooth MP4 SHA or byte count changed for {variant_id}"
                    )

            attempt = {
                "activity": "smooth-motion-experiment",
                "experiment_id": smooth_experiment.EXPERIMENT_ID,
                "variant_id": variant_id,
                "batch_id": smooth_experiment.PROVIDER_BATCH_ID,
                "provider_run_id": run.get("provider_run_id"),
                "lite_run_id": run.get("lite_run_id"),
                "sample_id": run.get("sample_id"),
                "model_id": run.get("model_id"),
                "status": status,
                "recorded_status": recorded_status,
                "provider_may_be_active": run.get("provider_may_be_active"),
                "request_sha256": request_sha256,
                "request_fingerprint_version": smooth_experiment.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": run.get("provider_job_id"),
                "submitted_at": run.get("submitted_at"),
                "completed_at": run.get("completed_at"),
                **expected_paths,
                "prompt_sha256": sha256_file(paths["prompt"]),
                "run_sha256": sha256_file(paths["run"]),
                "video_sha256": video_sha256,
                "available_video": has_available_status,
                "selected_for_demo": has_available_status and selected_for_demo,
                "selected_for_display": has_available_status and selected_for_demo,
                "selected_for_acceptance": False,
                "human_review": expected_human_review,
                "retry_of": expected_retry_of,
                "supersedes_for_demo": expected_retry_of,
                "experiment_attempt_number": attempt_number,
                "error": run.get("error"),
            }
            attempts.append(attempt)
            if has_available_status:
                available.append(
                    {
                        "variant_id": variant_id,
                        "entry": entry,
                        "job": job,
                        "run": run,
                        "media": media,
                        "video_path": expected_paths["video_path"],
                        "video_sha256": video_sha256,
                        "prompt_path": expected_paths["prompt_path"],
                        "run_path": expected_paths["run_path"],
                        "prompt_sha256": attempt["prompt_sha256"],
                        "run_sha256": attempt["run_sha256"],
                        "request_sha256": request_sha256,
                        "attempt_number": attempt_number,
                        "planning_variant": planning_variant,
                        "selected_for_demo": selected_for_demo,
                        "human_review": expected_human_review,
                        "retry_of": expected_retry_of,
                        "supersedes_for_demo": expected_retry_of,
                    }
                )

    retry_raw_output = retry_experiment["outputs"][0]
    retry_inventory_entry = retry_inventory["entries"][0]
    retry_planning = retry_experiment.get("planning")
    retry_entry = smooth_retry.ENTRY
    retry_variant_id = smooth_retry.SAMPLE.variant_id
    if (
        retry_variant_id != SMOOTH_RETRY_VARIANT_ID
        or not isinstance(retry_raw_output, dict)
        or not isinstance(retry_inventory_entry, dict)
        or not isinstance(retry_planning, dict)
    ):
        raise FinalizeError("Smooth explicit retry matrix changed")
    with smooth_retry.configured_native(root):
        retry_job = smooth_retry.load_retry_job(retry_entry, root)
        retry_paths = smooth_retry.artifact_paths(retry_entry, root)
        retry_expected_paths = {
            "prompt_path": _relative(retry_paths["prompt"], root),
            "run_path": _relative(retry_paths["run"], root),
            "video_path": _relative(retry_paths["video"], root),
        }
        retry_identity = {
            "lite_run_id": smooth_retry.PLANNING_RUN_ID,
            "provider_run_id": smooth_retry._provider_run_id(),  # noqa: SLF001
            "sample_id": smooth_retry.SAMPLE.sample_id,
            "article_slug": case21.ARTICLE_SLUG,
            "source_path": case21.SOURCE_PATH.as_posix(),
            "model_id": smooth_retry.MODEL_ID,
            "variant_id": SMOOTH_RETRY_VARIANT_ID,
            "retry_of": replaced_provider_run_id,
            "supersedes_for_demo": replaced_provider_run_id,
            **retry_expected_paths,
        }
        if any(
            retry_raw_output.get(key) != value
            for key, value in retry_identity.items()
        ):
            raise FinalizeError("Smooth explicit retry aggregate identity changed")
        if (
            retry_experiment.get("retry_of") != replaced_provider_run_id
            or retry_experiment.get("supersedes_for_demo")
            != replaced_provider_run_id
            or retry_inventory_entry.get("retry_of") != replaced_provider_run_id
            or retry_inventory_entry.get("supersedes_for_demo")
            != replaced_provider_run_id
            or retry_planning.get("planning_run_id")
            != smooth_retry.PLANNING_RUN_ID
            or retry_planning.get("result_sha256")
            != smooth_retry.PLANNING_RESULT_SHA256
        ):
            raise FinalizeError("Smooth explicit retry linkage changed")

        retry_prompt = read_json(retry_paths["prompt"])
        expected_retry_prompt = smooth_retry.retry_prompt_artifact(retry_job)
        if retry_prompt != expected_retry_prompt:
            raise FinalizeError(
                "Smooth retry prompt differs from verified Lite repair plan"
            )
        if (
            retry_inventory_entry.get("planning_result_sha256")
            != retry_job.result_sha256
            or retry_inventory_entry.get("positive_prompt_sha256")
            != _sha256_text(retry_job.positive_prompt)
            or retry_inventory_entry.get("negative_prompt_sha256")
            != _sha256_text(retry_job.negative_prompt or "")
        ):
            raise FinalizeError("Smooth retry planning or prompt SHA changed")

        retry_run = read_json(retry_paths["run"])
        retry_initial = smooth_retry.retry_initial_run(
            retry_job, retry_paths, root
        )
        retry_immutable_run_keys = (
            "schema_version",
            "ticket",
            "sample_id",
            "image_id",
            "model_id",
            "adapter",
            "prompt_path",
            "output_path",
            "batch_id",
            "agent_id",
            "lite_run_id",
            "provider_run_id",
            "lite_result_sha256",
            "provider_transport_experiment",
            "explicit_retry",
        )
        if (
            not isinstance(retry_run, dict)
            or any(
                retry_run.get(key) != retry_initial.get(key)
                for key in retry_immutable_run_keys
            )
            or retry_run.get("explicit_retry")
            != {
                "retry_of": replaced_provider_run_id,
                "supersedes_for_demo": replaced_provider_run_id,
            }
            or any(
                retry_run.get(key) for key in ("retry_count", "attempts")
            )
        ):
            raise FinalizeError("Smooth explicit retry run identity changed")
        retry_expected_request = smooth_retry.native.provider_request_preview(
            smooth_retry.provider_sample(retry_entry),
            smooth_retry.retry_provider_prompt(retry_job),
        )
        smooth_retry.assert_retry_request(
            retry_entry, retry_expected_request, retry_job
        )
        retry_request_sha256 = transport.request_fingerprint(
            retry_expected_request,
            smooth_retry.provider_sample(retry_entry),
        )
        retry_frames = retry_expected_request.get("frame_images")
        retry_frame_types = tuple(
            item.get("frame_type")
            for item in retry_frames
            if isinstance(item, dict)
        ) if isinstance(retry_frames, list) else ()
        retry_frame_urls = tuple(
            (item.get("image_url") or {}).get("url")
            for item in retry_frames
            if isinstance(item, dict)
        ) if isinstance(retry_frames, list) else ()
        if (
            retry_run.get("request") != retry_expected_request
            or retry_run.get("request_fingerprint_version")
            != smooth_retry.REQUEST_FINGERPRINT_VERSION
            or retry_run.get("request_sha256") != retry_request_sha256
            or retry_inventory_entry.get("request_sha256")
            != retry_request_sha256
            or retry_inventory_entry.get("request_fingerprint_version")
            != smooth_retry.REQUEST_FINGERPRINT_VERSION
            or retry_inventory_entry.get("frame_inputs") != ["first_frame"]
            or retry_inventory_entry.get("source_url") != smooth_retry.SOURCE_URL
            or retry_frame_types != SMOOTH_FRAME_TYPES
            or retry_frame_urls != (smooth_retry.SOURCE_URL,)
            or "loop" in retry_expected_request
            or any(
                frame_type == "last_frame" for frame_type in retry_frame_types
            )
        ):
            raise FinalizeError(
                "Smooth explicit retry request is not exact first-frame-only"
            )

        retry_recorded_status = retry_run.get("status")
        retry_status = native.effective_run_status(retry_run)
        if (
            retry_status in LOOP_INCOMPLETE_STATUSES
            or retry_run.get("provider_may_be_active") is True
        ):
            raise FinalizeError(
                f"Smooth explicit retry is not terminal ({retry_status})"
            )
        retry_mirrored = {
            "recorded_status": retry_recorded_status,
            "status": retry_status,
            "provider_may_be_active": retry_run.get("provider_may_be_active"),
            "media": retry_run.get("media"),
            "contract_check": retry_run.get("contract_check"),
            "error": retry_run.get("error"),
            "provider_transport_experiment": dict(smooth_retry.TRANSPORT_PROFILE),
            "retry_of": replaced_provider_run_id,
            "supersedes_for_demo": replaced_provider_run_id,
        }
        if any(
            retry_raw_output.get(key) != value
            for key, value in retry_mirrored.items()
        ):
            raise FinalizeError("Smooth explicit retry differs from run receipt")
        retry_video_path = retry_paths["video"]
        retry_has_video = retry_status in LOOP_AVAILABLE_STATUSES
        retry_media = retry_run.get("media")
        if retry_has_video != (
            retry_video_path.is_file()
            and not retry_video_path.is_symlink()
            and isinstance(retry_media, dict)
        ):
            raise FinalizeError("Smooth explicit retry MP4 availability changed")
        retry_video_sha256: str | None = None
        if retry_has_video:
            retry_video_sha256 = sha256_file(retry_video_path)
            if (
                retry_media.get("sha256") != retry_video_sha256
                or retry_media.get("bytes") != retry_video_path.stat().st_size
            ):
                raise FinalizeError(
                    "Smooth explicit retry MP4 SHA or byte count changed"
                )
        retry_human_review = {
            "reviewer": SMOOTH_REVIEWER,
            "status": "accepted",
            "reason_code": SMOOTH_ACCEPTED_REASON,
            "note": SMOOTH_RETRY_ACCEPTANCE_NOTE,
        }
        retry_attempt = {
            "activity": "smooth-motion-explicit-retry",
            "experiment_id": smooth_retry.RETRY_ID,
            "series_experiment_id": smooth_experiment.EXPERIMENT_ID,
            "variant_id": SMOOTH_RETRY_VARIANT_ID,
            "batch_id": smooth_retry.PROVIDER_BATCH_ID,
            "provider_run_id": retry_run.get("provider_run_id"),
            "lite_run_id": retry_run.get("lite_run_id"),
            "sample_id": retry_run.get("sample_id"),
            "model_id": retry_run.get("model_id"),
            "status": retry_status,
            "recorded_status": retry_recorded_status,
            "provider_may_be_active": retry_run.get("provider_may_be_active"),
            "request_sha256": retry_request_sha256,
            "request_fingerprint_version": smooth_retry.REQUEST_FINGERPRINT_VERSION,
            "provider_job_id": retry_run.get("provider_job_id"),
            "submitted_at": retry_run.get("submitted_at"),
            "completed_at": retry_run.get("completed_at"),
            **retry_expected_paths,
            "prompt_sha256": sha256_file(retry_paths["prompt"]),
            "run_sha256": sha256_file(retry_paths["run"]),
            "video_sha256": retry_video_sha256,
            "available_video": retry_has_video,
            "selected_for_demo": retry_has_video,
            "selected_for_display": retry_has_video,
            "selected_for_acceptance": False,
            "human_review": retry_human_review,
            "retry_of": replaced_provider_run_id,
            "supersedes_for_demo": replaced_provider_run_id,
            "experiment_attempt_number": SMOOTH_ATTEMPT_COUNT,
            "error": retry_run.get("error"),
        }
        attempts.append(retry_attempt)
        if retry_has_video:
            available.append(
                {
                    "variant_id": SMOOTH_RETRY_VARIANT_ID,
                    "entry": retry_entry,
                    "job": retry_job,
                    "run": retry_run,
                    "media": retry_media,
                    "video_path": retry_expected_paths["video_path"],
                    "video_sha256": retry_video_sha256,
                    "prompt_path": retry_expected_paths["prompt_path"],
                    "run_path": retry_expected_paths["run_path"],
                    "prompt_sha256": retry_attempt["prompt_sha256"],
                    "run_sha256": retry_attempt["run_sha256"],
                    "request_sha256": retry_request_sha256,
                    "attempt_number": SMOOTH_ATTEMPT_COUNT,
                    "planning_variant": {
                        "strategy": "staggered eased motion · explicit retry",
                        "result_sha256": smooth_retry.PLANNING_RESULT_SHA256,
                    },
                    "selected_for_demo": True,
                    "human_review": retry_human_review,
                    "retry_of": replaced_provider_run_id,
                    "supersedes_for_demo": replaced_provider_run_id,
                }
            )
    if (
        len(attempts) != SMOOTH_ATTEMPT_COUNT
        or len(available) != SMOOTH_ATTEMPT_COUNT
        or sum(attempt["selected_for_display"] for attempt in attempts)
        != SMOOTH_DISPLAY_OUTPUT_COUNT
        or next(
            attempt
            for attempt in attempts
            if attempt["variant_id"] == SMOOTH_REPLACED_VARIANT_ID
        )["selected_for_display"]
        or not next(
            attempt
            for attempt in attempts
            if attempt["variant_id"] == SMOOTH_RETRY_VARIANT_ID
        )["selected_for_display"]
    ):
        raise FinalizeError(
            "Smooth publication requires five available attempts and four demo selections"
        )

    reviewed, review_sha256 = _validated_smooth_review(root, available)
    outputs: list[dict[str, Any]] = []
    for item in available:
        if not item["selected_for_demo"]:
            continue
        variant_id = item["variant_id"]
        review = reviewed[variant_id]
        coverage = review["motion_coverage"]
        motion_summary = (
            "Deterministic proxy review measured motion in "
            f"{coverage['regions_with_detected_motion']} of "
            f"{coverage['requested_region_count']} requested regions; "
            f"proxy rank {review['proxy_rank']} of "
            f"{SMOOTH_ATTEMPT_COUNT}. Semantic direction, battery "
            "color order, preservation and visual quality still require human review."
        )
        run = item["run"]
        outputs.append(
            {
                "article_slug": case21.ARTICLE_SLUG,
                "image_id": case21.IMAGE_ID,
                "source_path": case21.SOURCE_PATH.as_posix(),
                "sample_id": item["entry"].sample.sample_id,
                "lite_run_id": item["entry"].planning_run_id,
                "provider_run_id": run.get("provider_run_id"),
                "model_id": smooth_experiment.MODEL_ID,
                "positive_prompt": item["job"].positive_prompt,
                "negative_prompt": item["job"].negative_prompt,
                "status": native.effective_run_status(run),
                "recorded_status": run.get("status"),
                "available": True,
                "accepted": False,
                "availability_status": "available-for-smooth-research-display",
                "acceptance_status": "research-only-human-review-required",
                "prompt_path": item["prompt_path"],
                "run_path": item["run_path"],
                "video_path": item["video_path"],
                "delivery": "repository-raw",
                "repository_raw_url": PUBLIC_RAW_BASE
                + quote(item["video_path"], safe="/"),
                "route": {
                    "adapter": route["adapter"],
                    "transport": route["transport"],
                    "provider": route["provider_key"],
                    "capacity": route["capacity"],
                    "route_substitution": False,
                },
                "route_label": "Atlas Cloud · canonical Lite first-frame",
                "media": item["media"],
                "contract_check": run.get("contract_check"),
                "visual_review": {
                    "status": "accepted-for-demo",
                    "summary": motion_summary,
                    "human_fidelity_review_complete": True,
                    "human_semantic_review_complete": False,
                },
                "human_review": item["human_review"],
                "review_path": SMOOTH_REVIEW_PATH.as_posix(),
                "selection": {
                    "activity": "smooth-motion-experiment",
                    "experiment_id": smooth_experiment.EXPERIMENT_ID,
                    "variant_id": variant_id,
                    "variant_label": item["planning_variant"].get("strategy"),
                    "purpose": "non-loop-point-animation-research",
                    "retry_of": item["retry_of"],
                    "supersedes_for_demo": item["supersedes_for_demo"],
                },
                "smooth_motion": {
                    "request_sha256": item["request_sha256"],
                    "request_fingerprint_version": smooth_experiment.REQUEST_FINGERPRINT_VERSION,
                    "frame_types": list(SMOOTH_FRAME_TYPES),
                    "first_frame_url": smooth_experiment.SOURCE_URL,
                    "last_frame_url": None,
                    "last_frame_is_source": False,
                    "provider_native_loop_parameter": False,
                    "browser_playback_loop": False,
                    "prompt_sha256": item["prompt_sha256"],
                    "run_sha256": item["run_sha256"],
                    "video_sha256": item["video_sha256"],
                    "review_sha256": review_sha256,
                    "proxy_review": {
                        "analysis_status": review["analysis_status"],
                        "proxy_rank": review["proxy_rank"],
                        "motion_coverage": review["motion_coverage"],
                        "requested_union_smoothness": review[
                            "requested_union_smoothness"
                        ],
                        "collateral_activity": review["collateral_activity"],
                    },
                },
                "error": run.get("error"),
            }
        )

    featured_output = next(
        (
            output
            for output in outputs
            if output["selection"]["variant_id"] == SMOOTH_RETRY_VARIANT_ID
        ),
        None,
    )
    expected_featured_provider_run_id = smooth_retry._provider_run_id()  # noqa: SLF001
    if (
        not isinstance(featured_output, dict)
        or featured_output.get("provider_run_id")
        != expected_featured_provider_run_id
    ):
        raise FinalizeError(
            "Smooth featured review must bind to the selected explicit retry"
        )
    featured_proxy = reviewed[SMOOTH_RETRY_VARIANT_ID]
    featured_coverage = featured_proxy["motion_coverage"]
    featured_smoothness = featured_proxy["requested_union_smoothness"]
    featured_acceleration = featured_smoothness["acceleration_proxy_mae_rgb"]
    featured_motion_energy = featured_smoothness["motion_energy_mae_rgb"]
    if (
        featured_coverage["regions_with_detected_motion"] != 7
        or featured_coverage["requested_region_count"] != 7
        or featured_acceleration["abrupt_transition_count"] != 0
        or featured_motion_energy["spike_count"] != 0
        or featured_proxy["proxy_rank"] != 2
    ):
        raise FinalizeError(
            "Smooth featured review evidence changed; refresh the human selection"
        )
    featured_review = {
        "schema_version": SMOOTH_FEATURED_REVIEW_SCHEMA_VERSION,
        "status": SMOOTH_FEATURED_STATUS,
        "label": SMOOTH_FEATURED_LABEL,
        "reviewer": SMOOTH_FEATURED_REVIEWER,
        "selection_basis": "operator-visual-review-not-proxy-rank",
        "variant_id": SMOOTH_RETRY_VARIANT_ID,
        "provider_run_id": expected_featured_provider_run_id,
        "summary": SMOOTH_FEATURED_SUMMARY,
        "prompt_distinction": SMOOTH_FEATURED_PROMPT_DISTINCTION,
        "evidence": {
            "analysis_status": featured_proxy["analysis_status"],
            "regions_with_detected_motion": featured_coverage[
                "regions_with_detected_motion"
            ],
            "requested_region_count": featured_coverage[
                "requested_region_count"
            ],
            "abrupt_transition_count": featured_acceleration[
                "abrupt_transition_count"
            ],
            "motion_energy_spike_count": featured_motion_energy["spike_count"],
            "proxy_rank": featured_proxy["proxy_rank"],
            "proxy_rank_scale": SMOOTH_ATTEMPT_COUNT,
        },
        "practices": [dict(practice) for practice in SMOOTH_FEATURED_PRACTICES],
    }

    cost = retry_experiment["cost"]
    endpoint_base = route["default_base_url"].rstrip("/")
    return {
        "schema_version": 1,
        "experiment_id": smooth_experiment.EXPERIMENT_ID,
        "model_id": smooth_experiment.MODEL_ID,
        "agent_id": AGENT_ID,
        "updated_at": retry_experiment["updated_at"],
        "request_contract": {
            "classification": "non-loop-smooth-motion-experiment",
            "verified_lite_planning": True,
            "canonical_lite_runtime": True,
            "mechanism": "single-source-first-frame",
            "request_mechanism": "single-source-first-frame",
            "last_frame_is_source": False,
            "same_source_for_endpoints": False,
            "provider_native_loop_parameter": False,
            "browser_playback_loop": False,
            "frame_types": list(SMOOTH_FRAME_TYPES),
            "first_frame_url": smooth_experiment.SOURCE_URL,
            "last_frame_url": None,
            "provider_api_base_url": route["default_base_url"],
            "provider_submit_url": endpoint_base + route["paths"]["submit"],
            "provider_status_url_template": endpoint_base
            + route["paths"]["status_template"],
            "provider_content_url_template": endpoint_base
            + route["paths"]["content_template"],
        },
        "cost": {
            "currency": "USD",
            "operator_budget_cap_usd": cost["operator_budget_cap_usd"],
            "reserved_usd": cost["aggregate_reserved_usd"],
            "reservation_per_output_usd": float(
                smooth_experiment.RESERVATION_PER_ENTRY_USD
            ),
            "remaining_contingency_attempt_count": cost[
                "remaining_contingency_attempt_count"
            ],
            "remaining_contingency_reserved_usd": cost[
                "remaining_contingency_reserved_usd"
            ],
            "automatic_paid_retries": False,
            "actual_billing_available": False,
            "reservation_kind": "conservative-operator-envelope",
            "note": cost["note"],
        },
        "attempt_count": len(attempts),
        "attempts_without_video_count": 0,
        "available_attempt_count": len(available),
        "available_output_count": len(outputs),
        "display_output_count": len(outputs),
        "excluded_from_demo_count": len(available) - len(outputs),
        "accepted_output_count": 0,
        "featured_review": featured_review,
        "source": experiment["source"],
        "source_manifests": {
            "base_inventory": smooth_experiment.INVENTORY_PATH.as_posix(),
            "base_generation": smooth_experiment.GENERATION_MANIFEST_PATH.as_posix(),
            "base_experiment": smooth_experiment.EXPERIMENT_MANIFEST_PATH.as_posix(),
            "retry_inventory": smooth_retry.INVENTORY_PATH.as_posix(),
            "retry_generation": smooth_retry.GENERATION_MANIFEST_PATH.as_posix(),
            "retry_experiment": smooth_retry.EXPERIMENT_MANIFEST_PATH.as_posix(),
            "review": SMOOTH_REVIEW_PATH.as_posix(),
        },
        "receipt_sha256": {
            "base_experiment_manifest": sha256_file(
                root / smooth_experiment.EXPERIMENT_MANIFEST_PATH
            ),
            "base_inventory": sha256_file(root / smooth_experiment.INVENTORY_PATH),
            "base_generation": sha256_file(
                root / smooth_experiment.GENERATION_MANIFEST_PATH
            ),
            "retry_experiment_manifest": sha256_file(
                root / smooth_retry.EXPERIMENT_MANIFEST_PATH
            ),
            "retry_inventory": sha256_file(root / smooth_retry.INVENTORY_PATH),
            "retry_generation": sha256_file(
                root / smooth_retry.GENERATION_MANIFEST_PATH
            ),
            "review": review_sha256,
        },
        "attempt_history": attempts,
        "outputs": outputs,
    }


def build_manifest(
    *,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    source = case21.discover_case(root)
    controls = validate_controls(root)
    validate_budget_receipts(root)
    case21.validate_routes()
    attempts = build_attempt_history(root)
    attempts_by_provider_run_id = {
        attempt["provider_run_id"]: attempt for attempt in attempts
    }
    outputs: list[dict[str, Any]] = []
    planning: list[dict[str, Any]] = []
    for selection in DISPLAY_SELECTIONS:
        output, selected_planning = validate_display_selection(selection, source, root)
        attempt = attempts_by_provider_run_id.get(selection.provider_run_id)
        if not attempt:
            raise FinalizeError(
                f"Selected attempt is missing: {selection.provider_run_id}"
            )
        output["model_attempt_number"] = attempt["model_attempt_number"]
        output["attempt_history"] = [
            item for item in attempts if item["model_id"] == selection.model_id
        ]
        outputs.append(output)
        planning.append(selected_planning)
    if (
        [output["model_id"] for output in outputs] != list(case21.MODEL_IDS)
        or any(output["visual_review"]["status"] != "fidelity-failed" for output in outputs)
        or any(output["accepted"] for output in outputs)
        or any(not output["available"] for output in outputs)
    ):
        raise FinalizeError("Failure-aware output selection changed")

    research_outputs: list[dict[str, Any]] = []
    research_planning: list[dict[str, Any]] = []
    for selection in RESEARCH_SELECTIONS:
        output, selected_planning = validate_display_selection(selection, source, root)
        attempt = attempts_by_provider_run_id.get(selection.provider_run_id)
        if not attempt:
            raise FinalizeError(
                f"Research attempt is missing: {selection.provider_run_id}"
            )
        output["model_attempt_number"] = attempt["model_attempt_number"]
        research_outputs.append(output)
        research_planning.append(selected_planning)
    all_display_outputs = outputs + research_outputs
    if (
        len(research_outputs) != 4
        or len(all_display_outputs) != 7
        or len({output["video_path"] for output in all_display_outputs}) != 7
        or any(
            output["visual_review"]["status"] != "fidelity-failed"
            for output in all_display_outputs
        )
        or any(output["accepted"] for output in all_display_outputs)
        or any(not output["available"] for output in all_display_outputs)
    ):
        raise FinalizeError("Full case-21 research display selection changed")

    image_record = {
        "image": {
            **source.image,
            "delivery": "repository-raw",
        },
        "delivery": "repository-raw",
        "repository_raw_url": PUBLIC_RAW_BASE
        + quote(source.image["source_path"], safe="/"),
        "outputs": outputs,
        "research_outputs": research_outputs,
    }
    document = {
        "schema_version": 1,
        "manifest_role": "case-21-extension",
        "ticket": TICKET,
        "case_number": case21.CASE_NUMBER,
        "batch_id": FINAL_BATCH_ID,
        "agent_id": AGENT_ID,
        "delivery": "repository-raw",
        "updated_at": updated_at or transport.utc_now(),
        "models": list(case21.MODEL_IDS),
        "article_count": 1,
        "image_count": 1,
        "expected_outputs": 3,
        "canonical_output_count": 3,
        "research_output_count": 4,
        "display_output_count": 7,
        "attempt_count": 11,
        "attempts_without_video_count": 4,
        "available_output_count": 7,
        "accepted_output_count": 0,
        "rejected_output_count": 7,
        "conforming_output_count": 3,
        "contract_warning_output_count": 4,
        "visual_fidelity_passed_count": 0,
        "visual_fidelity_failed_count": 7,
        "cost": _expected_cost(),
        "generation_policy": {
            "route_resolution": "exact-model-id",
            "automatic_route_substitution": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "research_attempts_are_explicit": True,
            "route_capacities": dict(case21.ROUTE_CAPACITIES),
        },
        "acceptance_policy": {
            "display_availability_is_not_acceptance": True,
            "requires_exact_source_context_and_lite_provenance": True,
            "requires_exact_request_video_media_and_review_receipts": True,
            "fidelity_failed_outputs_are_accepted": False,
            "purpose": "preserve failed clips for comparative research",
        },
        "controls": controls,
        "source_manifests": {
            "primary_generation": case21.GENERATION_MANIFEST_PATH.as_posix(),
            "retry_generation": case21.RETRY_GENERATION_MANIFEST_PATH.as_posix(),
            "stage1_inventory": STAGE1_INVENTORY_PATH.as_posix(),
            "stage1_generation": STAGE1_GENERATION_PATH.as_posix(),
            "stage2_inventory": STAGE2_INVENTORY_PATH.as_posix(),
            "stage2_generation": STAGE2_GENERATION_PATH.as_posix(),
        },
        "attempt_history": attempts,
        "planning": {
            "selection_mode": "full-research-display",
            "selected_runs": planning,
            "research_runs": research_planning,
        },
        "articles": [
            {
                "article_number": source.article_number,
                "article_slug": source.article_slug,
                "title": source.title,
                "lead": source.lead,
                "url": source.url,
                "context_path": source.context_path,
                "collected_image_count": len(source.images),
                "images": [image_record],
            }
        ],
        "outputs": outputs,
        "research_outputs": research_outputs,
    }
    loop_document = build_loop_experiment(root)
    if loop_document is not None:
        document["loop_experiment"] = loop_document
    smooth_document = build_smooth_experiment(root)
    if smooth_document is not None:
        document["smooth_experiment"] = smooth_document
    return document


def finalize(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = build_manifest(root=root)
    destination = root / FINAL_MANIFEST_PATH
    if destination.exists() and (not destination.is_file() or destination.is_symlink()):
        raise FinalizeError(f"Final manifest path is unsafe: {destination}")
    transport.atomic_write_json(destination, document)
    return document


def verify(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    path = root / FINAL_MANIFEST_PATH
    existing = read_json(path)
    if not isinstance(existing, dict):
        raise FinalizeError("Final case-21 manifest is not an object")
    updated_at = existing.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise FinalizeError("Final case-21 manifest updated_at is missing")
    expected = build_manifest(root=root, updated_at=updated_at)
    if existing != expected:
        raise FinalizeError("Final case-21 manifest differs from exact reconstruction")
    return existing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preview", "finalize", "verify"),
        help="validate only, validate and write the sidecar, or verify the sidecar",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="workspace root (defaults to the script workspace)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            document = build_manifest(root=args.root)
        elif args.command == "finalize":
            document = finalize(args.root)
        else:
            document = verify(args.root)
    except (
        FinalizeError,
        case21.PipelineError,
        runner.LiteRunnerError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
        KeyError,
        ValueError,
    ) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS: case 21 exposes "
        f"{document['available_output_count']} research clips and accepts "
        f"{document['accepted_output_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
