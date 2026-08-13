#!/usr/bin/env python3
"""Build the deterministic public review manifest for the 2026-08-13 batch.

The private final-selection manifest is the sole source of selection and
attempt-audit data.  The S3 delivery manifest is the sole source of public
URLs.  This builder joins them fail-closed and re-runs the trusted Clipmaker
Lite provenance verifier for each article before publishing a compact review
payload.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402


BATCH_ID = "promopages-live-images-20260813-v1"
DATASET_PREFIX = "PROMOPAGES-live-images-20260813-v1"
AGENT_ID = "clipmaker-lite"
CONTRACT_VERSION = "2.1.4"
RUNNER_VERSION = 8
MANIFEST_ROLE = "clipmaker-lite-public-review"
MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
MODEL_DIRECTORIES = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
}
PUBLIC_BASE_URL = "https://yastatic.net/s3/promopages-front-bundles/"
BUCKET = "promopages-front-bundles"
OBJECT_PREFIX = "front-images/exp_video/"

DEFAULT_FINAL_SELECTION = (
    Path("clipmaker-lite-test/runs") / BATCH_ID / "final-selection.json"
)
DEFAULT_DELIVERY_MANIFEST = (
    Path(DATASET_PREFIX) / "s3-export/output/delivery-manifest.json"
)
DEFAULT_OUTPUT = Path("clipmaker-lite-test/reviews") / f"{BATCH_ID}.json"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


ARTICLE_CONTRACTS: tuple[dict[str, Any], ...] = (
    {
        "article_number": "01",
        "article_slug": "01-level-ipoteka-2026",
        "publication_id": "6a048ddca495b52c9d873940",
        "brand": "Level Group",
        "title": "Брать ипотеку в II половине 2026 года? Отвечают эксперты",
        "article_url": (
            "https://level-group.promo.page/media/"
            "brat-ipoteku-v-ii-polovine-2026-goda-otvechaiut-eksperty-"
            "6a048ddca495b52c9d873940_0_0"
        ),
        "image_id": "04",
        "media_id": "6a049156a495b52c9d87cb75",
        "width": 1920,
        "height": 1023,
        "caption": (
            "Ещё Банк России обсуждает возможность предоставлять льготную "
            "ипотеку только по месту регистрации родителей. В таком случае "
            "не получится купить квартиру в нужном городе без регистрации"
        ),
        "source_url": (
            "https://avatars.mds.yandex.net/get-promoarticles/6165752/"
            "pub_6a048ddca495b52c9d873940_6a049156a495b52c9d87cb75/orig"
        ),
        "source_sha256": (
            "e65e115579ed3143be9ee01f93bcb4f3cf68bf48ed58be9834c84babd98fcd49"
        ),
        "planning_run_id": (
            "promopages-live-images-20260813-v1-01-level-ipoteka-2026-04"
        ),
        "cabinet_path": "level-group__69ee06293ba10e0ae4b765d1",
    },
    {
        "article_number": "02",
        "article_slug": "02-banki-vygodno-kupit-dollar",
        "publication_id": "6a4f5fe924801975680d9be5",
        "brand": "Банки.ру",
        "title": "В каких банках можно выгодно купить доллар?",
        "article_url": (
            "https://banki.promo.page/save/"
            "v-kakih-bankah-mojno-vygodno-kupit-dollar-"
            "6a4f5fe924801975680d9be5_0_0"
        ),
        "image_id": "01",
        "media_id": "6a4f718952e3ce75a3110deb",
        "width": 2000,
        "height": 1125,
        "caption": "",
        "source_url": (
            "https://avatars.mds.yandex.net/get-promoarticles/5126709/"
            "pub_6a4f5fe924801975680d9be5_6a4f718952e3ce75a3110deb/orig"
        ),
        "source_sha256": (
            "82f180a2e7ec64bbf46ba4089cef8494109c5960df2d89206e8faf570dbf3a65"
        ),
        "planning_run_id": (
            "promopages-live-images-20260813-v1-"
            "02-banki-vygodno-kupit-dollar-01"
        ),
        "cabinet_path": "banki-ru__5b0fb7c448c85e2421e049ab",
    },
)


class ReviewManifestError(RuntimeError):
    """A fail-closed review-manifest validation or build error."""


ProvenanceResolver = Callable[[Path, str], Mapping[str, Any]]


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewManifestError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewManifestError(f"{label} must be a JSON object: {path}")
    return value


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value > 0
    )


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReviewManifestError(f"Cannot hash current runner {path}: {exc}") from exc
    return digest.hexdigest()


def _normalize_prompt(value: Any, *, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not _is_nonempty_string(value.get("positive")):
        raise ReviewManifestError(f"{label} prompt is invalid")
    negative = value.get("negative")
    if negative is None:
        negative = ""
    if not isinstance(negative, str):
        raise ReviewManifestError(f"{label} negative prompt must be a string or null")
    return {"positive": value["positive"], "negative": negative}


def _normalize_attempt(
    value: Any, *, label: str, model_id: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewManifestError(f"{label} attempt must be an object")
    attempt_id = value.get("attempt_id")
    status = value.get("status")
    recorded_status = value.get("recorded_status")
    provider_run_id = value.get("provider_run_id")
    error = value.get("error")
    provider_response = value.get("provider_response")
    if (
        not _is_nonempty_string(attempt_id)
        or not _is_nonempty_string(status)
        or not _is_nonempty_string(recorded_status)
        or provider_run_id is not None
        and not _is_nonempty_string(provider_run_id)
        or error is not None
        and not _is_nonempty_string(error)
        or provider_response is not None
        and not isinstance(provider_response, dict)
    ):
        raise ReviewManifestError(f"{label} attempt audit is invalid")
    media = value.get("media")
    contract_check = value.get("contract_check")
    media_acceptance = value.get("media_acceptance")
    if (media is None, contract_check is None, media_acceptance is None).count(True) not in {0, 3}:
        raise ReviewManifestError(f"{label} attempt media audit is incomplete")
    if media is not None:
        media = _validate_media(media, label=label)
        contract_check = _validate_contract_check(contract_check, label=label)
        if not native.validate_media_acceptance(
            model_id, media, contract_check, media_acceptance
        ):
            raise ReviewManifestError(f"{label} media acceptance is invalid")
        if media_acceptance["accepted"] is True:
            expected_recorded = (
                "succeeded"
                if media_acceptance["mode"] == "strict-contract"
                else "verification-failed"
            )
            if status != "succeeded" or recorded_status != expected_recorded:
                raise ReviewManifestError(f"{label} effective attempt status differs")
        elif (
            status != "verification-failed"
            or recorded_status != "verification-failed"
            or contract_check.get("conforms") is not False
            or not contract_check.get("warnings")
        ):
            raise ReviewManifestError(f"{label} rejected attempt audit differs")
        media_acceptance = copy.deepcopy(media_acceptance)
    elif status != recorded_status:
        raise ReviewManifestError(f"{label} attempt status has no acceptance basis")
    return {
        "attempt_id": attempt_id,
        "status": status,
        "recorded_status": recorded_status,
        "prompt": _normalize_prompt(value.get("prompt"), label=label),
        "provider_run_id": provider_run_id,
        "provider_response": copy.deepcopy(provider_response),
        "media": media,
        "contract_check": copy.deepcopy(contract_check),
        "media_acceptance": media_acceptance,
        "error": error,
    }


def _validate_final_identity(final: Mapping[str, Any]) -> None:
    if (
        final.get("schema_version") != 1
        or final.get("manifest_role") != "clipmaker-lite-final-selection"
        or final.get("dataset_prefix") != DATASET_PREFIX
        or final.get("batch_id") != BATCH_ID
        or final.get("producer")
        != {
            "agent_id": AGENT_ID,
            "contract_version": CONTRACT_VERSION,
            "runner_version": RUNNER_VERSION,
        }
        or final.get("models") != list(MODEL_IDS)
        or final.get("article_count") != 2
        or final.get("image_count") != 2
        or final.get("expected_outputs") != 6
        or not isinstance(final.get("articles"), list)
        or len(final["articles"]) != 2
        or not isinstance(final.get("outputs"), list)
        or len(final["outputs"]) != 6
    ):
        raise ReviewManifestError("Final-selection identity, models, or counts differ")


def _index_articles(final: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in final["articles"]:
        if not isinstance(raw, dict) or not _is_nonempty_string(raw.get("article_slug")):
            raise ReviewManifestError("Final-selection article is invalid")
        slug = raw["article_slug"]
        if slug in indexed:
            raise ReviewManifestError(f"Duplicate final-selection article: {slug}")
        indexed[slug] = raw
    if set(indexed) != {item["article_slug"] for item in ARTICLE_CONTRACTS}:
        raise ReviewManifestError("Final-selection article set differs")
    return indexed


def _validate_article(raw: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    for field in (
        "article_number",
        "article_slug",
        "publication_id",
        "brand",
        "title",
        "article_url",
    ):
        if raw.get(field) != contract[field]:
            raise ReviewManifestError(
                f"{contract['article_slug']} article field differs: {field}"
            )
    image = raw.get("image")
    if not isinstance(image, dict):
        raise ReviewManifestError(f"{contract['article_slug']} image is missing")
    for field in (
        "image_id",
        "media_id",
        "width",
        "height",
        "caption",
        "source_url",
        "source_sha256",
        "planning_run_id",
    ):
        if image.get(field) != contract[field]:
            raise ReviewManifestError(
                f"{contract['article_slug']} frozen image field differs: {field}"
            )


def _index_outputs(final: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    expected = {
        (contract["article_slug"], model_id)
        for contract in ARTICLE_CONTRACTS
        for model_id in MODEL_IDS
    }
    contracts = {item["article_slug"]: item for item in ARTICLE_CONTRACTS}
    for raw in final["outputs"]:
        if not isinstance(raw, dict):
            raise ReviewManifestError("Final-selection output must be an object")
        key = (str(raw.get("article_slug")), str(raw.get("model_id")))
        if key not in expected or key in indexed:
            raise ReviewManifestError(f"Unexpected or duplicate final output: {key}")
        contract = contracts[key[0]]
        for field in (
            "article_number",
            "article_slug",
            "publication_id",
            "image_id",
            "media_id",
        ):
            if raw.get(field) != contract[field]:
                raise ReviewManifestError(f"Final output route differs: {key}/{field}")
        indexed[key] = raw
    if set(indexed) != expected:
        raise ReviewManifestError("Final-selection output coverage differs")
    return indexed


def _index_delivery(delivery: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    outputs = delivery.get("outputs")
    if (
        delivery.get("schema_version") != 1
        or delivery.get("manifest_role") != "promopages-live-images-s3-delivery"
        or delivery.get("batch_id") != BATCH_ID
        or delivery.get("bucket") != BUCKET
        or delivery.get("object_prefix") != OBJECT_PREFIX
        or not isinstance(outputs, list)
        or delivery.get("verified_output_count") != len(outputs)
    ):
        raise ReviewManifestError("S3 delivery identity or count differs")
    expected = {
        (contract["article_slug"], model_id)
        for contract in ARTICLE_CONTRACTS
        for model_id in MODEL_IDS
    }
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in outputs:
        if not isinstance(raw, dict):
            raise ReviewManifestError("S3 delivery output must be an object")
        key = (str(raw.get("article_slug")), str(raw.get("model_id")))
        if key not in expected or key in indexed:
            raise ReviewManifestError(f"Unexpected or duplicate S3 delivery: {key}")
        indexed[key] = raw
    return indexed


def _verify_provenance(
    root: Path,
    contract: Mapping[str, Any],
    resolver: ProvenanceResolver,
) -> dict[str, Any]:
    run_id = contract["planning_run_id"]
    try:
        raw = resolver(root, run_id)
    except Exception as exc:
        raise ReviewManifestError(
            f"Lite provenance verification failed for {run_id}: {exc}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise ReviewManifestError(f"Lite provenance is not an object: {run_id}")

    runner_path = root / runner.RUNNER_PATH
    expected_runner = {
        "path": runner.RUNNER_PATH.as_posix(),
        "sha256": _sha256_file(runner_path),
    }
    expected_result_path = (
        runner.OUTPUT_NAMESPACE / run_id / "result.json"
    ).as_posix()
    if (
        runner.RUNNER_VERSION != RUNNER_VERSION
        or tuple(runner.SUPPORTED_MODELS) != MODEL_IDS
        or raw.get("verified") is not True
        or raw.get("verification_scope") != runner.VERIFICATION_SCOPE
        or raw.get("agent_id") != AGENT_ID
        or raw.get("contract_version") != CONTRACT_VERSION
        or raw.get("result_path") != expected_result_path
        or raw.get("models") != list(MODEL_IDS)
        or raw.get("source_image_sha256") != contract["source_sha256"]
        or not _is_sha256(raw.get("article_context_sha256"))
        or raw.get("runner") != expected_runner
        or not isinstance(raw.get("contract_fingerprint"), str)
        or FINGERPRINT_RE.fullmatch(raw["contract_fingerprint"]) is None
        or not _is_sha256(raw.get("instruction_bundle_sha256"))
    ):
        raise ReviewManifestError(f"Lite provenance differs from current run: {run_id}")

    return {
        "verified": True,
        "verification_scope": raw["verification_scope"],
        "cryptographically_signed": raw.get("cryptographically_signed") is True,
        "result_path": raw["result_path"],
        "agent_id": raw["agent_id"],
        "contract_version": raw["contract_version"],
        "contract_fingerprint": raw["contract_fingerprint"],
        "instruction_bundle_sha256": raw["instruction_bundle_sha256"],
        "runner_version": RUNNER_VERSION,
        "runner": copy.deepcopy(raw["runner"]),
        "models": list(raw["models"]),
        "source_image_sha256": raw["source_image_sha256"],
        "article_context_sha256": raw["article_context_sha256"],
    }


def _validate_attempts(
    raw: Mapping[str, Any], *, label: str, model_id: str
) -> list[dict[str, Any]]:
    attempt_count = raw.get("attempt_count")
    attempts = raw.get("attempts")
    if (
        not _is_positive_int(attempt_count)
        or not isinstance(attempts, list)
        or len(attempts) != attempt_count
    ):
        raise ReviewManifestError(f"{label} attempt count differs")
    normalized = [
        _normalize_attempt(
            attempt, label=f"{label}/{index + 1}", model_id=model_id
        )
        for index, attempt in enumerate(attempts)
    ]
    attempt_ids = [attempt["attempt_id"] for attempt in normalized]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ReviewManifestError(f"{label} has duplicate attempt IDs")
    return normalized


def _validate_media(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewManifestError(f"{label} media is missing")
    if (
        not _is_sha256(value.get("sha256"))
        or not _is_positive_int(value.get("bytes"))
        or not _is_positive_int(value.get("width"))
        or not _is_positive_int(value.get("height"))
        or not _is_positive_number(value.get("duration_seconds"))
    ):
        raise ReviewManifestError(f"{label} media metadata is invalid")
    return copy.deepcopy(value)


def _validate_contract_check(value: Any, *, label: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("conforms"), bool)
        or not isinstance(value.get("warnings"), list)
        or any(not isinstance(item, str) for item in value["warnings"])
    ):
        raise ReviewManifestError(f"{label} media contract is invalid")
    return copy.deepcopy(value)


def _public_output(
    raw: Mapping[str, Any],
    delivery: Mapping[str, Any] | None,
    contract: Mapping[str, Any],
    *,
    model_id: str,
) -> dict[str, Any]:
    label = f"{contract['article_slug']}/{contract['image_id']}/{model_id}"
    attempts = _validate_attempts(raw, label=label, model_id=model_id)
    status = raw.get("status")
    if status == "unavailable":
        if (
            raw.get("selected_attempt_id") is not None
            or raw.get("selected_prompt") is not None
            or raw.get("provider_run_id") is not None
            or raw.get("video_path") is not None
            or raw.get("media") is not None
            or raw.get("contract_check") is not None
            or raw.get("media_acceptance") is not None
            or raw.get("recorded_status") is not None
            or not _is_nonempty_string(raw.get("error"))
            or any(attempt["status"] == "succeeded" for attempt in attempts)
            or delivery is not None
        ):
            raise ReviewManifestError(f"Unavailable output has selected media: {label}")
        return {
            "model_id": model_id,
            "status": "unavailable",
            "selected_attempt_id": None,
            "selected_prompt": None,
            "attempt_count": len(attempts),
            "attempts": attempts,
            "video_url": None,
            "media": None,
            "contract_check": None,
            "media_acceptance": None,
            "recorded_status": None,
            "error": raw["error"],
        }

    if status != "succeeded" or delivery is None:
        raise ReviewManifestError(f"Succeeded output has no exact delivery: {label}")
    selected_attempt_id = raw.get("selected_attempt_id")
    if not _is_nonempty_string(selected_attempt_id):
        raise ReviewManifestError(f"Selected attempt is missing: {label}")
    selected = next(
        (attempt for attempt in attempts if attempt["attempt_id"] == selected_attempt_id),
        None,
    )
    selected_prompt = _normalize_prompt(raw.get("selected_prompt"), label=label)
    recorded_status = raw.get("recorded_status")
    if (
        selected is None
        or selected["status"] != "succeeded"
        or not _is_nonempty_string(recorded_status)
        or selected["recorded_status"] != recorded_status
        or selected["prompt"] != selected_prompt
        or not _is_nonempty_string(raw.get("provider_run_id"))
        or selected["provider_run_id"] != raw["provider_run_id"]
        or not _is_nonempty_string(raw.get("video_path"))
        or raw.get("error") is not None
    ):
        raise ReviewManifestError(f"Succeeded selection audit differs: {label}")
    media = _validate_media(raw.get("media"), label=label)
    contract_check = _validate_contract_check(raw.get("contract_check"), label=label)
    media_acceptance = raw.get("media_acceptance")
    if (
        not native.validate_media_acceptance(
            model_id, media, contract_check, media_acceptance
        )
        or selected["media"] != media
        or selected["contract_check"] != contract_check
        or selected["media_acceptance"] != media_acceptance
    ):
        raise ReviewManifestError(f"Succeeded media acceptance audit differs: {label}")

    for field in ("article_slug", "publication_id", "image_id", "media_id"):
        if delivery.get(field) != contract[field]:
            raise ReviewManifestError(f"S3 delivery route differs: {label}/{field}")
    if (
        delivery.get("model_id") != model_id
        or delivery.get("selected_attempt_id") != selected_attempt_id
        or delivery.get("provider_run_id") != raw["provider_run_id"]
        or delivery.get("sha256") != media["sha256"]
        or delivery.get("bytes") != media["bytes"]
        or delivery.get("recorded_status") != recorded_status
        or delivery.get("media_acceptance") != media_acceptance
    ):
        raise ReviewManifestError(f"S3 delivery selection or media differs: {label}")

    object_key = (
        f"{OBJECT_PREFIX}{contract['cabinet_path']}/"
        f"{contract['publication_id']}/{MODEL_DIRECTORIES[model_id]}/"
        f"image_{contract['image_id']}--sha256-{media['sha256'][:12]}.mp4"
    )
    video_url = PUBLIC_BASE_URL + object_key
    if delivery.get("object_key") != object_key or delivery.get("yastatic_url") != video_url:
        raise ReviewManifestError(f"S3 object key or yastatic URL differs: {label}")

    return {
        "model_id": model_id,
        "status": "succeeded",
        "recorded_status": recorded_status,
        "selected_attempt_id": selected_attempt_id,
        "selected_prompt": selected_prompt,
        "attempt_count": len(attempts),
        "attempts": attempts,
        "video_url": video_url,
        "media": media,
        "contract_check": contract_check,
        "media_acceptance": copy.deepcopy(media_acceptance),
        "error": None,
    }


def build_manifest(
    *,
    root: Path = ROOT,
    final_selection_path: Path | None = None,
    delivery_manifest_path: Path | None = None,
    provenance_resolver: ProvenanceResolver | None = None,
) -> dict[str, Any]:
    """Validate both private manifests and return one deterministic payload."""

    root = root.resolve()
    final_path = final_selection_path or root / DEFAULT_FINAL_SELECTION
    delivery_path = delivery_manifest_path or root / DEFAULT_DELIVERY_MANIFEST
    final = _read_json(final_path, label="final selection")
    delivery = _read_json(delivery_path, label="S3 delivery manifest")
    _validate_final_identity(final)
    article_index = _index_articles(final)
    output_index = _index_outputs(final)
    delivery_index = _index_delivery(delivery)
    resolver = provenance_resolver or runner.provenance_summary

    articles: list[dict[str, Any]] = []
    successful_keys: set[tuple[str, str]] = set()
    common_provenance: tuple[str, str, tuple[tuple[str, str], ...]] | None = None
    for contract in ARTICLE_CONTRACTS:
        article = article_index[contract["article_slug"]]
        _validate_article(article, contract)
        provenance = _verify_provenance(root, contract, resolver)
        provenance_identity = (
            provenance["contract_fingerprint"],
            provenance["instruction_bundle_sha256"],
            tuple(sorted(provenance["runner"].items())),
        )
        if common_provenance is None:
            common_provenance = provenance_identity
        elif provenance_identity != common_provenance:
            raise ReviewManifestError("Article planning runs use different Lite contract/runner")

        public_outputs: list[dict[str, Any]] = []
        for model_id in MODEL_IDS:
            key = (contract["article_slug"], model_id)
            selected = output_index[key]
            delivered = delivery_index.get(key)
            public_output = _public_output(
                selected, delivered, contract, model_id=model_id
            )
            if public_output["status"] == "succeeded":
                successful_keys.add(key)
            public_outputs.append(public_output)

        image = article["image"]
        articles.append(
            {
                "publication_id": contract["publication_id"],
                "brand": contract["brand"],
                "title": contract["title"],
                "article_url": contract["article_url"],
                "image": {
                    "image_id": contract["image_id"],
                    "media_id": contract["media_id"],
                    "width": contract["width"],
                    "height": contract["height"],
                    "caption": image["caption"],
                    "source_url": contract["source_url"],
                    "provenance": provenance,
                    "outputs": public_outputs,
                },
            }
        )

    if set(delivery_index) != successful_keys:
        extras = sorted(set(delivery_index) - successful_keys)
        missing = sorted(successful_keys - set(delivery_index))
        raise ReviewManifestError(
            f"S3 delivery coverage differs: missing={missing}, extras={extras}"
        )

    return {
        "schema_version": 1,
        "manifest_role": MANIFEST_ROLE,
        "batch_id": BATCH_ID,
        "producer": {
            "agent_id": AGENT_ID,
            "contract_version": CONTRACT_VERSION,
            "runner_version": RUNNER_VERSION,
        },
        "models": list(MODEL_IDS),
        "article_count": 2,
        "image_count": 2,
        "expected_outputs": 6,
        "articles": articles,
    }


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    """Durably replace one manifest without exposing a partial JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ReviewManifestError(f"Cannot atomically write {path}: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def build(
    *,
    root: Path = ROOT,
    final_selection_path: Path | None = None,
    delivery_manifest_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    manifest = build_manifest(
        root=root,
        final_selection_path=final_selection_path,
        delivery_manifest_path=delivery_manifest_path,
    )
    target = output_path or root.resolve() / DEFAULT_OUTPUT
    atomic_write(target, manifest)
    return manifest


def verify(
    *,
    root: Path = ROOT,
    final_selection_path: Path | None = None,
    delivery_manifest_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    expected = build_manifest(
        root=root,
        final_selection_path=final_selection_path,
        delivery_manifest_path=delivery_manifest_path,
    )
    target = manifest_path or root.resolve() / DEFAULT_OUTPUT
    actual = _read_json(target, label="public review manifest")
    if actual != expected:
        raise ReviewManifestError("Public review manifest is stale or was modified")
    succeeded = sum(
        output["status"] == "succeeded"
        for article in actual["articles"]
        for output in article["image"]["outputs"]
    )
    return {
        "verified": True,
        "batch_id": BATCH_ID,
        "article_count": 2,
        "output_count": 6,
        "succeeded_output_count": succeeded,
        "unavailable_output_count": 6 - succeeded,
        "manifest_path": target.resolve().as_posix(),
    }


def _rooted(root: Path, value: str | None, default: Path) -> Path:
    path = Path(value) if value is not None else default
    return path if path.is_absolute() else root / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="workspace root")
    parser.add_argument("--final-selection", help="final-selection JSON path")
    parser.add_argument("--delivery-manifest", help="delivery-manifest JSON path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_command = subparsers.add_parser("build", help="validate and atomically write")
    build_command.add_argument("--output", help="public review JSON path")
    verify_command = subparsers.add_parser("verify", help="rebuild in memory and compare")
    verify_command.add_argument("--manifest", help="public review JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    final_path = _rooted(root, args.final_selection, DEFAULT_FINAL_SELECTION)
    delivery_path = _rooted(root, args.delivery_manifest, DEFAULT_DELIVERY_MANIFEST)
    try:
        if args.command == "build":
            output_path = _rooted(root, args.output, DEFAULT_OUTPUT)
            manifest = build(
                root=root,
                final_selection_path=final_path,
                delivery_manifest_path=delivery_path,
                output_path=output_path,
            )
            result = {
                "built": True,
                "batch_id": manifest["batch_id"],
                "output_count": manifest["expected_outputs"],
                "manifest_path": output_path.resolve().as_posix(),
            }
        else:
            manifest_path = _rooted(root, args.manifest, DEFAULT_OUTPUT)
            result = verify(
                root=root,
                final_selection_path=final_path,
                delivery_manifest_path=delivery_path,
                manifest_path=manifest_path,
            )
    except ReviewManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
