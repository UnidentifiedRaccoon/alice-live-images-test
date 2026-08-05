"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


const ROOT = path.resolve(__dirname, "..");
const APP_PATH = path.join(ROOT, "clipmaker-lite", "app.js");
const CASE_21_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "case-21-manifest.json",
);

const loadHooks = () => {
  const source = fs
    .readFileSync(APP_PATH, "utf8")
    .replace(
      "  const validateCase21Manifest",
      "  globalThis.__validateSmoothExperiment = validateSmoothExperiment;\n\n" +
        "  const validateCase21Manifest",
    )
    .replace(
      "  const renderLoopAttemptHistory",
      "  globalThis.__renderModel = renderModel;\n\n" +
        "  const renderLoopAttemptHistory",
    )
    .replace(
      "  const renderFacts",
      "  globalThis.__validatePromopages10060Manifest = validatePromopages10060Manifest;\n" +
        "  globalThis.__mergeArticleCollections = mergeArticleCollections;\n" +
        "  globalThis.__datasetCounts = datasetCounts;\n" +
        "  globalThis.__availableOutputCount = availableOutputCount;\n" +
        "  globalThis.__resolveRequestedArticleIndex = resolveRequestedArticleIndex;\n\n" +
        "  globalThis.__resolveRequestedImageIndex = resolveRequestedImageIndex;\n\n" +
        "  const renderFacts",
    )
    .replace(
      "  const renderSmoothSection",
      "  globalThis.__renderSmoothFeaturedReview = renderSmoothFeaturedReview;\n\n" +
        "  const renderSmoothSection",
    );
  const inertElement = {
    addEventListener() {},
  };
  const context = {
    console,
    document: {
      querySelector() {
        return inertElement;
      },
    },
    fetch() {
      return new Promise(() => {});
    },
    window: {
      location: {
        hostname: "unidentifiedraccoon.github.io",
        href: "https://unidentifiedraccoon.github.io/alice-live-images-test/clipmaker-lite/",
      },
      history: { replaceState() {} },
      matchMedia() {
        return { matches: false };
      },
    },
  };
  vm.runInNewContext(source, context, { filename: APP_PATH });
  return context;
};

const actualSmoothExperiment = () => {
  const manifest = JSON.parse(fs.readFileSync(CASE_21_MANIFEST_PATH, "utf8"));
  assert.ok(manifest.smooth_experiment, "smooth_experiment must be published");
  return manifest.smooth_experiment;
};

const clone = (value) => JSON.parse(JSON.stringify(value));

const REVIEW_ARTICLE_IMAGE_COUNTS = [
  ["01", 4],
  ["03", 9],
  ["04", 8],
  ["05", 7],
  ["06", 6],
  ["07", 9],
  ["08", 8],
  ["09", 5],
  ["10", 8],
  ["11", 4],
  ["12", 10],
  ["13", 8],
  ["14", 6],
];
const NORMALIZED_RETRY_NAMESPACE =
  "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-retries-v1";
const NORMALIZED_ASSET_NAMESPACE =
  "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-assets-v1";
const NORMALIZED_ORIGINAL_URL =
  "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/orig";
const NORMALIZED_URL =
  "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/scale_1200";

const providerFilteredOutput = (articleSlug, imageId, modelId) => {
  const requestSha = "1".repeat(64);
  const namespace =
    "clipmaker-lite-test/runs/promopages-10060-test/terminal-provider-retries-v1/filtered-output";
  const retryError =
    "Video generation completed with no output; content may have been filtered";
  return {
    article_slug: articleSlug,
    image_id: imageId,
    model_id: modelId,
    provider_run_id: "retry-provider-run",
    positive_prompt: `Prompt ${articleSlug}/${imageId}/filtered`,
    negative_prompt: "Do not replace the subject.",
    status: "provider-filtered",
    recorded_status: "provider-failed",
    selected_attempt: "terminal-retry-v1-exhausted",
    video_path: null,
    media: null,
    contract_check: null,
    error: retryError,
    retry: {
      retry_number: 1,
      namespace,
      envelope_path: `${namespace}/retry.json`,
      exhausted: true,
      primary_attempt: {
        provider_run_id: "primary-provider-run",
        provider_job_id: "primary-provider-job",
        status: "provider-failed",
        submitted_at: "2026-08-04T23:42:39Z",
        completed_at: "2026-08-04T23:44:12Z",
        error: "Video completed with no output; content may have been filtered",
        run_path: "runs/primary.run.json",
        run_sha256: "2".repeat(64),
        prompt_path: "runs/primary.prompt.json",
        prompt_sha256: "3".repeat(64),
        request_sha256: requestSha,
      },
      retry_attempt: {
        provider_run_id: "retry-provider-run",
        provider_job_id: "retry-provider-job",
        status: "provider-failed",
        provider_may_be_active: false,
        submitted_at: "2026-08-04T23:57:23Z",
        completed_at: "2026-08-04T23:58:27Z",
        error: retryError,
        run_path: "runs/retry.run.json",
        run_sha256: "4".repeat(64),
        prompt_path: "runs/retry.prompt.json",
        prompt_sha256: "5".repeat(64),
        request_sha256: requestSha,
      },
    },
  };
};

const providerUnavailableOutput = (articleSlug, imageId, modelId) => {
  const requestSha = "6".repeat(64);
  const namespace =
    "clipmaker-lite-test/runs/promopages-10060-test/ambiguous-submit-retries-v1/unavailable-output";
  const retryError = "Provider returned a terminal failure after the explicit retry";
  return {
    article_slug: articleSlug,
    image_id: imageId,
    model_id: modelId,
    provider_run_id: "ambiguous-retry-provider-run",
    positive_prompt: `Prompt ${articleSlug}/${imageId}/unavailable`,
    negative_prompt: "",
    status: "provider-unavailable",
    recorded_status: "provider-failed",
    selected_attempt: "ambiguous-submit-retry-v1-exhausted",
    video_path: null,
    media: null,
    contract_check: null,
    error: retryError,
    retry: {
      retry_kind: "ambiguous-submit",
      retry_number: 1,
      namespace,
      envelope_path: `${namespace}/retry.json`,
      envelope_sha256: "7".repeat(64),
      exhausted: true,
      primary_outcome_unknown: true,
      primary_attempt: {
        provider_run_id: "ambiguous-primary-provider-run",
        provider_job_id: null,
        status: "submit-unknown",
        recorded_status: "submitting",
        outcome: "unknown",
        outcome_unknown: true,
        ambiguity_reason:
          "Synchronous submit may have reached the provider without a durable response",
        provider_may_be_active: true,
        submitted_at: null,
        completed_at: null,
        error: null,
        run_path: "runs/ambiguous-primary.run.json",
        run_sha256: "8".repeat(64),
        prompt_path: "runs/ambiguous-primary.prompt.json",
        prompt_sha256: "9".repeat(64),
        request_sha256: requestSha,
      },
      retry_attempt: {
        provider_run_id: "ambiguous-retry-provider-run",
        provider_job_id: "ambiguous-retry-provider-job",
        status: "provider-failed",
        provider_may_be_active: false,
        submitted_at: "2026-08-05T05:10:00Z",
        completed_at: "2026-08-05T05:12:00Z",
        error: retryError,
        run_path: "runs/ambiguous-retry.run.json",
        run_sha256: "a".repeat(64),
        prompt_path: "runs/ambiguous-retry.prompt.json",
        prompt_sha256: "b".repeat(64),
        request_sha256: requestSha,
      },
    },
  };
};

const ambiguousRetrySuccessOutput = (articleSlug, imageId, modelId) => {
  const output = providerUnavailableOutput(articleSlug, imageId, modelId);
  return {
    ...output,
    status: "succeeded",
    recorded_status: "succeeded",
    selected_attempt: "ambiguous-submit-retry-v1",
    video_path: `PROMOPAGES-10060/video/${articleSlug}-${imageId}-ambiguous-retry.mp4`,
    media: {
      width: 1280,
      height: 720,
      duration_seconds: 5,
      bytes: 2048,
    },
    contract_check: { conforms: true, warnings: [] },
    error: null,
    retry: {
      ...output.retry,
      exhausted: false,
      retry_attempt: {
        ...output.retry.retry_attempt,
        status: "succeeded",
        error: null,
      },
    },
  };
};

const normalizedInputRetryOutput = (
  articleSlug,
  image,
  modelId,
  { exhausted },
) => {
  const modelSuffix = modelId === "alibaba/wan-2.2" ? "wan22" : "wan27";
  const namespace = `${NORMALIZED_RETRY_NAMESPACE}/${modelSuffix}-retry-key`;
  const retryError = exhausted
    ? "Provider returned a terminal failure after normalized input retry"
    : null;
  const recordedStatus = exhausted ? "provider-failed" : "succeeded";
  const primary = {
    provider_run_id: `${modelSuffix}-oversize-primary-run`,
    provider_job_id: `${modelSuffix}-oversize-primary-job`,
    status: "provider-failed",
    recorded_status:
      modelId === "alibaba/wan-2.2" ? "submit-unknown" : "provider-failed",
    provider_may_be_active: false,
    recorded_provider_may_be_active: modelId === "alibaba/wan-2.2",
    submitted_at:
      modelId === "alibaba/wan-2.2" ? null : "2026-08-05T06:00:00Z",
    completed_at:
      modelId === "alibaba/wan-2.2" ? null : "2026-08-05T06:01:00Z",
    error: "File size exceeds maximum allowed size of 20971520 bytes",
    run_path: `runs/${modelSuffix}-oversize-primary.run.json`,
    run_sha256: "c".repeat(64),
    prompt_path: `runs/${modelSuffix}-oversize-primary.prompt.json`,
    prompt_sha256: "d".repeat(64),
    request_sha256: "e".repeat(64),
  };
  if (modelId === "alibaba/wan-2.2") {
    Object.assign(primary, {
      provider_submit_time: "2026-08-05T06:00:00Z",
      provider_scheduled_time: "2026-08-05T06:00:01Z",
      provider_end_time: "2026-08-05T06:00:02Z",
    });
  }
  return {
    article_slug: articleSlug,
    image_id: image.image_id,
    source_path: image.source_path,
    model_id: modelId,
    provider_run_id: `${modelSuffix}-normalized-retry-run`,
    positive_prompt: "Keep the exact scene and add one restrained movement.",
    negative_prompt: "Do not alter the composition.",
    status: exhausted ? "provider-unavailable" : "succeeded",
    recorded_status: recordedStatus,
    selected_attempt: exhausted
      ? "normalized-input-retry-v1-exhausted"
      : "normalized-input-retry-v1",
    video_path: exhausted
      ? null
      : `PROMOPAGES-10060/video/${articleSlug}-${image.image_id}-${modelSuffix}-normalized.mp4`,
    media: exhausted
      ? null
      : { width: 1280, height: 720, duration_seconds: 5, bytes: 4096 },
    contract_check: exhausted ? null : { conforms: true, warnings: [] },
    error: retryError,
    retry: {
      retry_kind: "normalized-input",
      retry_number: 1,
      namespace,
      envelope_path: `${namespace}/retry.json`,
      envelope_sha256: "f".repeat(64),
      exhausted,
      primary_attempt: primary,
      retry_attempt: {
        provider_run_id: `${modelSuffix}-normalized-retry-run`,
        provider_job_id: `${modelSuffix}-normalized-retry-job`,
        status: recordedStatus,
        provider_may_be_active: false,
        submitted_at: "2026-08-05T06:05:00Z",
        completed_at: "2026-08-05T06:07:00Z",
        error: retryError,
        run_path: `runs/${modelSuffix}-normalized-retry.run.json`,
        run_sha256: "1".repeat(64),
        prompt_path: `runs/${modelSuffix}-normalized-retry.prompt.json`,
        prompt_sha256: "2".repeat(64),
        request_sha256: "3".repeat(64),
      },
      source_transform: {
        strategy: "frozen-page-variant",
        original: {
          url: NORMALIZED_ORIGINAL_URL,
          path: image.source_path,
          sha256: image.sha256,
          bytes: 23_472_383,
          width: image.width,
          height: image.height,
        },
        normalized: {
          url: NORMALIZED_URL,
          sha256: "4".repeat(64),
          bytes: 1_500_000,
          width: 1200,
          height: 801,
          metadata_path: `${NORMALIZED_ASSET_NAMESPACE}/shared-asset/asset.json`,
          metadata_sha256: "5".repeat(64),
        },
        request_delta: {
          json_pointer:
            modelId === "alibaba/wan-2.2"
              ? "/input/image"
              : "/frame_images/0/image_url/url",
          from: NORMALIZED_ORIGINAL_URL,
          to: NORMALIZED_URL,
          changed_leaf_count: 1,
        },
      },
    },
  };
};

const reviewManifest = () => {
  const models = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
  ];
  const outputs = [];
  const articles = REVIEW_ARTICLE_IMAGE_COUNTS.map(([articleNumber, imageCount]) => {
    const articleSlug =
      articleNumber === "12"
        ? "12-dream-island-7-fishek"
        : `${articleNumber}-new-article`;
    const images = Array.from({ length: imageCount }, (_, imageIndex) => {
      const imageId = String(imageIndex + 1).padStart(2, "0");
      const imageOutputs = models.map((modelId, modelIndex) =>
        articleNumber === "07" &&
        imageId === "06" &&
        modelId === "google/veo-3.1-lite"
          ? providerFilteredOutput(articleSlug, imageId, modelId)
          : {
              article_slug: articleSlug,
              image_id: imageId,
              model_id: modelId,
              positive_prompt: `Prompt ${articleNumber}/${imageId}/${modelIndex + 1}`,
              negative_prompt: "",
              status: "succeeded",
              video_path: `PROMOPAGES-10060/video/${articleNumber}-${imageId}-${modelIndex + 1}.mp4`,
              media: {
                width: 1280,
                height: 720,
                duration_seconds: 5,
                bytes: 1024 + imageIndex * models.length + modelIndex,
              },
            },
      );
      outputs.push(...imageOutputs);
      return {
        image: {
          image_id: imageId,
          file: `${imageId}.jpg`,
          role: imageIndex === 0 ? "cover" : "article_image",
          source_path: `PROMOPAGES-9857/PROMOPAGES-10060/articles/${articleSlug}/${imageId}.jpg`,
          manifest_file_path: `PROMOPAGES-10060/articles/${articleSlug}/${imageId}.jpg`,
          // Deliberately identical: all-image mode must preserve repeated bytes.
          sha256: "a".repeat(64),
          width: 1200,
          height: 800,
        },
        lite_planning: {
          run_id: `promopages-10060-${articleNumber}-${imageId}`,
          result_path: `artifacts/clipmaker-lite/v1/promopages-10060-${articleNumber}-${imageId}/result.json`,
          structured_intent: { primary_action: "A subtle camera move." },
          provenance: { verified: true, agent_id: "clipmaker-lite" },
        },
        outputs: imageOutputs,
      };
    });
    return {
      article_number: articleNumber,
      article_slug: articleSlug,
      title: `New article ${articleNumber}`,
      url: `https://example.promo.page/media/new-${articleNumber}`,
      context_path: `PROMOPAGES-10060/articles/${articleSlug}/content.json`,
      image_count: imageCount,
      images,
    };
  });
  return {
    schema_version: 1,
    manifest_role: "promopages-10060-all-images",
    ticket: "PROMOPAGES-10060",
    batch_id: "promopages-10060-test",
    agent_id: "clipmaker-lite",
    models,
    article_count: 13,
    image_count: 92,
    expected_outputs: 276,
    accepted_output_count: 275,
    terminal_accounted_output_count: 276,
    provider_filtered_output_count: 1,
    provider_unavailable_output_count: 0,
    status_summary: {
      succeeded: 275,
      "provider-filtered": 1,
      "provider-unavailable": 0,
    },
    acceptance_policy: {
      requires_mp4_and_media: true,
      terminal_accounted_without_media: [
        "provider-filtered",
        "provider-unavailable",
      ],
      provider_filtered_requires_exhausted_retry_v1: true,
      provider_unavailable_requires_ambiguous_submit_retry_v1: true,
      provider_unavailable_requires_retry_v1: [
        "ambiguous-submit",
        "normalized-input",
      ],
    },
    articles,
    outputs,
    unavailable_articles: [
      {
        article_number: "02",
        article_slug: "02-unavailable",
        url: "https://example.promo.page/media/unavailable",
        status: "source-unavailable",
        error: "Article returned HTTP 404.",
      },
    ],
  };
};

const reviewManifestWithProviderUnavailable = () => {
  const manifest = reviewManifest();
  const article = manifest.articles.find((item) => item.article_number === "10");
  const imageRecord = article.images.find((record) => record.image.image_id === "04");
  const nested = imageRecord.outputs.find(
    (output) => output.model_id === "alibaba/wan-2.2",
  );
  const replacement = providerUnavailableOutput(
    article.article_slug,
    imageRecord.image.image_id,
    nested.model_id,
  );
  const flat = manifest.outputs.find(
    (output) =>
      output.article_slug === article.article_slug &&
      output.image_id === imageRecord.image.image_id &&
      output.model_id === nested.model_id,
  );
  Object.assign(nested, replacement);
  Object.assign(flat, replacement);
  manifest.accepted_output_count = 274;
  manifest.provider_unavailable_output_count = 1;
  manifest.status_summary.succeeded = 274;
  manifest.status_summary["provider-unavailable"] = 1;
  return manifest;
};

const reviewManifestWithAmbiguousRetrySuccess = () => {
  const manifest = reviewManifest();
  const article = manifest.articles.find((item) => item.article_number === "10");
  const imageRecord = article.images.find((record) => record.image.image_id === "04");
  const nested = imageRecord.outputs.find(
    (output) => output.model_id === "alibaba/wan-2.2",
  );
  const replacement = ambiguousRetrySuccessOutput(
    article.article_slug,
    imageRecord.image.image_id,
    nested.model_id,
  );
  const flat = manifest.outputs.find(
    (output) =>
      output.article_slug === article.article_slug &&
      output.image_id === imageRecord.image.image_id &&
      output.model_id === nested.model_id,
  );
  Object.assign(nested, replacement);
  Object.assign(flat, replacement);
  return manifest;
};

const reviewManifestWithNormalizedRetry = ({
  modelId = "alibaba/wan-2.2",
  exhausted = false,
} = {}) => {
  const manifest = reviewManifest();
  const article = manifest.articles.find((item) => item.article_number === "12");
  const imageRecord = article.images.find((record) => record.image.image_id === "08");
  Object.assign(imageRecord.image, {
    orig_url: NORMALIZED_ORIGINAL_URL,
    sha256: "2cf03435b0ae53b208f033a4ec407750ed494e0cd6ec6c76e1b36e397dd1377d",
    width: 5445,
    height: 3635,
  });
  const nested = imageRecord.outputs.find((output) => output.model_id === modelId);
  const replacement = normalizedInputRetryOutput(
    article.article_slug,
    imageRecord.image,
    modelId,
    { exhausted },
  );
  const flat = manifest.outputs.find(
    (output) =>
      output.article_slug === article.article_slug &&
      output.image_id === imageRecord.image.image_id &&
      output.model_id === modelId,
  );
  Object.assign(nested, replacement);
  Object.assign(flat, replacement);
  manifest.cost = {
    normalized_input_retry_version: 1,
    normalized_input_retry_accounting_cost_usd: 0.35,
    normalized_input_retry_reservations: 1,
  };
  manifest.generation_policy = {
    normalized_input_retry: {
      version: 1,
      namespace: NORMALIZED_RETRY_NAMESPACE,
      shared_asset_namespace: NORMALIZED_ASSET_NAMESPACE,
      eligible_source: {
        article_slug: "12-dream-island-7-fishek",
        image_id: "08",
      },
      models: ["alibaba/wan-2.2", "alibaba/wan-2.7"],
      explicit_operator_command_required: true,
      maximum_new_paid_submissions_per_eligible_output: 1,
      retry2_forbidden: true,
      automatic_paid_retries: false,
      fallback: false,
      primary_receipts_immutable: true,
      request_delta_only_image_pointer: true,
    },
  };
  if (exhausted) {
    manifest.accepted_output_count -= 1;
    manifest.provider_unavailable_output_count += 1;
    manifest.status_summary.succeeded -= 1;
    manifest.status_summary["provider-unavailable"] += 1;
  }
  return manifest;
};

test("PROMOPAGES-10060 uses a collision-safe case key and keeps legacy links historical", () => {
  const hooks = loadHooks();
  const historical = [
    {
      case_key: "PROMOPAGES-9910:01-old-article",
      legacy_case_key: "01",
      article_number: "01",
      article_slug: "01-old-article",
      sourceTicket: "PROMOPAGES-9910 + PROMOPAGES-9930",
      sourceStatus: "Историческая выборка",
      images: [
        {
          image: {
            image_id: "01",
            source_path: "historical/01.jpg",
            sha256: "a".repeat(64),
          },
          outputs: [
            { video_path: "historical/01.mp4" },
          ],
        },
      ],
    },
  ];
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifest(),
    historical,
  );
  const merged = hooks.__mergeArticleCollections(historical, review.articles);

  assert.equal(review.articles[0].case_key, "PROMOPAGES-10060:01-new-article");
  assert.equal(review.articles[0].article_number, "01");
  assert.equal(review.articles[0].sourceTicket, "PROMOPAGES-10060");
  assert.equal(review.articles[0].sourceStatus, "Готово к просмотру · 4 изобр.");
  assert.equal(hooks.__resolveRequestedArticleIndex(merged, "01"), 0);
  assert.equal(
    hooks.__resolveRequestedArticleIndex(
      merged,
      "PROMOPAGES-10060:01-new-article",
    ),
    1,
  );
  assert.equal(hooks.__resolveRequestedImageIndex(review.articles[0], "04"), 3);
  assert.equal(hooks.__resolveRequestedImageIndex(review.articles[1], "04"), 3);
  assert.equal(hooks.__resolveRequestedImageIndex(review.articles[0], "99"), -1);
  const counts = hooks.__datasetCounts(merged);
  assert.equal(counts.articleCount, 14);
  assert.equal(counts.imageCount, 93);
  assert.equal(counts.videoCount, 277);
  assert.equal(counts.availableVideoCount, 276);
  assert.equal(counts.unavailableOutputCount, 1);
  assert.equal(
    review.articles.find((article) => article.article_number === "07").sourceStatus,
    "Готово частично · 9 изобр. · 1 видео недоступно",
  );
});

test("PROMOPAGES-10060 validation fails closed when Lite provenance is invalid", () => {
  const hooks = loadHooks();
  const manifest = reviewManifest();
  manifest.articles[0].images[0].lite_planning.provenance.verified = false;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(manifest, []),
    /Lite provenance/,
  );
});

test("terminal provider-filtered output keeps its logical slot and renders full two-attempt audit", () => {
  const hooks = loadHooks();
  const review = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  assert.equal(review.filteredOutputCount, 1);
  const article = review.articles.find((item) => item.article_number === "07");
  const imageRecord = article.images.find((record) => record.image.image_id === "06");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "google/veo-3.1-lite",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 2);

  assert.equal(output.providerFiltered, true);
  assert.equal(output.availableVideo, false);
  assert.match(markup, /data-output-kind="provider-filtered"/);
  assert.match(markup, /Veo 3\.1 Lite/);
  assert.match(markup, /Видео недоступно/);
  assert.match(markup, /Основная попытка/);
  assert.match(markup, /Retry-v1 · исчерпан/);
  assert.match(markup, /primary-provider-job/);
  assert.match(markup, /retry-provider-job/);
  assert.match(markup, /content may have been filtered/);
  assert.match(markup, /Immutable request SHA-256/);
  assert.match(markup, /terminal-provider-retries-v1\/filtered-output\/retry\.json/);
  assert.doesNotMatch(markup, /<video/);
  assert.doesNotMatch(markup, /src="[^\"]+\.mp4/);
});

test("terminal provider-filtered validation fails closed on missing audit or changed request", () => {
  const hooks = loadHooks();
  const missingAudit = reviewManifest();
  const missingOutput = missingAudit.articles[5].images[5].outputs[2];
  delete missingOutput.retry.retry_attempt.request_sha256;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(missingAudit, []),
    /request_sha256/,
  );

  const changedRequest = reviewManifest();
  changedRequest.articles[5].images[5].outputs[2].retry.retry_attempt.request_sha256 =
    "9".repeat(64);
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(changedRequest, []),
    /immutable provider request/,
  );

  const genericFailure = reviewManifest();
  genericFailure.articles[5].images[5].outputs[2].status = "provider-failed";
  const flatFailure = genericFailure.outputs.find(
    (output) =>
      output.article_slug === "07-new-article" &&
      output.image_id === "06" &&
      output.model_id === "google/veo-3.1-lite",
  );
  flatFailure.status = "provider-failed";
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(genericFailure, []),
    /неверный статус/,
  );
});

test("successful ambiguous-submit retry remains a normal video with strict audit binding", () => {
  const hooks = loadHooks();
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifestWithAmbiguousRetrySuccess(),
    [],
  );
  const article = review.articles.find((item) => item.article_number === "10");
  const imageRecord = article.images.find((record) => record.image.image_id === "04");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.2",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 0);

  assert.equal(output.availableVideo, true);
  assert.equal(output.providerUnavailable, false);
  assert.equal(hooks.__availableOutputCount(imageRecord.outputs), 3);
  assert.match(markup, /<video/);
  assert.match(markup, /ambiguous-retry\.mp4/);
  assert.doesNotMatch(markup, /data-provider-unavailable/);

  const changedRequest = reviewManifestWithAmbiguousRetrySuccess();
  changedRequest.articles[8].images[3].outputs[0].retry.retry_attempt.request_sha256 =
    "c".repeat(64);
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(changedRequest, []),
    /immutable request/,
  );
});

test("provider-unavailable keeps the logical slot and shows primary unknown plus failed retry", () => {
  const hooks = loadHooks();
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifestWithProviderUnavailable(),
    [],
  );
  assert.equal(review.filteredOutputCount, 1);
  assert.equal(review.providerUnavailableOutputCount, 1);
  assert.equal(review.unavailableOutputCount, 2);

  const article = review.articles.find((item) => item.article_number === "10");
  assert.equal(article.sourceStatus, "Готово частично · 8 изобр. · 1 видео недоступно");
  const imageRecord = article.images.find((record) => record.image.image_id === "04");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.2",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 0);

  assert.equal(output.availableVideo, false);
  assert.equal(output.providerFiltered, false);
  assert.equal(output.providerUnavailable, true);
  assert.equal(hooks.__availableOutputCount(imageRecord.outputs), 2);
  assert.match(markup, /data-output-kind="provider-unavailable"/);
  assert.match(markup, /Outcome основной отправки неизвестен/);
  assert.match(markup, /provider может оставаться активным/);
  assert.match(markup, /Retry-v1 · provider-failed/);
  assert.match(markup, /ambiguous-retry-provider-job/);
  assert.match(markup, /Envelope SHA-256/);
  assert.doesNotMatch(markup, /Обе попытки terminal/);
  assert.doesNotMatch(markup, /<video/);
  assert.doesNotMatch(markup, /src="[^"]+\.mp4/);

  assert.deepEqual(
    { ...hooks.__datasetCounts(review.articles) },
    {
      articleCount: 13,
      imageCount: 92,
      videoCount: 276,
      availableVideoCount: 274,
      unavailableOutputCount: 2,
    },
  );
});

test("provider-unavailable validation fails closed on dishonest ambiguous retry audit", () => {
  const hooks = loadHooks();

  const knownPrimary = reviewManifestWithProviderUnavailable();
  knownPrimary.articles[8].images[3].outputs[0].retry.primary_attempt.outcome_unknown = false;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(knownPrimary, []),
    /primary outcome.*unknown/,
  );

  const activeRetry = reviewManifestWithProviderUnavailable();
  activeRetry.articles[8].images[3].outputs[0].retry.retry_attempt.provider_may_be_active = true;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(activeRetry, []),
    /retry-v1.*terminal selected attempt/,
  );

  const changedRequest = reviewManifestWithProviderUnavailable();
  changedRequest.articles[8].images[3].outputs[0].retry.retry_attempt.request_sha256 =
    "c".repeat(64);
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(changedRequest, []),
    /immutable request/,
  );

  const fakeMedia = reviewManifestWithProviderUnavailable();
  fakeMedia.articles[8].images[3].outputs[0].video_path = "unexpected.mp4";
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(fakeMedia, []),
    /не должен содержать MP4/,
  );
});

test("successful normalized-input retry renders video with exact source and request-delta audit", () => {
  const hooks = loadHooks();
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifestWithNormalizedRetry(),
    [],
  );
  assert.equal(review.normalizedInputRetryOutputCount, 1);
  assert.equal(review.providerUnavailableOutputCount, 0);
  const article = review.articles.find((item) => item.article_number === "12");
  const imageRecord = article.images.find((record) => record.image.image_id === "08");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.2",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 0);

  assert.equal(output.availableVideo, true);
  assert.equal(output.normalizedInputRetry, true);
  assert.match(markup, /<video/);
  assert.match(markup, /wan22-normalized\.mp4/);
  assert.match(markup, /Source normalized/);
  assert.match(markup, /Исходник нормализован из-за размера больше 20 MiB/);
  assert.match(markup, /Prompt и модель сохранены/);
  assert.match(markup, /\/input\/image/);
  assert.match(markup, /22,4[^<]*МиБ/);
  assert.match(markup, /5445×3635/);
  assert.match(markup, /1200×801/);
  assert.match(markup, /shared-asset\/asset\.json/);
  assert.doesNotMatch(markup, /data-provider-unavailable/);
});

test("provider-unavailable normalized-input retry keeps audit but never renders video", () => {
  const hooks = loadHooks();
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifestWithNormalizedRetry({
      modelId: "alibaba/wan-2.7",
      exhausted: true,
    }),
    [],
  );
  assert.equal(review.normalizedInputRetryOutputCount, 1);
  assert.equal(review.providerUnavailableOutputCount, 1);
  const article = review.articles.find((item) => item.article_number === "12");
  const imageRecord = article.images.find((record) => record.image.image_id === "08");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.7",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 1);

  assert.equal(output.availableVideo, false);
  assert.equal(output.providerUnavailable, true);
  assert.equal(output.normalizedInputRetry, true);
  assert.match(markup, /data-retry-kind="normalized-input"/);
  assert.match(markup, /Normalized-input retry завершился без MP4/);
  assert.match(markup, /\/frame_images\/0\/image_url\/url/);
  assert.match(markup, /Primary failure и normalized-input retry-v1/);
  assert.match(markup, /wan27-normalized-retry-job/);
  assert.doesNotMatch(markup, /<video/);
  assert.doesNotMatch(markup, /src="[^"]+\.mp4/);
});

test("normalized-input validation fails closed on source, delta, request, policy and media drift", () => {
  const hooks = loadHooks();

  const sourceDrift = reviewManifestWithNormalizedRetry();
  sourceDrift.articles[10].images[7].image.sha256 = "9".repeat(64);
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(sourceDrift, []),
    /original source audit/,
  );

  const oversizedNormalized = reviewManifestWithNormalizedRetry();
  oversizedNormalized.articles[10].images[7].outputs[0].retry.source_transform.normalized.bytes =
    20 * 1024 * 1024 + 1;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(oversizedNormalized, []),
    /normalized source audit/,
  );

  const extraDelta = reviewManifestWithNormalizedRetry();
  extraDelta.articles[10].images[7].outputs[0].retry.source_transform.request_delta.extra =
    "not allowed";
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(extraDelta, []),
    /request delta/,
  );

  const sameRequest = reviewManifestWithNormalizedRetry();
  const retry = sameRequest.articles[10].images[7].outputs[0].retry;
  retry.retry_attempt.request_sha256 = retry.primary_attempt.request_sha256;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(sameRequest, []),
    /request binding/,
  );

  const badPolicy = reviewManifestWithNormalizedRetry();
  badPolicy.generation_policy.normalized_input_retry.namespace = "wrong/namespace";
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(badPolicy, []),
    /разрешённые namespaces/,
  );

  const fakeMedia = reviewManifestWithNormalizedRetry({
    modelId: "alibaba/wan-2.7",
    exhausted: true,
  });
  fakeMedia.articles[10].images[7].outputs[1].video_path = "unexpected.mp4";
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(fakeMedia, []),
    /не должен содержать MP4/,
  );
});

test("all-image sidecar produces the final 34 / 133 / 415 demo totals", () => {
  const hooks = loadHooks();
  let historicalImageNumber = 0;
  let researchVideoNumber = 0;
  const historical = Array.from({ length: 21 }, (_, articleIndex) => {
    const imageCount = articleIndex < 20 ? 2 : 1;
    const images = Array.from({ length: imageCount }, (_, imageIndex) => {
      historicalImageNumber += 1;
      const outputs = Array.from({ length: 3 }, (_, modelIndex) => ({
        video_path: `historical/canonical-${historicalImageNumber}-${modelIndex + 1}.mp4`,
      }));
      const research_outputs = researchVideoNumber < 16
        ? [{ video_path: `historical/research-${++researchVideoNumber}.mp4` }]
        : [];
      return {
        image: {
          image_id: String(imageIndex + 1).padStart(2, "0"),
          source_path: `historical/article-${articleIndex + 1}/image-${imageIndex + 1}.jpg`,
        },
        outputs,
        research_outputs,
      };
    });
    return {
      case_key: `PROMOPAGES-9910:historical-${articleIndex + 1}`,
      article_slug: `historical-${articleIndex + 1}`,
      images,
    };
  });
  const review = hooks.__validatePromopages10060Manifest(
    reviewManifest(),
    historical,
  );
  const merged = hooks.__mergeArticleCollections(historical, review.articles);
  const counts = hooks.__datasetCounts(merged);

  assert.equal(historicalImageNumber, 41);
  assert.equal(researchVideoNumber, 16);
  assert.deepEqual(
    { ...counts },
    {
      articleCount: 34,
      imageCount: 133,
      videoCount: 415,
      availableVideoCount: 414,
      unavailableOutputCount: 1,
    },
  );
});


test("actual five-attempt smooth retry schema validates and rank five is retained", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );

  assert.equal(normalized.outputs.length, 4);
  assert.equal(normalized.attempt_history.length, 5);
  assert.equal(
    normalized.attempt_history.filter(
      (attempt) => attempt.activity === "smooth-motion-explicit-retry",
    ).length,
    1,
  );
  assert.ok(normalized.outputs.some((output) => output.motionProxy.rank === 5));
  assert.ok(normalized.outputs.every((output) => output.motionProxy.rankScale === 5));
});

test("smooth retry identity and proxy rank fail closed", () => {
  const hooks = loadHooks();
  const wrongActivity = clone(actualSmoothExperiment());
  wrongActivity.attempt_history[4].activity = "smooth-motion-experiment";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongActivity, new Set()),
    /identity smooth-попытки 5/,
  );

  const wrongSeries = clone(actualSmoothExperiment());
  wrongSeries.attempt_history[4].series_experiment_id = "wrong-series";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongSeries, new Set()),
    /identity smooth-попытки 5/,
  );

  const wrongRank = clone(actualSmoothExperiment());
  wrongRank.outputs[0].smooth_motion.proxy_review.proxy_rank = 6;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongRank, new Set()),
    /motion proxy review/,
  );
});

test("smooth featured review binds fail closed to the selected retry", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  assert.equal(normalized.featuredReview.status, "visual-winner");
  assert.equal(normalized.featuredReview.variant_id, "staggered-ease-retry1");
  assert.equal(normalized.outputs.filter((output) => output.isFeaturedWinner).length, 1);

  const wrongRun = clone(actualSmoothExperiment());
  wrongRun.featured_review.provider_run_id = wrongRun.outputs[0].provider_run_id;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongRun, new Set()),
    /featured review/,
  );

  const wrongPractice = clone(actualSmoothExperiment());
  wrongPractice.featured_review.practices[0].id = "generic-smoothness";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongPractice, new Set()),
    /featured review/,
  );

  const wrongEvidence = clone(actualSmoothExperiment());
  wrongEvidence.featured_review.evidence.motion_energy_spike_count = 1;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongEvidence, new Set()),
    /featured review/,
  );
});

test("featured callout explains visual selection and prompt practices", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const markup = hooks.__renderSmoothFeaturedReview(normalized.featuredReview);

  assert.match(markup, /Визуальный победитель · Staggered retry/);
  assert.match(markup, /Motion coverage[\s\S]*7\/7/);
  assert.match(markup, /Abrupt transitions[\s\S]*0/);
  assert.match(markup, /Motion spikes[\s\S]*0/);
  assert.match(markup, /Proxy rank[\s\S]*2\/5/);
  assert.match(markup, /Победитель выбран визуально/);
  assert.match(markup, /Part-level invariants/);
  assert.match(markup, /Ключевое отличие prompt/);
  assert.match(markup, /clock\/dial substitution/);
});

test("rendered smooth video is muted but has no loop semantics", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const markup = hooks.__renderModel(
    { article_number: "21", title: "Case 21" },
    { image: { image_id: "04" } },
    normalized.outputs[0],
    0,
    {
      idPrefix: "smoothModel",
      loopPlayback: false,
      smoothExperiment: true,
      headingLevel: 4,
    },
  );
  const videoTag = markup.match(/<video[\s\S]*?>/)[0];
  assert.match(videoTag, /\smuted(?:\s|>)/);
  assert.doesNotMatch(videoTag, /\sloop(?:\s|>)/);
  assert.doesNotMatch(videoTag, /data-loop-output/);
});

test("featured retry card has a winner badge and its exact negative prompt", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const winner = normalized.outputs.find((output) => output.isFeaturedWinner);
  const markup = hooks.__renderModel(
    { article_number: "21", title: "Case 21" },
    { image: { image_id: "04" } },
    winner,
    3,
    {
      idPrefix: "smoothModel",
      loopPlayback: false,
      smoothExperiment: true,
      headingLevel: 4,
    },
  );

  assert.match(markup, /data-featured-winner="true"/);
  assert.match(markup, /class="winnerBadge">Визуальный победитель/);
  assert.match(markup, /Дословный negative prompt/);
  assert.match(markup, /No clock or dial substitution/);
});
