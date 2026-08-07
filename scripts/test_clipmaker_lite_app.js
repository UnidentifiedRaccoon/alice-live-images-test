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
const PROMOPAGES_10060_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "promopages-10060-manifest.json",
);
const PROMOPAGES_10060_EXTENSION_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "promopages-10060-campaigns-20260805-v1-manifest.json",
);
const PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "promopages-10060-article-02-20260806-v2-manifest.json",
);
const PROMOPAGES_10060_CAMPAIGN_20260807_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "promopages-10060-campaigns-20260807-v1-manifest.json",
);
const PROMOPAGES_10060_S3_DELIVERY_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "promopages-10060-s3-delivery.json",
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
        "  globalThis.__sortPromopages10060Articles = sortPromopages10060Articles;\n" +
      "  globalThis.__mergeUnavailableArticleCollections = mergeUnavailableArticleCollections;\n" +
        "  globalThis.__validatePromopages10060S3Delivery = validatePromopages10060S3Delivery;\n" +
        "  globalThis.__datasetCounts = datasetCounts;\n" +
        "  globalThis.__availableOutputCount = availableOutputCount;\n" +
        "  globalThis.__resolveRequestedArticleIndex = resolveRequestedArticleIndex;\n\n" +
        "  globalThis.__resolveRequestedMediaPosition = resolveRequestedMediaPosition;\n\n" +
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
const loadJson = (filePath) => JSON.parse(fs.readFileSync(filePath, "utf8"));

const actualPromopages10060Articles = (hooks) => {
  const legacy = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_MANIFEST_PATH),
    [],
  );
  const extension = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_EXTENSION_MANIFEST_PATH),
    legacy.articles,
    { extension: true },
  );
  const article02 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH),
    [...legacy.articles, ...extension.articles],
    { article02: true },
  );
  const campaign20260807 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_CAMPAIGN_20260807_MANIFEST_PATH),
    [...legacy.articles, ...extension.articles, ...article02.articles],
    { campaign20260807: true },
  );
  return hooks.__sortPromopages10060Articles([
    ...legacy.articles,
    ...extension.articles,
    ...article02.articles,
    ...campaign20260807.articles,
  ]);
};

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
const EXTENSION_BATCH_ID = "promopages-10060-campaigns-20260805-v1";
const EXTENSION_RETRY_NAMESPACE =
  `clipmaker-lite-test/runs/${EXTENSION_BATCH_ID}/normalized-input-retries-v1`;
const EXTENSION_ASSET_NAMESPACE =
  `clipmaker-lite-test/runs/${EXTENSION_BATCH_ID}/normalized-input-assets-v1`;
const EXTENSION_SOURCE_COMMIT = "25995ee6ea168d2ae7025e5a416bc008ae17a908";
const EXTENSION_SUPERSEDED_RUN_ID =
  "promopages-10060-campaigns-20260805-v1-normalized-input-retry-v1-c45a8447813d1b4e4df0-18-volma-plitochnyi-klei-07-wan-2-7";
const EXTENSION_SUPERSEDED_JOB_ID = "novcFDcwbuZkgtrmgQIY";
const EXTENSION_NORMALIZED_SOURCES = {
  "05": {
    file: "05.png",
    orig_url:
      "https://avatars.mds.yandex.net/get-promoarticles/5400274/pub_6a267e54c6621a31e5630a18_6a2682a081cbac61b6b77c7f/orig",
    source_sha256:
      "95a38e9469f6055c7eab934ab7173af57d5445112e835e200a83964f74938543",
    source_bytes: 17_569,
    source_width: 758,
    source_height: 220,
    asset_key: "660c32c4d1331cb3a82d",
    sha256:
      "4ad98c730c783a63bce382ecffe640d51c936b3ccaec019b637861f8ddbf5b23",
    bytes: 46_883,
    width: 882,
    height: 256,
    format: "PNG",
  },
  "07": {
    file: "07.png",
    orig_url:
      "https://avatars.mds.yandex.net/get-promoarticles/5096941/pub_6a267e54c6621a31e5630a18_6a269812b55c4222ecf7445c/orig",
    source_sha256:
      "07fd4373396697d3078265a72337a759d591449deb6cafe9869e9d2f92fb43e8",
    source_bytes: 27_754,
    source_width: 773,
    source_height: 239,
    asset_key: "0535f187b92384618210",
    sha256:
      "7f71227971a99ca0f204eccadb89a706128eabfb6022657bf8718e952fca70e4",
    bytes: 57_771,
    width: 828,
    height: 256,
    format: "PNG",
  },
  "08": {
    file: "08.jpeg",
    orig_url:
      "https://avatars.mds.yandex.net/get-promoarticles/5400274/pub_6a267e54c6621a31e5630a18_6a267e6fc6621a31e5630ed8/orig",
    source_sha256:
      "ff2fa123c99e8b82a954af9870660faa5306e3d6ebb7c57675df542077fbaa03",
    source_bytes: 30_852,
    source_width: 752,
    source_height: 193,
    asset_key: "2d974dbe489b2e6617a3",
    sha256:
      "1a005159d7efaee55f2124844851b7135f28cccfcad0463ad1ac2f5dec1f589a",
    bytes: 246_119,
    width: 998,
    height: 256,
    format: "PNG",
  },
};

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

const campaignExtensionManifest = () => {
  const source = reviewManifest();
  const article = clone(source.articles[0]);
  const oldSlug = article.article_slug;
  const articleSlug = "15-campaign-6a3d17575c59bd0e6d046aa6";
  article.article_number = "15";
  article.article_slug = articleSlug;
  article.title = "Campaign article 15";
  article.url = "https://example.promo.page/media/campaign-15";
  article.context_path =
    `PROMOPAGES-9884/PROMOPAGES-10060-campaigns-20260805-v1/articles/${articleSlug}/content.json`;
  article.images.forEach((record) => {
    record.image.source_path = record.image.source_path.replace(oldSlug, articleSlug);
    record.image.manifest_file_path =
      `PROMOPAGES-10060-campaigns-20260805-v1/articles/${articleSlug}/${record.image.file}`;
    record.lite_planning.run_id = record.lite_planning.run_id.replace("-01-", "-15-");
    record.lite_planning.result_path = record.lite_planning.result_path.replace(
      "-01-",
      "-15-",
    );
    record.outputs.forEach((output) => {
      output.article_slug = articleSlug;
      output.video_path = output.video_path.replace("/01-", "/15-");
    });
  });
  const outputs = article.images.flatMap((record) => record.outputs.map(clone));
  return {
    schema_version: 1,
    manifest_role: "promopages-10060-campaign-extension",
    ticket: "PROMOPAGES-10060",
    batch_id: "promopages-10060-campaigns-20260805-v1",
    agent_id: "clipmaker-lite",
    models: source.models,
    article_count: 1,
    image_count: article.image_count,
    expected_outputs: outputs.length,
    accepted_output_count: outputs.length,
    terminal_accounted_output_count: outputs.length,
    provider_filtered_output_count: 0,
    provider_unavailable_output_count: 0,
    status_summary: {
      succeeded: outputs.length,
    },
    acceptance_policy: source.acceptance_policy,
    articles: [article],
    outputs,
    unavailable_articles: ["16", "17", "18"].map((number) => ({
      article_number: number,
      article_slug: `${number}-unavailable-campaign`,
      url: `https://example.promo.page/media/campaign-${number}`,
      status: "source-unavailable",
      error: "Article source is unavailable.",
    })),
  };
};

const campaign20260807Manifest = () => {
  const manifest = campaignExtensionManifest();
  const article = manifest.articles[0];
  const oldSlug = article.article_slug;
  const articleSlug = "19-pixel24-ekshn-kamery";
  article.article_number = "19";
  article.article_slug = articleSlug;
  article.title = "Стоп-кадр и другие классные фишки экшн-камер в Pixel24";
  article.url = "https://pixel24.promo.page/promo/campaign-19";
  article.context_path =
    `PROMOPAGES-9884/PROMOPAGES-10060-campaigns-20260807-v1/articles/${articleSlug}/content.json`;
  article.images.forEach((record) => {
    record.image.source_path = record.image.source_path
      .replace(oldSlug, articleSlug)
      .replace("campaigns-20260805-v1", "campaigns-20260807-v1");
    record.image.manifest_file_path =
      `PROMOPAGES-10060-campaigns-20260807-v1/articles/${articleSlug}/${record.image.file}`;
    record.outputs.forEach((output) => {
      output.article_slug = articleSlug;
      output.video_path = output.video_path
        .replace(oldSlug, articleSlug)
        .replace("/15-", "/19-")
        .replace("campaigns-20260805-v1", "campaigns-20260807-v1");
    });
  });
  manifest.outputs = article.images.flatMap((record) => record.outputs.map(clone));
  manifest.manifest_role = "promopages-10060-campaigns-20260807-extension";
  manifest.batch_id = "promopages-10060-campaigns-20260807-v1";
  manifest.unavailable_articles = ["20", "21"].map((number) => ({
    article_number: number,
    article_slug: `${number}-unavailable-campaign`,
    url: `https://example.promo.page/media/campaign-${number}`,
    status: "source-unavailable",
    error: "Article source is unavailable.",
  }));
  return manifest;
};

const extensionNormalizedRetryOutput = (articleSlug, image, modelId) => {
  const asset = EXTENSION_NORMALIZED_SOURCES[image.image_id];
  const modelSuffix = modelId === "alibaba/wan-2.2" ? "wan-2.2" : "wan-2.7";
  const retryKey =
    image.image_id === "07" && modelId === "alibaba/wan-2.7"
      ? "c45a8447813d1b4e4df0"
      : `${image.image_id}-${modelSuffix}-retry-key`;
  const namespace = `${EXTENSION_RETRY_NAMESPACE}/${retryKey}`;
  const assetParent = `${EXTENSION_ASSET_NAMESPACE}/${asset.asset_key}`;
  const normalizedUrl =
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/" +
    `alice-live-images-test/${EXTENSION_SOURCE_COMMIT}/${assetParent}/normalized.png`;
  const providerRunId =
    retryKey === "c45a8447813d1b4e4df0"
      ? EXTENSION_SUPERSEDED_RUN_ID
      : `${image.image_id}-${modelSuffix}-normalized-retry`;
  const acceptedStatus =
    modelId === "alibaba/wan-2.2" ? "succeeded" : "verification-failed";
  const acceptedError =
    acceptedStatus === "succeeded"
      ? null
      : "Media contract verification failed: audio, resolution, aspect_ratio";
  const primary = {
    provider_run_id: `${image.image_id}-${modelSuffix}-primary`,
    provider_job_id: `${image.image_id}-${modelSuffix}-primary-job`,
    status: "provider-failed",
    recorded_status:
      modelId === "alibaba/wan-2.2" ? "submit-unknown" : "provider-failed",
    provider_may_be_active: false,
    recorded_provider_may_be_active: modelId === "alibaba/wan-2.2",
    submitted_at:
      modelId === "alibaba/wan-2.2" ? null : "2026-08-05T18:00:00Z",
    completed_at:
      modelId === "alibaba/wan-2.2" ? null : "2026-08-05T18:01:00Z",
    error:
      modelId === "alibaba/wan-2.2"
        ? "Image height or width is too small than 240"
        : `Error validating image resolution: resolution must be at least 240x240, got ${image.width}x${image.height}`,
    run_path: `runs/${image.image_id}-${modelSuffix}-primary.run.json`,
    run_sha256: "1".repeat(64),
    prompt_path: `runs/${image.image_id}-${modelSuffix}-primary.prompt.json`,
    prompt_sha256: "2".repeat(64),
    request_sha256: "3".repeat(64),
  };
  if (modelId === "alibaba/wan-2.2") {
    Object.assign(primary, {
      provider_submit_time: "2026-08-05 18:00:00.000",
      provider_scheduled_time: "2026-08-05 18:00:00.010",
      provider_end_time: "2026-08-05 18:00:01.000",
    });
  }
  return {
    article_slug: articleSlug,
    image_id: image.image_id,
    source_path: image.source_path,
    model_id: modelId,
    provider_run_id: providerRunId,
    positive_prompt: "Keep the source stable with restrained motion.",
    negative_prompt: "Do not alter the composition.",
    status: acceptedStatus,
    recorded_status: acceptedStatus,
    selected_attempt: "normalized-input-retry-v1",
    video_path:
      `clipmaker-lite-test/runs/${EXTENSION_BATCH_ID}/videos/` +
      `${articleSlug}/${modelSuffix}/${image.image_id}.mp4`,
    media: { width: 1280, height: 720, duration_seconds: 5, bytes: 2048 },
    contract_check:
      acceptedStatus === "succeeded"
        ? { conforms: true, warnings: [] }
        : {
            conforms: false,
            warnings: ["audio", "resolution", "aspect_ratio"],
          },
    error: acceptedError,
    retry: {
      retry_kind: "normalized-input",
      retry_number: 1,
      namespace,
      envelope_path: `${namespace}/retry.json`,
      envelope_sha256: "4".repeat(64),
      exhausted: false,
      primary_attempt: primary,
      retry_attempt: {
        provider_run_id: providerRunId,
        provider_job_id: `${providerRunId}-job`,
        status: acceptedStatus,
        provider_may_be_active: false,
        submitted_at: "2026-08-05T18:02:00Z",
        completed_at: "2026-08-05T18:03:00Z",
        error: acceptedError,
        run_path: `runs/${retryKey}.run.json`,
        run_sha256: "5".repeat(64),
        prompt_path: `runs/${retryKey}.prompt.json`,
        prompt_sha256: "6".repeat(64),
        request_sha256: "7".repeat(64),
      },
      source_transform: {
        strategy: "deterministic-uniform-upscale",
        original: {
          url: image.orig_url,
          path: image.source_path,
          sha256: image.sha256,
          bytes: image.bytes,
          width: image.width,
          height: image.height,
        },
        normalized: {
          http_status: 200,
          url: normalizedUrl,
          sha256: asset.sha256,
          bytes: asset.bytes,
          width: asset.width,
          height: asset.height,
          format: asset.format,
          delivery: "repository-raw",
          repository_path: `${assetParent}/normalized.png`,
          source_commit_sha: EXTENSION_SOURCE_COMMIT,
          metadata_path: `${assetParent}/asset.json`,
          metadata_sha256: image.image_id.repeat(32),
        },
        request_delta: {
          json_pointer:
            modelId === "alibaba/wan-2.2"
              ? "/input/image"
              : "/frame_images/0/image_url/url",
          from: image.orig_url,
          to: normalizedUrl,
          changed_leaf_count: 1,
        },
        preparation: {
          operation: "uniform-scale",
          target_height: asset.height,
          resampler: "lanczos",
          crop: false,
          local_reencode: true,
        },
        minimum_provider_input_dimension: 240,
      },
    },
  };
};

const extensionSupersedeOutput = (sourceOutput) => {
  const output = clone(sourceOutput);
  const supersedeNamespace = `${output.retry.namespace}/superseding-attempt-v1`;
  const superseded = clone(output.retry.retry_attempt);
  Object.assign(superseded, {
    provider_run_id: EXTENSION_SUPERSEDED_RUN_ID,
    provider_job_id: EXTENSION_SUPERSEDED_JOB_ID,
    status: "running",
    provider_may_be_active: true,
    completed_at: null,
    error: null,
  });
  const selected = {
    provider_run_id:
      "promopages-10060-campaigns-20260805-v1-normalized-input-supersede-v1-658980e5ab1ada676dbe-18-volma-plitochnyi-klei-07-wan-2-7",
    provider_job_id: "replacement-wan27-job",
    status: output.recorded_status,
    provider_may_be_active: false,
    submitted_at: "2026-08-06T02:00:00Z",
    completed_at: "2026-08-06T02:03:00Z",
    error: output.error,
    run_path: `${supersedeNamespace}/videos/wan-2.7/07.run.json`,
    run_sha256: "8".repeat(64),
    prompt_path: `${supersedeNamespace}/videos/wan-2.7/07.prompt.json`,
    prompt_sha256: "9".repeat(64),
    request_sha256: superseded.request_sha256,
  };
  Object.assign(output, {
    provider_run_id: selected.provider_run_id,
    selected_attempt: "normalized-input-superseding-attempt-v1",
    video_path: `${supersedeNamespace}/videos/wan-2.7/07.mp4`,
  });
  output.retry.retry_attempt = clone(superseded);
  output.retry.supersede = {
    version: 1,
    namespace: supersedeNamespace,
    envelope_path: `${supersedeNamespace}/supersede.json`,
    envelope_sha256: "a".repeat(64),
    exhausted: false,
    superseded_attempt: superseded,
    superseding_attempt: selected,
  };
  return output;
};

const extensionSupersedePolicy = () => ({
  version: 1,
  namespace:
    `${EXTENSION_RETRY_NAMESPACE}/c45a8447813d1b4e4df0/superseding-attempt-v1`,
  explicit_operator_command_required: true,
  operator_authorized_active_job: true,
  automatic_retry: false,
  maximum_new_paid_submissions: 1,
  retry2_forbidden: true,
  one_off_allowlist: {
    article_slug: "18-volma-plitochnyi-klei",
    image_id: "07",
    model_id: "alibaba/wan-2.7",
    normalized_retry_provider_run_id: EXTENSION_SUPERSEDED_RUN_ID,
    active_provider_job_id: EXTENSION_SUPERSEDED_JOB_ID,
  },
  duplicate_submission_risk_acknowledged: true,
  duplicate_billing_risk_acknowledged: true,
  same_verified_lite_result: true,
  same_normalized_source: true,
  same_prompt: true,
  same_model: true,
  same_route: true,
  same_seed: true,
  same_request: true,
  fallback: false,
  route_discovery: false,
  primary_receipt_immutable: true,
  normalized_retry_envelope_immutable: true,
  superseded_receipt_immutable: true,
});

const campaignNormalizedExtensionManifest = () => {
  const articleSlug = "18-volma-plitochnyi-klei";
  const models = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
  ];
  const records = Object.entries(EXTENSION_NORMALIZED_SOURCES).map(
    ([imageId, source]) => {
      const sourcePath =
        `PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260805-v1/articles/` +
        `${articleSlug}/${source.file}`;
      const image = {
        image_id: imageId,
        file: source.file,
        role: "article_image",
        source_path: sourcePath,
        manifest_file_path:
          `PROMOPAGES-10060-campaigns-20260805-v1/articles/` +
          `${articleSlug}/${source.file}`,
        orig_url: source.orig_url,
        sha256: source.source_sha256,
        bytes: source.source_bytes,
        width: source.source_width,
        height: source.source_height,
      };
      const outputs = models.map((modelId) => {
        if (modelId !== "google/veo-3.1-lite") {
          return extensionNormalizedRetryOutput(articleSlug, image, modelId);
        }
        return {
          article_slug: articleSlug,
          image_id: imageId,
          source_path: sourcePath,
          model_id: modelId,
          provider_run_id: `${imageId}-veo-primary`,
          positive_prompt: "Keep the source stable.",
          negative_prompt: "",
          status: "succeeded",
          recorded_status: "succeeded",
          selected_attempt: "primary",
          video_path:
            `clipmaker-lite-test/runs/${EXTENSION_BATCH_ID}/videos/` +
            `${articleSlug}/veo-3.1-lite/${imageId}.mp4`,
          media: { width: 1280, height: 720, duration_seconds: 5, bytes: 2048 },
          contract_check: { conforms: true, warnings: [] },
          error: null,
          retry: null,
        };
      });
      return {
        image,
        lite_planning: {
          run_id: `extension-${articleSlug}-${imageId}`,
          result_path: `artifacts/clipmaker-lite/v1/${articleSlug}-${imageId}/result.json`,
          structured_intent: { primary_action: "Subtle motion." },
          provenance: { verified: true, agent_id: "clipmaker-lite" },
        },
        outputs,
      };
    },
  );
  const record07 = records.find((record) => record.image.image_id === "07");
  const wan27Index = record07.outputs.findIndex(
    (output) => output.model_id === "alibaba/wan-2.7",
  );
  record07.outputs[wan27Index] = extensionSupersedeOutput(
    record07.outputs[wan27Index],
  );
  const outputs = records.flatMap((record) => record.outputs.map(clone));
  const eligibleSources = Object.entries(EXTENSION_NORMALIZED_SOURCES).map(
    ([imageId, source]) => ({
      article_slug: articleSlug,
      image_id: imageId,
      source_sha256: source.source_sha256,
      models: ["alibaba/wan-2.2", "alibaba/wan-2.7"],
      failure_kind: "minimum-dimension",
      normalization_strategy: "deterministic-uniform-upscale",
    }),
  );
  return {
    schema_version: 1,
    manifest_role: "promopages-10060-campaign-extension",
    ticket: "PROMOPAGES-10060",
    batch_id: EXTENSION_BATCH_ID,
    agent_id: "clipmaker-lite",
    models,
    article_count: 1,
    image_count: 3,
    expected_outputs: 9,
    accepted_output_count: 9,
    terminal_accounted_output_count: 9,
    provider_filtered_output_count: 0,
    provider_unavailable_output_count: 0,
    status_summary: { succeeded: 6, "verification-failed": 3 },
    acceptance_policy: reviewManifest().acceptance_policy,
    cost: {
      terminal_retry_reservations: 0,
      ambiguous_submit_retry_reservations: 0,
      normalized_input_retry_version: 1,
      normalized_input_retry_accounting_cost_usd: 0.35,
      normalized_input_retry_reservations: 6,
      normalized_input_supersede_version: 1,
      normalized_input_supersede_accounting_cost_usd: 0.35,
      normalized_input_supersede_reservations: 1,
      maximum_new_paid_submissions_per_superseded_output: 1,
      total_retry_reservations: 7,
      maximum_new_paid_submissions_per_normalized_input_output: 1,
      automatic_paid_retries: false,
    },
    generation_policy: {
      normalized_input_retry: {
        version: 1,
        namespace: EXTENSION_RETRY_NAMESPACE,
        shared_asset_namespace: EXTENSION_ASSET_NAMESPACE,
        eligible_sources: eligibleSources,
        explicit_operator_command_required: true,
        maximum_new_paid_submissions_per_eligible_output: 1,
        retry2_forbidden: true,
        automatic_paid_retries: false,
        fallback: false,
        primary_receipts_immutable: true,
        request_delta_only_image_pointer: true,
      },
      normalized_input_supersede: extensionSupersedePolicy(),
    },
    articles: [
      {
        article_number: "18",
        article_slug: articleSlug,
        title: "Плиточный клей: 5 вопросов экспертам по ремонту",
        url: "https://volma.promo.page/promo/example",
        context_path:
          `PROMOPAGES-9884/PROMOPAGES-10060-campaigns-20260805-v1/articles/` +
          `${articleSlug}/content.json`,
        image_count: records.length,
        images: records,
      },
    ],
    outputs,
    unavailable_articles: ["15", "16", "17"].map((number) => ({
      article_number: number,
      article_slug: `${number}-unavailable-campaign`,
      url: `https://example.promo.page/media/campaign-${number}`,
      status: "source-unavailable",
      error: "Article source is unavailable.",
    })),
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
  assert.deepEqual(
    { ...hooks.__resolveRequestedMediaPosition(merged[1], "04") },
    { mediaBlockIndex: 3, frameIndex: 0 },
  );
  assert.deepEqual(
    { ...hooks.__resolveRequestedMediaPosition(merged[2], "04") },
    { mediaBlockIndex: 3, frameIndex: 0 },
  );
  assert.equal(hooks.__resolveRequestedMediaPosition(merged[1], "99"), null);
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

test("legacy PROMOPAGES-10060 keeps the frozen 13 / 92 / 276 audit", () => {
  const hooks = loadHooks();
  const manifest = reviewManifest();
  manifest.image_count = 93;
  assert.throws(
    () => hooks.__validatePromopages10060Manifest(manifest, []),
    /legacy audit.*13 \/ 92 \/ 276/,
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

test("historical library and A/B preparation expose separate dataset totals", () => {
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
  const historicalLibrary = hooks.__mergeArticleCollections(historical, []);
  const abPreparation = hooks.__mergeArticleCollections([], review.articles);
  const historicalCounts = hooks.__datasetCounts(historicalLibrary);
  const abPreparationCounts = hooks.__datasetCounts(abPreparation);

  assert.equal(historicalImageNumber, 41);
  assert.equal(researchVideoNumber, 16);
  assert.deepEqual(
    { ...historicalCounts },
    {
      articleCount: 21,
      imageCount: 41,
      videoCount: 139,
      availableVideoCount: 139,
      unavailableOutputCount: 0,
    },
  );
  assert.deepEqual(
    { ...abPreparationCounts },
    {
      articleCount: 13,
      imageCount: 92,
      videoCount: 276,
      availableVideoCount: 275,
      unavailableOutputCount: 1,
    },
  );
});

test("campaign extension is optional, additive, and derives aggregate counts", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  const extensionManifest = campaignExtensionManifest();
  const extension = hooks.__validatePromopages10060Manifest(
    extensionManifest,
    legacy.articles,
    { extension: true },
  );
  const merged = hooks.__mergeArticleCollections(legacy.articles, extension.articles);
  const unavailable = hooks.__mergeUnavailableArticleCollections(
    merged,
    legacy.unavailableArticles,
    extension.unavailableArticles,
  );

  assert.deepEqual(
    { ...hooks.__datasetCounts(merged) },
    {
      articleCount: 14,
      imageCount: 96,
      videoCount: 288,
      availableVideoCount: 287,
      unavailableOutputCount: 1,
    },
  );
  assert.equal(unavailable.length, 4);
  assert.equal(extension.articles[0].case_key, "PROMOPAGES-10060:15-campaign-6a3d17575c59bd0e6d046aa6");
});

test("campaigns 20260807 sidecar is isolated and accounts for articles 19–21", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  const extension = hooks.__validatePromopages10060Manifest(
    campaignExtensionManifest(),
    legacy.articles,
    { extension: true },
  );
  const campaign20260807 = hooks.__validatePromopages10060Manifest(
    campaign20260807Manifest(),
    [...legacy.articles, ...extension.articles],
    { campaign20260807: true },
  );

  assert.equal(campaign20260807.articles[0].article_number, "19");
  assert.equal(
    campaign20260807.articles[0].sourceBatchId,
    "promopages-10060-campaigns-20260807-v1",
  );
  assert.deepEqual(
    [...campaign20260807.unavailableArticles].map(
      (article) => article.article_number,
    ),
    ["20", "21"],
  );
});

test("article 02 sidecar exactly replaces legacy unavailable and completes 18 / 137 / 411", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_MANIFEST_PATH),
    [],
  );
  const extension = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_EXTENSION_MANIFEST_PATH),
    legacy.articles,
    { extension: true },
  );
  const article02 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH),
    [...legacy.articles, ...extension.articles],
    { article02: true },
  );
  const articles = hooks.__sortPromopages10060Articles([
    ...legacy.articles,
    ...extension.articles,
    ...article02.articles,
  ]);
  const unavailable = hooks.__mergeUnavailableArticleCollections(
    articles,
    legacy.unavailableArticles,
    extension.unavailableArticles,
    article02.unavailableArticles,
  );

  assert.deepEqual(
    [...articles].map((article) => article.article_number),
    Array.from({ length: 18 }, (_, index) => String(index + 1).padStart(2, "0")),
  );
  assert.equal(articles[1].article_slug, "02-level-rabotaiu-v-level");
  assert.equal(
    articles[1].sourceBatchId,
    "promopages-10060-article-02-20260806-v2",
  );
  assert.deepEqual([...unavailable], []);
  assert.deepEqual(
    { ...hooks.__datasetCounts(articles) },
    {
      articleCount: 18,
      imageCount: 137,
      videoCount: 411,
      availableVideoCount: 409,
      unavailableOutputCount: 2,
    },
  );
});

test("campaigns 20260807 sidecar completes 21 / 170 / 510", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_MANIFEST_PATH),
    [],
  );
  const extension = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_EXTENSION_MANIFEST_PATH),
    legacy.articles,
    { extension: true },
  );
  const article02 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH),
    [...legacy.articles, ...extension.articles],
    { article02: true },
  );
  const campaign20260807 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_CAMPAIGN_20260807_MANIFEST_PATH),
    [...legacy.articles, ...extension.articles, ...article02.articles],
    { campaign20260807: true },
  );
  const articles = hooks.__sortPromopages10060Articles([
    ...legacy.articles,
    ...extension.articles,
    ...article02.articles,
    ...campaign20260807.articles,
  ]);

  assert.deepEqual(
    [...articles].map((article) => article.article_number),
    Array.from({ length: 21 }, (_, index) => String(index + 1).padStart(2, "0")),
  );
  assert.deepEqual(
    { ...hooks.__datasetCounts(articles) },
    {
      articleCount: 21,
      imageCount: 170,
      videoCount: 510,
      availableVideoCount: 508,
      unavailableOutputCount: 2,
    },
  );
});

test("verified S3 delivery covers all 508 MP4 and renders a copyable public URL", () => {
  const hooks = loadHooks();
  const canonicalArticles = actualPromopages10060Articles(hooks);
  const deliveryManifest = loadJson(PROMOPAGES_10060_S3_DELIVERY_MANIFEST_PATH);
  const deliveredArticles = hooks.__validatePromopages10060S3Delivery(
    deliveryManifest,
    canonicalArticles,
  );
  const deliveredOutputs = deliveredArticles.flatMap((article) =>
    article.images.flatMap((record) => record.outputs),
  );
  const publicOutputs = deliveredOutputs.filter((output) => output.publicVideoUrl);
  const unavailableOutputs = deliveredOutputs.filter(
    (output) => !output.availableVideo,
  );

  assert.equal(publicOutputs.length, 508);
  assert.equal(unavailableOutputs.length, 2);
  assert.ok(
    publicOutputs.every(
      (output) =>
        output.delivery === "public-s3" &&
        output.publicVideoUrl.startsWith(
          "https://yastatic.net/s3/promopages-front-bundles/front-images/exp_video/",
        ),
    ),
  );
  assert.ok(unavailableOutputs.every((output) => !output.publicVideoUrl));

  const article = deliveredArticles.find(
    (item) => item.article_slug === "19-pixel24-ekshn-kamery",
  );
  const imageRecord = article.images.find((record) => record.image.image_id === "01");
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.2",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 0);
  const escapedUrl = output.publicVideoUrl.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert.match(markup, new RegExp(`src="${escapedUrl}"`));
  assert.match(markup, /data-video-delivery="s3-yastatic"/);
  assert.match(markup, new RegExp(`value="${escapedUrl}"`));
  assert.match(markup, new RegExp(`href="${escapedUrl}"`));
  assert.match(markup, /Публичная ссылка/);
  assert.match(markup, /data-copy-public-video-url/);
});

test("S3 delivery fails closed on missing, media-drifted, or foreign-host entries", () => {
  const hooks = loadHooks();
  const canonicalArticles = actualPromopages10060Articles(hooks);
  const deliveryManifest = loadJson(PROMOPAGES_10060_S3_DELIVERY_MANIFEST_PATH);
  const mutations = [
    [
      /ровно 508/,
      (manifest) => {
        manifest.outputs.pop();
        manifest.verified_output_count -= 1;
      },
    ],
    [
      /расходится с canonical media/,
      (manifest) => {
        manifest.outputs[0].sha256 = "0".repeat(64);
      },
    ],
    [
      /небезопасную публичную ссылку/,
      (manifest) => {
        manifest.outputs[0].yastatic_url = "https://example.test/video.mp4";
      },
    ],
    [
      /неверный маршрут статьи/,
      (manifest) => {
        manifest.articles[0].cabinet_id = "0".repeat(24);
      },
    ],
    [
      /небезопасную публичную ссылку/,
      (manifest) => {
        manifest.outputs[0].object_key = manifest.outputs[0].object_key.replace(
          "level-group__69ee06293ba10e0ae4b765d1/6a048ddca495b52c9d873940",
          `other-cabinet__${"0".repeat(24)}/${"1".repeat(24)}`,
        );
        manifest.outputs[0].yastatic_url =
          `https://yastatic.net/s3/promopages-front-bundles/${manifest.outputs[0].object_key}`;
      },
    ],
  ];

  mutations.forEach(([pattern, mutate]) => {
    const changed = clone(deliveryManifest);
    mutate(changed);
    assert.throws(
      () => hooks.__validatePromopages10060S3Delivery(changed, canonicalArticles),
      pattern,
    );
  });
});

test("article 02 sidecar rejects role, batch, article and frozen v1 namespace drift", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_MANIFEST_PATH),
    [],
  );
  const extension = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_EXTENSION_MANIFEST_PATH),
    legacy.articles,
    { extension: true },
  );
  const knownArticles = [...legacy.articles, ...extension.articles];
  const cases = [
    [
      /manifest_role/,
      (manifest) => {
        manifest.manifest_role = "promopages-10060-all-images";
      },
    ],
    [
      /batch_id/,
      (manifest) => {
        manifest.batch_id = "promopages-10060-article-02-20260806-v1";
      },
    ],
    [
      /exact article 02/,
      (manifest) => {
        manifest.articles[0].article_number = "03";
      },
    ],
    [
      /context_path/,
      (manifest) => {
        manifest.articles[0].context_path = manifest.articles[0].context_path.replace(
          "article-02-20260806-v1",
          "article-02-20260806-v2",
        );
      },
    ],
    [
      /frozen source namespace v1/,
      (manifest) => {
        manifest.articles[0].images[0].image.source_path =
          manifest.articles[0].images[0].image.source_path.replace(
            "article-02-20260806-v1",
            "article-02-20260806-v2",
          );
      },
    ],
  ];

  cases.forEach(([pattern, mutate]) => {
    const manifest = loadJson(PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH);
    mutate(manifest);
    assert.throws(
      () =>
        hooks.__validatePromopages10060Manifest(manifest, knownArticles, {
          article02: true,
        }),
      pattern,
    );
  });
});

test("article 02 replacement keeps every non-exact unavailable collision fail-closed", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_MANIFEST_PATH),
    [],
  );
  const article02 = hooks.__validatePromopages10060Manifest(
    loadJson(PROMOPAGES_10060_ARTICLE_02_MANIFEST_PATH),
    legacy.articles,
    { article02: true },
  );
  const available = [...legacy.articles, ...article02.articles];
  const duplicateAvailable03 = {
    article_number: "03",
    article_slug: legacy.articles.find((article) => article.article_number === "03")
      .article_slug,
    status: "source-unavailable",
  };

  assert.throws(
    () =>
      hooks.__mergeUnavailableArticleCollections(
        available,
        legacy.unavailableArticles,
        [duplicateAvailable03],
      ),
    /повторяется: 03/,
  );
  assert.throws(
    () =>
      hooks.__mergeUnavailableArticleCollections(
        available,
        legacy.unavailableArticles,
        legacy.unavailableArticles,
      ),
    /повторяется: 02/,
  );
});

test("campaign normalized supersede selects the terminal MP4 and renders both attempts", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  const extension = hooks.__validatePromopages10060Manifest(
    campaignNormalizedExtensionManifest(),
    legacy.articles,
    { extension: true },
  );

  assert.equal(extension.normalizedInputRetryOutputCount, 6);
  assert.equal(extension.normalizedInputSupersedeOutputCount, 1);
  const article = extension.articles[0];
  const imageRecord = article.images.find(
    (record) => record.image.image_id === "07",
  );
  const output = imageRecord.outputs.find(
    (item) => item.model_id === "alibaba/wan-2.7",
  );
  const markup = hooks.__renderModel(article, imageRecord, output, 1);

  assert.equal(output.availableVideo, true);
  assert.equal(output.normalizedInputRetry, true);
  assert.equal(
    output.selected_attempt,
    "normalized-input-superseding-attempt-v1",
  );
  assert.match(markup, /<video/);
  assert.match(markup, /superseding-attempt-v1\/videos\/wan-2\.7\/07\.mp4/);
  assert.match(markup, /Superseding attempt selected/);
  assert.match(markup, /Выбран результат новой terminal-попытки/);
  assert.match(markup, /Предыдущая попытка · может оставаться активной/);
  assert.match(markup, new RegExp(EXTENSION_SUPERSEDED_JOB_ID));
  assert.match(markup, /replacement-wan27-job/);
  assert.match(markup, /стороны меньше 240 px/);
  assert.match(markup, /тот же normalized input \/ prompt \/ model \/ route \/ seed \/ request/);
  assert.doesNotMatch(markup, /data-provider-unavailable/);
});

test("campaign normalized supersede fails closed on audit, policy, or cost tampering", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  const selectedOutput = (manifest) => {
    const record = manifest.articles[0].images.find(
      (item) => item.image.image_id === "07",
    );
    return record.outputs.find(
      (output) => output.model_id === "alibaba/wan-2.7",
    );
  };
  const cases = [
    [
      /superseded active job evidence/,
      (manifest) => {
        selectedOutput(manifest).retry.supersede.superseded_attempt.provider_job_id =
          "other-job";
      },
    ],
    [
      /superseded active job evidence/,
      (manifest) => {
        selectedOutput(
          manifest,
        ).retry.supersede.superseded_attempt.provider_may_be_active = false;
      },
    ],
    [
      /identity\/request/,
      (manifest) => {
        selectedOutput(
          manifest,
        ).retry.supersede.superseding_attempt.request_sha256 = "b".repeat(64);
      },
    ],
    [
      /разрешённый namespace/,
      (manifest) => {
        selectedOutput(manifest).retry.supersede.namespace =
          `${EXTENSION_RETRY_NAMESPACE}/other/superseding-attempt-v1`;
      },
    ],
    [
      /identity\/request/,
      (manifest) => {
        selectedOutput(manifest).selected_attempt = "normalized-input-retry-v1";
      },
    ],
    [
      /supersede policy/,
      (manifest) => {
        manifest.generation_policy.normalized_input_supersede.duplicate_billing_risk_acknowledged =
          false;
      },
    ],
    [
      /supersede cost/,
      (manifest) => {
        manifest.cost.normalized_input_supersede_reservations = 0;
      },
    ],
  ];

  cases.forEach(([pattern, mutate]) => {
    const manifest = campaignNormalizedExtensionManifest();
    mutate(manifest);
    assert.throws(
      () =>
        hooks.__validatePromopages10060Manifest(manifest, legacy.articles, {
          extension: true,
        }),
      pattern,
    );
  });
});

test("campaign extension rejects identity and media collisions with legacy", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);

  const duplicateNumber = campaignExtensionManifest();
  duplicateNumber.articles[0].article_number = "01";
  assert.throws(
    () =>
      hooks.__validatePromopages10060Manifest(
        duplicateNumber,
        legacy.articles,
        { extension: true },
      ),
    /номер.*повторяется/i,
  );

  const duplicateSource = campaignExtensionManifest();
  duplicateSource.articles[0].images[0].image.source_path =
    reviewManifest().articles[0].images[0].image.source_path;
  assert.throws(
    () =>
      hooks.__validatePromopages10060Manifest(
        duplicateSource,
        legacy.articles,
        { extension: true },
      ),
    /Путь исходника.*использован/,
  );

  const sourceCollidesWithVideo = campaignExtensionManifest();
  sourceCollidesWithVideo.articles[0].images[0].image.source_path =
    legacy.articles[0].images[0].outputs[0].video_path;
  assert.throws(
    () =>
      hooks.__validatePromopages10060Manifest(
        sourceCollidesWithVideo,
        legacy.articles,
        { extension: true },
      ),
    /Путь исходника.*использован/,
  );

  const videoCollidesWithSource = campaignExtensionManifest();
  videoCollidesWithSource.articles[0].images[0].outputs[0].video_path =
    legacy.articles[0].images[0].image.source_path;
  assert.throws(
    () =>
      hooks.__validatePromopages10060Manifest(
        videoCollidesWithSource,
        legacy.articles,
        { extension: true },
      ),
    /MP4.*media.*использован/,
  );
});

test("campaign extension requires exact registered article union 15–18", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);
  const extension = campaignExtensionManifest();
  extension.articles[0].article_number = "99";
  assert.throws(
    () =>
      hooks.__validatePromopages10060Manifest(
        extension,
        legacy.articles,
        { extension: true },
      ),
    /зарегистрированные статьи 15–18/,
  );
});

test("campaign extension rejects unsafe or foreign audit paths", () => {
  const hooks = loadHooks();
  const legacy = hooks.__validatePromopages10060Manifest(reviewManifest(), []);

  for (const contextPath of [
    "../../outside.json",
    "PROMOPAGES-10060/articles/15-campaign/content.json",
  ]) {
    const extension = campaignExtensionManifest();
    extension.articles[0].context_path = contextPath;
    assert.throws(
      () =>
        hooks.__validatePromopages10060Manifest(
          extension,
          legacy.articles,
          { extension: true },
        ),
      /context_path/,
    );
  }

  for (const manifestPath of [
    "/absolute/source.jpg",
    "PROMOPAGES-10060/articles/15-campaign/source.jpg",
  ]) {
    const extension = campaignExtensionManifest();
    extension.articles[0].images[0].image.manifest_file_path = manifestPath;
    assert.throws(
      () =>
        hooks.__validatePromopages10060Manifest(
          extension,
          legacy.articles,
          { extension: true },
        ),
      /manifest_file_path/,
    );
  }
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
