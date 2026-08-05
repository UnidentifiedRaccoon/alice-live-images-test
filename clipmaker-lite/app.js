(() => {
  "use strict";

  const BASE_MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";
  const ADDITIONAL_MANIFEST_PATH =
    "../clipmaker-lite-test/promopages-9930-manifest.json";
  const CASE_21_MANIFEST_PATH = "../clipmaker-lite-test/case-21-manifest.json";
  const PROMOPAGES_10060_MANIFEST_PATH =
    "../clipmaker-lite-test/promopages-10060-manifest.json";
  const EXPECTED_BASE_ARTICLE_COUNT = 20;
  const EXPECTED_BASE_OUTPUT_COUNT = 60;
  const EXPECTED_ADDITIONAL_ARTICLE_COUNT = 20;
  const EXPECTED_ADDITIONAL_IMAGE_COUNT = 20;
  const EXPECTED_ADDITIONAL_OUTPUT_COUNT = 60;
  const EXPECTED_CASE_21_ARTICLE_COUNT = 1;
  const EXPECTED_CASE_21_IMAGE_COUNT = 1;
  const EXPECTED_CASE_21_OUTPUT_COUNT = 3;
  const EXPECTED_CASE_21_RESEARCH_OUTPUT_COUNT = 4;
  const EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT = 7;
  const EXPECTED_CASE_21_ATTEMPT_COUNT = 11;
  const EXPECTED_PROMOPAGES_10060_ARTICLE_NUMBERS = [
    "01",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
  ];
  const EXPECTED_PROMOPAGES_10060_ARTICLE_COUNT = 13;
  const EXPECTED_PROMOPAGES_10060_IMAGE_COUNT = 92;
  const EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT = 276;
  const EXPECTED_PROMOPAGES_10060_UNAVAILABLE_ARTICLE_NUMBER = "02";
  const PROVIDER_FILTERED_STATUS = "provider-filtered";
  const PROVIDER_FILTERED_RECORDED_STATUS = "provider-failed";
  const PROVIDER_FILTERED_SELECTION = "terminal-retry-v1-exhausted";
  const PROVIDER_UNAVAILABLE_STATUS = "provider-unavailable";
  const AMBIGUOUS_SUBMIT_RETRY_KIND = "ambiguous-submit";
  const AMBIGUOUS_SUBMIT_RETRY_SELECTION = "ambiguous-submit-retry-v1";
  const AMBIGUOUS_SUBMIT_RETRY_EXHAUSTED_SELECTION =
    "ambiguous-submit-retry-v1-exhausted";
  const NORMALIZED_INPUT_RETRY_KIND = "normalized-input";
  const NORMALIZED_INPUT_RETRY_SELECTION = "normalized-input-retry-v1";
  const NORMALIZED_INPUT_RETRY_EXHAUSTED_SELECTION =
    "normalized-input-retry-v1-exhausted";
  const MAX_PROVIDER_SOURCE_BYTES = 20 * 1024 * 1024;
  const LOOP_MODEL_ID = "alibaba/wan-2.7";
  const LOOP_REQUEST_CLASSIFICATION = "api-loop-closure-experiment";
  const LOOP_REQUEST_MECHANISM = "same-source-first-and-last-frame";
  const LOOP_FRAME_TYPES = ["first_frame", "last_frame"];
  const LOOP_SEAM_PRESENTATION = {
    "seam-passed": "Шов · проверен",
    "seam-failed": "Шов · не прошёл проверку",
    "seam-not-reviewed": "Шов · не проверен",
  };
  const EXPECTED_CASE_21_SMOOTH_OUTPUT_COUNT = 4;
  const SMOOTH_REQUEST_CLASSIFICATION = "non-loop-smooth-motion-experiment";
  const SMOOTH_REQUEST_MECHANISM = "single-source-first-frame";
  const SMOOTH_FRAME_TYPES = ["first_frame"];
  const SMOOTH_RETRY_ACTIVITY = "smooth-motion-explicit-retry";
  const SMOOTH_RETRY_VARIANT_ID = "staggered-ease-retry1";
  const SMOOTH_REPLACED_VARIANT_ID = "staggered-ease";
  const SMOOTH_RETRY_OF_PROVIDER_RUN_ID =
    "promopages-9930-case21-wan27-smooth-provider-20260728-v1-21-maier-04-smooth-staggered-ease-wan-2-7";
  const SMOOTH_FEATURED_REVIEW_SCHEMA =
    "clipmaker-lite.case21-smooth-featured-review.v1";
  const SMOOTH_FEATURED_PRACTICE_IDS = [
    "long-overlapping-eases",
    "bounded-one-shot-motion",
    "structural-locks",
    "failure-specific-negative",
    "held-end-states",
  ];
  const EXPECTED_EXPERIMENT_OUTPUT_COUNT = 2;
  const EXPECTED_EXTERNAL_OUTPUT_COUNT = 1;
  const MODEL_ORDER = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
  ];
  const EXPERIMENT_ARTICLE_NUMBER = "14";
  const EXTERNAL_MODEL_ID = "segmind/wan-2.2-i2v-flash";
  const EXPERIMENT_PROMPT_SOURCE_MODEL_ID = MODEL_ORDER[0];
  const EXPERIMENT_TARGET_MODEL_ORDER = MODEL_ORDER.slice(1);
  const ADDITIONAL_MODEL_ORDER = MODEL_ORDER;
  const RAW_REPOSITORY_BASE =
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/main/";
  const MODEL_PRESENTATION = {
    "alibaba/wan-2.2": {
      name: "Wan 2.2",
      cost: "8–10 ₽",
    },
    "alibaba/wan-2.7": {
      name: "Wan 2.7",
      cost: "$0.50",
    },
    "google/veo-3.1-lite": {
      name: "Veo 3.1 Lite",
      cost: "$0.20",
    },
    [EXTERNAL_MODEL_ID]: {
      name: "Wan 2.2 Flash",
      cost: "$0.18",
    },
  };
  const CASE_21_VARIANT_LABELS = {
    "baseline-generation:": "Baseline",
    "explicit-retry:": "Baseline retry",
    "prompt-experiment:monotonic-positive": "Monotonic positive",
    "prompt-experiment:erosion-negative": "Erosion + negative repair",
    "prompt-experiment:veo-motion-only": "Motion-only",
    "prompt-experiment:opacity-only": "Opacity-only + negative repair",
  };

  const elements = {
    currentNumber: document.querySelector("#currentNumber"),
    totalNumber: document.querySelector("#totalNumber"),
    caseTitle: document.querySelector("#caseTitle"),
    previousCase: document.querySelector("#previousCase"),
    nextCase: document.querySelector("#nextCase"),
    caseSelect: document.querySelector("#caseSelect"),
    currentImageNumber: document.querySelector("#currentImageNumber"),
    totalImageNumber: document.querySelector("#totalImageNumber"),
    previousImage: document.querySelector("#previousImage"),
    nextImage: document.querySelector("#nextImage"),
    imageSelect: document.querySelector("#imageSelect"),
    navigatorStatus: document.querySelector("#navigatorStatus"),
    datasetError: document.querySelector("#datasetError"),
    datasetErrorText: document.querySelector("#datasetErrorText"),
    caseViewport: document.querySelector("#caseViewport"),
    articleCountSummary: document.querySelector("#articleCountSummary"),
    imageCountSummary: document.querySelector("#imageCountSummary"),
    videoCountSummary: document.querySelector("#videoCountSummary"),
    datasetSourceStatus: document.querySelector("#datasetSourceStatus"),
    caseDatasetMeta: document.querySelector("#caseDatasetMeta"),
  };

  const missingElement = Object.values(elements).some((element) => !element);
  if (missingElement) return;

  const numberFormatter = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  });
  const prefersReducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const escapeHtml = (value = "") =>
    String(value).replace(/[&<>"']/g, (character) => {
      const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      };
      return entities[character];
    });

  const encodeRepositoryPath = (repositoryPath) =>
    String(repositoryPath)
      .replace(/^\/+/, "")
      .split("/")
      .map((part) => encodeURIComponent(part))
      .join("/");

  const asAssetUrl = (repositoryPath, delivery = "site") => {
    const normalizedPath = String(repositoryPath).replace(/^\/+/, "");
    const isPublishedPages = window.location.hostname.endsWith("github.io");
    if (delivery === "repository-raw" && isPublishedPages) {
      return `${RAW_REPOSITORY_BASE}${encodeRepositoryPath(normalizedPath)}`;
    }
    return `../${normalizedPath}`;
  };

  const formatDuration = (seconds) => `${numberFormatter.format(seconds)}\u00a0с`;
  const formatMiB = (bytes) => `${numberFormatter.format(bytes / 1024 / 1024)}\u00a0МиБ`;

  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };

  const hasOwn = (object, property) =>
    Object.prototype.hasOwnProperty.call(object, property);

  const makeCaseKey = (ticket, articleSlug) => {
    assert(
      typeof ticket === "string" && /^PROMOPAGES-\d+$/.test(ticket),
      `Некорректный ticket для case key: ${ticket ?? "—"}.`,
    );
    assert(
      typeof articleSlug === "string" && articleSlug.trim(),
      `Некорректный slug для case key: ${articleSlug ?? "—"}.`,
    );
    return `${ticket}:${articleSlug}`;
  };

  const asDomIdPart = (value) => String(value).replace(/[^a-zA-Z0-9_-]/g, "-");

  const articleIdentityLabel = (article) =>
    `${article.sourceTicket || "источник не указан"} · ${article.article_number}`;

  const validateOutput = (articleNumber, output, videoPaths, contextLabel) => {
    assert(output && typeof output === "object", `У ${articleNumber} / ${contextLabel} нет данных.`);
    assert(output.video_path, `У ${articleNumber} / ${contextLabel} нет MP4.`);
    assert(
      !videoPaths.has(output.video_path),
      `Путь MP4 повторяется: ${output.video_path}.`,
    );
    assert(
      typeof output.positive_prompt === "string" && output.positive_prompt.trim(),
      `У ${articleNumber} / ${contextLabel} пустой positive prompt.`,
    );
    assert(
      Number(output.media?.width) > 0 && Number(output.media?.height) > 0,
      `У ${articleNumber} / ${contextLabel} нет геометрии видео.`,
    );
    assert(
      Number(output.media?.duration_seconds) > 0 && Number(output.media?.bytes) > 0,
      `У ${articleNumber} / ${contextLabel} нет метаданных видео.`,
    );
    videoPaths.add(output.video_path);
  };

  const validateProviderFilteredAttempt = (
    attempt,
    contextLabel,
    { requireInactive = false } = {},
  ) => {
    assert(
      attempt && typeof attempt === "object",
      `${contextLabel}: нет аудита provider-попытки.`,
    );
    ["provider_run_id", "provider_job_id", "submitted_at", "completed_at", "error"].forEach(
      (field) => {
        assert(
          typeof attempt[field] === "string" && attempt[field].trim(),
          `${contextLabel}: в аудите попытки нет ${field}.`,
        );
      },
    );
    assert(
      attempt.status === PROVIDER_FILTERED_RECORDED_STATUS,
      `${contextLabel}: попытка должна иметь terminal provider-failed status.`,
    );
    assert(
      /filter/i.test(attempt.error),
      `${contextLabel}: terminal error не подтверждает content filtering.`,
    );
    ["run_path", "prompt_path"].forEach((field) => {
      assert(
        typeof attempt[field] === "string" && attempt[field].trim(),
        `${contextLabel}: в аудите попытки нет ${field}.`,
      );
    });
    ["run_sha256", "prompt_sha256", "request_sha256"].forEach((field) => {
      assert(
        typeof attempt[field] === "string" && /^[a-f0-9]{64}$/.test(attempt[field]),
        `${contextLabel}: в аудите попытки нет валидного ${field}.`,
      );
    });
    if (requireInactive) {
      assert(
        attempt.provider_may_be_active === false,
        `${contextLabel}: retry-попытка не подтверждена как terminal.`,
      );
    }
    return attempt;
  };

  const validateProviderFilteredOutput = (articleNumber, output, contextLabel) => {
    const label = `${articleNumber} / ${contextLabel}`;
    assert(
      output.status === PROVIDER_FILTERED_STATUS &&
        output.recorded_status === PROVIDER_FILTERED_RECORDED_STATUS &&
        output.selected_attempt === PROVIDER_FILTERED_SELECTION,
      `${label}: неверная terminal provider-filtered identity.`,
    );
    assert(
      output.video_path === null && output.media === null && output.contract_check === null,
      `${label}: provider-filtered output не должен содержать MP4 или media contract.`,
    );
    assert(
      typeof output.positive_prompt === "string" && output.positive_prompt.trim(),
      `${label}: пустой positive prompt.`,
    );
    assert(
      typeof output.error === "string" && output.error.trim() && /filter/i.test(output.error),
      `${label}: нет terminal content-filter error.`,
    );
    const retry = output.retry;
    assert(
      retry &&
        typeof retry === "object" &&
        retry.retry_number === 1 &&
        retry.exhausted === true &&
        typeof retry.namespace === "string" &&
        retry.namespace.trim() &&
        typeof retry.envelope_path === "string" &&
        retry.envelope_path === `${retry.namespace}/retry.json`,
      `${label}: нет immutable retry-v1 envelope audit.`,
    );
    const primaryAttempt = validateProviderFilteredAttempt(
      retry.primary_attempt,
      `${label} / primary`,
    );
    const retryAttempt = validateProviderFilteredAttempt(
      retry.retry_attempt,
      `${label} / retry-v1`,
      { requireInactive: true },
    );
    assert(
      output.provider_run_id === retryAttempt.provider_run_id &&
        output.error === retryAttempt.error,
      `${label}: selected retry identity или error не совпадает с output.`,
    );
    assert(
      primaryAttempt.provider_run_id !== retryAttempt.provider_run_id &&
        primaryAttempt.provider_job_id !== retryAttempt.provider_job_id,
      `${label}: primary и retry должны иметь разные provider identities.`,
    );
    assert(
      primaryAttempt.request_sha256 === retryAttempt.request_sha256,
      `${label}: retry изменил immutable provider request.`,
    );
    return {
      ...output,
      availableVideo: false,
      providerFiltered: true,
      providerUnavailable: false,
    };
  };

  const validateAmbiguousSubmitRetry = (
    output,
    contextLabel,
    { exhausted },
  ) => {
    const retry = output.retry;
    assert(
      retry &&
        typeof retry === "object" &&
        retry.retry_kind === AMBIGUOUS_SUBMIT_RETRY_KIND &&
        retry.retry_number === 1 &&
        retry.exhausted === exhausted &&
        retry.primary_outcome_unknown === true &&
        typeof retry.namespace === "string" &&
        retry.namespace.trim() &&
        retry.envelope_path === `${retry.namespace}/retry.json` &&
        typeof retry.envelope_sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(retry.envelope_sha256),
      `${contextLabel}: нет immutable ambiguous-submit retry-v1 audit.`,
    );

    const primary = retry.primary_attempt;
    assert(
      primary &&
        typeof primary === "object" &&
        primary.status === "submit-unknown" &&
        ["submitting", "submit-unknown"].includes(primary.recorded_status) &&
        primary.outcome === "unknown" &&
        primary.outcome_unknown === true &&
        primary.provider_may_be_active === true &&
        primary.provider_job_id === null &&
        primary.submitted_at === null &&
        primary.completed_at === null &&
        typeof primary.ambiguity_reason === "string" &&
        primary.ambiguity_reason.trim() &&
        (primary.error === null ||
          (typeof primary.error === "string" && primary.error.trim())),
      `${contextLabel}: primary outcome должен оставаться строго unknown.`,
    );

    const retryAttempt = retry.retry_attempt;
    assert(
      retryAttempt &&
        typeof retryAttempt === "object" &&
        typeof retryAttempt.provider_job_id === "string" &&
        retryAttempt.provider_job_id.trim() &&
        retryAttempt.status === output.recorded_status &&
        retryAttempt.provider_may_be_active === false &&
        typeof retryAttempt.submitted_at === "string" &&
        retryAttempt.submitted_at.trim() &&
        typeof retryAttempt.completed_at === "string" &&
        retryAttempt.completed_at.trim() &&
        retryAttempt.error === output.error,
      `${contextLabel}: retry-v1 не подтверждён как terminal selected attempt.`,
    );

    [primary, retryAttempt].forEach((attempt, index) => {
      const attemptLabel = index === 0 ? "primary" : "retry-v1";
      ["provider_run_id", "run_path", "prompt_path"].forEach((field) => {
        assert(
          typeof attempt[field] === "string" && attempt[field].trim(),
          `${contextLabel} / ${attemptLabel}: в аудите нет ${field}.`,
        );
      });
      ["run_sha256", "prompt_sha256", "request_sha256"].forEach((field) => {
        assert(
          typeof attempt[field] === "string" && /^[a-f0-9]{64}$/.test(attempt[field]),
          `${contextLabel} / ${attemptLabel}: в аудите нет валидного ${field}.`,
        );
      });
    });
    assert(
      output.provider_run_id === retryAttempt.provider_run_id &&
        primary.provider_run_id !== retryAttempt.provider_run_id &&
        primary.request_sha256 === retryAttempt.request_sha256,
      `${contextLabel}: ambiguous primary/retry identity или immutable request не совпадает.`,
    );
    if (exhausted) {
      assert(
        output.status === PROVIDER_UNAVAILABLE_STATUS &&
          output.recorded_status === "provider-failed" &&
          output.selected_attempt === AMBIGUOUS_SUBMIT_RETRY_EXHAUSTED_SELECTION &&
          typeof output.error === "string" &&
          output.error.trim(),
        `${contextLabel}: неверная exhausted ambiguous-submit identity.`,
      );
    } else {
      assert(
        ["succeeded", "verification-failed"].includes(output.status) &&
          output.selected_attempt === AMBIGUOUS_SUBMIT_RETRY_SELECTION,
        `${contextLabel}: неверная selected ambiguous-submit retry identity.`,
      );
    }
    return retry;
  };

  const validateProviderUnavailableOutput = (articleNumber, output, contextLabel) => {
    const label = `${articleNumber} / ${contextLabel}`;
    assert(
      output.video_path === null && output.media === null && output.contract_check === null,
      `${label}: provider-unavailable output не должен содержать MP4 или media contract.`,
    );
    assert(
      typeof output.positive_prompt === "string" && output.positive_prompt.trim(),
      `${label}: пустой positive prompt.`,
    );
    validateAmbiguousSubmitRetry(output, label, { exhausted: true });
    return {
      ...output,
      availableVideo: false,
      providerFiltered: false,
      providerUnavailable: true,
    };
  };

  const validateNormalizedInputRetry = (
    output,
    image,
    contextLabel,
    { exhausted },
  ) => {
    const retry = output.retry;
    assert(
      retry &&
        typeof retry === "object" &&
        retry.retry_kind === NORMALIZED_INPUT_RETRY_KIND &&
        retry.retry_number === 1 &&
        retry.exhausted === exhausted &&
        typeof retry.namespace === "string" &&
        retry.namespace.trim() &&
        retry.envelope_path === `${retry.namespace}/retry.json` &&
        typeof retry.envelope_sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(retry.envelope_sha256),
      `${contextLabel}: нет immutable normalized-input retry-v1 audit.`,
    );
    assert(
      output.article_slug === "12-dream-island-7-fishek" &&
        output.image_id === "08" &&
        ["alibaba/wan-2.2", "alibaba/wan-2.7"].includes(output.model_id),
      `${contextLabel}: normalized-input retry разрешён только для 12/08 Wan 2.2 или Wan 2.7.`,
    );

    const transform = retry.source_transform;
    const original = transform?.original;
    const normalized = transform?.normalized;
    const delta = transform?.request_delta;
    const expectedPointer =
      output.model_id === "alibaba/wan-2.2"
        ? "/input/image"
        : "/frame_images/0/image_url/url";
    assert(
      transform &&
        typeof transform === "object" &&
        transform.strategy === "frozen-page-variant" &&
        original &&
        typeof original === "object" &&
        normalized &&
        typeof normalized === "object" &&
        delta &&
        typeof delta === "object",
      `${contextLabel}: source_transform audit отсутствует.`,
    );
    assert(
      typeof original.url === "string" &&
        /^https:\/\//.test(original.url) &&
        original.path === output.source_path &&
        original.path === image.source_path &&
        typeof original.sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(original.sha256) &&
        original.sha256 === image.sha256 &&
        Number.isInteger(original.bytes) &&
        original.bytes > MAX_PROVIDER_SOURCE_BYTES &&
        Number.isInteger(original.width) &&
        original.width > 0 &&
        original.width === image.width &&
        Number.isInteger(original.height) &&
        original.height > 0 &&
        original.height === image.height &&
        (!image.orig_url || image.orig_url === original.url),
      `${contextLabel}: original source audit не совпадает с logical source.`,
    );
    assert(
      typeof normalized.url === "string" &&
        /^https:\/\/avatars\.mds\.yandex\.net\/.+\/scale_1200$/.test(
          normalized.url,
        ) &&
        normalized.url !== original.url &&
        typeof normalized.sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(normalized.sha256) &&
        normalized.sha256 !== original.sha256 &&
        Number.isInteger(normalized.bytes) &&
        normalized.bytes > 0 &&
        normalized.bytes <= MAX_PROVIDER_SOURCE_BYTES &&
        normalized.bytes < original.bytes &&
        Number.isInteger(normalized.width) &&
        normalized.width > 0 &&
        normalized.width <= original.width &&
        Number.isInteger(normalized.height) &&
        normalized.height > 0 &&
        normalized.height <= original.height &&
        (normalized.width < original.width || normalized.height < original.height) &&
        typeof normalized.metadata_path === "string" &&
        normalized.metadata_path.trim() &&
        typeof normalized.metadata_sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(normalized.metadata_sha256),
      `${contextLabel}: normalized source audit некорректен или превышает 20 MiB.`,
    );
    assert(
      delta.json_pointer === expectedPointer &&
        delta.from === original.url &&
        delta.to === normalized.url &&
        delta.changed_leaf_count === 1 &&
        JSON.stringify(Object.keys(delta).sort()) ===
          JSON.stringify(["changed_leaf_count", "from", "json_pointer", "to"]),
      `${contextLabel}: request delta должен менять только model-specific image URL.`,
    );

    const primary = retry.primary_attempt;
    const retryAttempt = retry.retry_attempt;
    assert(
      primary &&
        typeof primary === "object" &&
        primary.status === "provider-failed" &&
        primary.provider_may_be_active === false &&
        typeof primary.provider_job_id === "string" &&
        primary.provider_job_id.trim() &&
        typeof primary.error === "string" &&
        primary.error.trim(),
      `${contextLabel}: normalized-input primary failure audit некорректен.`,
    );
    if (output.model_id === "alibaba/wan-2.2") {
      assert(
        primary.recorded_status === "submit-unknown" &&
          primary.recorded_provider_may_be_active === true &&
          primary.submitted_at === null &&
          primary.completed_at === null &&
          ["provider_submit_time", "provider_scheduled_time", "provider_end_time"].every(
            (field) => typeof primary[field] === "string" && primary[field].trim(),
          ),
        `${contextLabel}: Wan 2.2 nested provider terminal evidence отсутствует.`,
      );
    } else {
      assert(
        primary.recorded_status === "provider-failed" &&
          primary.recorded_provider_may_be_active === false &&
          typeof primary.submitted_at === "string" &&
          primary.submitted_at.trim() &&
          typeof primary.completed_at === "string" &&
          primary.completed_at.trim(),
        `${contextLabel}: Wan 2.7 primary terminal evidence отсутствует.`,
      );
    }
    assert(
      retryAttempt &&
        typeof retryAttempt === "object" &&
        retryAttempt.status === output.recorded_status &&
        retryAttempt.provider_may_be_active === false &&
        typeof retryAttempt.provider_job_id === "string" &&
        retryAttempt.provider_job_id.trim() &&
        typeof retryAttempt.submitted_at === "string" &&
        retryAttempt.submitted_at.trim() &&
        typeof retryAttempt.completed_at === "string" &&
        retryAttempt.completed_at.trim() &&
        retryAttempt.error === output.error,
      `${contextLabel}: normalized-input retry-v1 не подтверждён как selected terminal attempt.`,
    );
    [primary, retryAttempt].forEach((attempt, index) => {
      const attemptLabel = index === 0 ? "primary" : "retry-v1";
      ["provider_run_id", "run_path", "prompt_path"].forEach((field) => {
        assert(
          typeof attempt[field] === "string" && attempt[field].trim(),
          `${contextLabel} / ${attemptLabel}: в аудите нет ${field}.`,
        );
      });
      ["run_sha256", "prompt_sha256", "request_sha256"].forEach((field) => {
        assert(
          typeof attempt[field] === "string" && /^[a-f0-9]{64}$/.test(attempt[field]),
          `${contextLabel} / ${attemptLabel}: в аудите нет валидного ${field}.`,
        );
      });
    });
    assert(
      output.provider_run_id === retryAttempt.provider_run_id &&
        primary.provider_run_id !== retryAttempt.provider_run_id &&
        primary.request_sha256 !== retryAttempt.request_sha256,
      `${contextLabel}: normalized retry identity/request binding некорректен.`,
    );
    const expectedSelection = exhausted
      ? NORMALIZED_INPUT_RETRY_EXHAUSTED_SELECTION
      : NORMALIZED_INPUT_RETRY_SELECTION;
    assert(
      output.selected_attempt === expectedSelection &&
        (exhausted
          ? output.status === PROVIDER_UNAVAILABLE_STATUS &&
            output.recorded_status === "provider-failed" &&
            typeof output.error === "string" &&
            output.error.trim()
          : ["succeeded", "verification-failed"].includes(output.status)),
      `${contextLabel}: normalized-input selected attempt identity некорректна.`,
    );
    return retry;
  };

  const validateNormalizedInputProviderUnavailable = (
    articleNumber,
    output,
    image,
    contextLabel,
  ) => {
    const label = `${articleNumber} / ${contextLabel}`;
    assert(
      output.video_path === null && output.media === null && output.contract_check === null,
      `${label}: provider-unavailable normalized retry не должен содержать MP4.`,
    );
    assert(
      typeof output.positive_prompt === "string" && output.positive_prompt.trim(),
      `${label}: пустой positive prompt.`,
    );
    validateNormalizedInputRetry(output, image, label, { exhausted: true });
    return {
      ...output,
      availableVideo: false,
      providerFiltered: false,
      providerUnavailable: true,
      normalizedInputRetry: true,
    };
  };

  const validateBaseManifest = (manifest) => {
    assert(manifest && typeof manifest === "object", "Манифест имеет неверный формат.");
    assert(
      manifest.article_count === EXPECTED_BASE_ARTICLE_COUNT,
      `В манифесте заявлено статей: ${manifest.article_count ?? "—"}, ожидалось 20.`,
    );
    assert(Array.isArray(manifest.articles), "В манифесте нет списка articles.");
    assert(
      manifest.articles.length === EXPECTED_BASE_ARTICLE_COUNT,
      `Найдено статей: ${manifest.articles.length}, ожидалось 20.`,
    );
    assert(Array.isArray(manifest.outputs), "В манифесте нет общего списка outputs.");
    assert(
      manifest.outputs.length === EXPECTED_BASE_OUTPUT_COUNT,
      `Найдено роликов: ${manifest.outputs.length}, ожидалось 60.`,
    );

    const expectedNumbers = Array.from({ length: EXPECTED_BASE_ARTICLE_COUNT }, (_, index) =>
      String(index + 1).padStart(2, "0"),
    );
    const canonicalVideoPaths = new Set();
    const allVideoPaths = new Set();
    let promptCount = 0;
    let comparisonOutputCount = 0;
    let externalOutputCount = 0;

    manifest.articles.forEach((article, articleIndex) => {
      assert(
        article.article_number === expectedNumbers[articleIndex],
        `Нарушен порядок кейсов около позиции ${expectedNumbers[articleIndex]}.`,
      );
      assert(article.title, `У кейса ${article.article_number} нет заголовка.`);
      assert(
        article.selected_image?.source_path,
        `У кейса ${article.article_number} нет исходного изображения.`,
      );
      assert(
        article.selected_image.image_id === "01",
        `У кейса ${article.article_number} базовым должно быть изображение 01.`,
      );
      assert(
        Number(article.selected_image.width) > 0 && Number(article.selected_image.height) > 0,
        `У исходника кейса ${article.article_number} нет геометрии.`,
      );
      assert(
        Array.isArray(article.outputs) && article.outputs.length === MODEL_ORDER.length,
        `У кейса ${article.article_number} должно быть три ролика.`,
      );

      const outputsByModel = new Map(article.outputs.map((output) => [output.model_id, output]));
      assert(
        outputsByModel.size === MODEL_ORDER.length,
        `У кейса ${article.article_number} повторяются модели.`,
      );

      MODEL_ORDER.forEach((modelId) => {
        const output = outputsByModel.get(modelId);
        assert(output, `У кейса ${article.article_number} нет модели ${modelId}.`);
        validateOutput(article.article_number, output, allVideoPaths, modelId);
        canonicalVideoPaths.add(output.video_path);
        promptCount += 1;
      });

      const hasComparisonOutputs = hasOwn(article, "comparison_outputs");
      const hasExternalOutputs = hasOwn(article, "external_outputs");
      if (!hasComparisonOutputs) {
        assert(
          !hasExternalOutputs,
          `Внешний route без comparison experiment найден у кейса ${article.article_number}.`,
        );
        return;
      }

      assert(
        article.article_number === EXPERIMENT_ARTICLE_NUMBER,
        `Экспериментальные ролики допустимы только у кейса ${EXPERIMENT_ARTICLE_NUMBER}.`,
      );
      assert(
        Array.isArray(article.comparison_outputs) &&
          article.comparison_outputs.length === EXPERIMENT_TARGET_MODEL_ORDER.length,
        `У кейса ${EXPERIMENT_ARTICLE_NUMBER} должно быть два экспериментальных ролика.`,
      );
      comparisonOutputCount += article.comparison_outputs.length;

      const comparisonsByModel = new Map(
        article.comparison_outputs.map((output) => [output.model_id, output]),
      );
      assert(
        comparisonsByModel.size === EXPERIMENT_TARGET_MODEL_ORDER.length,
        `У кейса ${EXPERIMENT_ARTICLE_NUMBER} повторяются экспериментальные модели.`,
      );
      const referencePrompt = outputsByModel.get(EXPERIMENT_PROMPT_SOURCE_MODEL_ID).positive_prompt;

      EXPERIMENT_TARGET_MODEL_ORDER.forEach((modelId) => {
        const output = comparisonsByModel.get(modelId);
        assert(
          output,
          `У эксперимента кейса ${EXPERIMENT_ARTICLE_NUMBER} нет модели ${modelId}.`,
        );
        assert(
          output.prompt_source_model_id === EXPERIMENT_PROMPT_SOURCE_MODEL_ID,
          `У ${EXPERIMENT_ARTICLE_NUMBER} / ${modelId} неверный источник prompt.`,
        );
        assert(
          output.positive_prompt === referencePrompt,
          `У ${EXPERIMENT_ARTICLE_NUMBER} / ${modelId} изменён prompt Wan 2.2.`,
        );
        validateOutput(
          article.article_number,
          output,
          allVideoPaths,
          `${modelId} · prompt Wan 2.2`,
        );
      });

      assert(
        Array.isArray(article.external_outputs) &&
          article.external_outputs.length === EXPECTED_EXTERNAL_OUTPUT_COUNT,
        `У кейса ${EXPERIMENT_ARTICLE_NUMBER} должен быть один внешний Eliza → Segmind ролик.`,
      );
      const externalOutput = article.external_outputs[0];
      assert(
        externalOutput.model_id === EXTERNAL_MODEL_ID,
        `У внешнего ролика кейса ${EXPERIMENT_ARTICLE_NUMBER} неверный model ID.`,
      );
      assert(
        externalOutput.gateway === "eliza" && externalOutput.provider === "segmind",
        `У внешнего ролика кейса ${EXPERIMENT_ARTICLE_NUMBER} неверный route.`,
      );
      assert(
        externalOutput.route_label === "Eliza → Segmind",
        `У внешнего ролика кейса ${EXPERIMENT_ARTICLE_NUMBER} нет явной подписи route.`,
      );
      assert(
        externalOutput.delivery === "repository-raw",
        `Внешний ролик кейса ${EXPERIMENT_ARTICLE_NUMBER} должен доставляться из main.`,
      );
      assert(
        externalOutput.actual_cost_usd === 0.18,
        `У внешнего ролика кейса ${EXPERIMENT_ARTICLE_NUMBER} неверная стоимость.`,
      );
      assert(
        externalOutput.visual_review?.status === "fidelity-failed" &&
          externalOutput.visual_review.summary,
        `У внешнего ролика кейса ${EXPERIMENT_ARTICLE_NUMBER} нет fidelity-review.`,
      );
      validateOutput(
        article.article_number,
        externalOutput,
        allVideoPaths,
        "Wan 2.2 Flash · Eliza → Segmind",
      );
      externalOutputCount += 1;
    });

    assert(
      canonicalVideoPaths.size === EXPECTED_BASE_OUTPUT_COUNT,
      "Пути выбранных canonical MP4 повторяются.",
    );
    assert(
      promptCount === EXPECTED_BASE_OUTPUT_COUNT,
      "Проверены не все 60 базовых positive prompts.",
    );
    assert(
      manifest.comparison_output_count === EXPECTED_EXPERIMENT_OUTPUT_COUNT,
      `В манифесте должно быть заявлено два экспериментальных ролика.`,
    );
    assert(
      comparisonOutputCount === EXPECTED_EXPERIMENT_OUTPUT_COUNT,
      `Проверено экспериментальных роликов: ${comparisonOutputCount}, ожидалось 2.`,
    );
    assert(
      manifest.external_output_count === EXPECTED_EXTERNAL_OUTPUT_COUNT,
      `В манифесте должен быть заявлен один внешний Eliza → Segmind ролик.`,
    );
    assert(
      externalOutputCount === EXPECTED_EXTERNAL_OUTPUT_COUNT,
      `Проверено внешних роликов: ${externalOutputCount}, ожидался 1.`,
    );

    return manifest.articles.map((article) => {
      const outputsByModel = new Map(article.outputs.map((output) => [output.model_id, output]));
      const normalizedOutputs = MODEL_ORDER.map((modelId) => outputsByModel.get(modelId));
      const identity = {
        case_key: makeCaseKey(manifest.ticket, article.article_slug),
        legacy_case_key: article.article_number,
        sourceTicket: manifest.ticket,
        sourceStatus: "Историческая выборка",
      };
      if (!hasOwn(article, "comparison_outputs")) {
        return {
          ...article,
          ...identity,
          outputs: normalizedOutputs,
          displayOutputs: normalizedOutputs,
        };
      }

      const comparisonsByModel = new Map(
        article.comparison_outputs.map((output) => [output.model_id, output]),
      );
      const displayOutputs = [
        {
          ...outputsByModel.get(EXPERIMENT_PROMPT_SOURCE_MODEL_ID),
          showcaseLabel: "Референс · свой prompt",
          showcaseVariant: "reference",
        },
        {
          ...article.external_outputs[0],
          showcaseLabel: "Eliza → Segmind",
          showcaseVariant: "external",
        },
      ];
      EXPERIMENT_TARGET_MODEL_ORDER.forEach((modelId) => {
        displayOutputs.push({
          ...outputsByModel.get(modelId),
          showcaseLabel: "Свой prompt",
          showcaseVariant: "baseline",
        });
        displayOutputs.push({
          ...comparisonsByModel.get(modelId),
          showcaseLabel: "Prompt Wan 2.2",
          showcaseVariant: "comparison",
        });
      });

      return {
        ...article,
        ...identity,
        outputs: normalizedOutputs,
        comparison_outputs: EXPERIMENT_TARGET_MODEL_ORDER.map((modelId) =>
          comparisonsByModel.get(modelId),
        ),
        external_outputs: article.external_outputs,
        displayOutputs,
      };
    });
  };

  const validateAdditionalManifest = (manifest, baseArticles) => {
    assert(manifest && typeof manifest === "object", "Дополнительный манифест имеет неверный формат.");
    assert(
      manifest.article_count === EXPECTED_ADDITIONAL_ARTICLE_COUNT,
      `В дополнительном манифесте заявлено статей: ${manifest.article_count ?? "—"}, ожидалось 20.`,
    );
    assert(
      manifest.image_count === EXPECTED_ADDITIONAL_IMAGE_COUNT,
      `В дополнительном манифесте заявлено изображений: ${manifest.image_count ?? "—"}, ожидалось 20.`,
    );
    assert(
      manifest.expected_outputs === EXPECTED_ADDITIONAL_OUTPUT_COUNT,
      `В дополнительном манифесте заявлено роликов: ${manifest.expected_outputs ?? "—"}, ожидалось 60.`,
    );
    assert(
      JSON.stringify(manifest.models) === JSON.stringify(ADDITIONAL_MODEL_ORDER),
      "Дополнительный манифест должен содержать Wan 2.2, Wan 2.7 и Veo 3.1 Lite.",
    );
    assert(
      Array.isArray(manifest.articles) &&
        manifest.articles.length === EXPECTED_ADDITIONAL_ARTICLE_COUNT,
      "В дополнительном манифесте должен быть список из 20 статей.",
    );
    assert(
      Array.isArray(manifest.outputs) &&
        manifest.outputs.length === EXPECTED_ADDITIONAL_OUTPUT_COUNT,
      "В дополнительном манифесте должен быть плоский список из 60 роликов.",
    );

    const baseBySlug = new Map(baseArticles.map((article) => [article.article_slug, article]));
    const usedSourceDigests = new Set(
      baseArticles.map((article) => article.selected_image.sha256),
    );
    const videoPaths = new Set();
    let imageCount = 0;
    let outputCount = 0;

    const normalizedArticles = manifest.articles.map((article, articleIndex) => {
      const baseArticle = baseBySlug.get(article.article_slug);
      assert(baseArticle, `Неизвестная статья в дополнительном манифесте: ${article.article_slug}.`);
      assert(
        article.article_number === baseArticle.article_number,
        `Неверный номер статьи ${article.article_slug}.`,
      );
      assert(
        article.article_slug === baseArticles[articleIndex].article_slug,
        `Нарушен порядок дополнительных статей около ${article.article_slug}.`,
      );
      assert(
        Array.isArray(article.images) && article.images.length === 1,
        `У статьи ${article.article_number} должно быть ровно одно дополнительное изображение.`,
      );

      const images = article.images.map((record) => {
        const image = record?.image;
        assert(image && typeof image === "object", `У ${article.article_number} есть пустая запись image.`);
        assert(image.source_path, `У ${article.article_number}/${image.image_id ?? "—"} нет source_path.`);
        assert(
          Number(image.width) > 0 && Number(image.height) > 0,
          `У ${article.article_number}/${image.image_id ?? "—"} нет геометрии исходника.`,
        );
        assert(
          typeof image.sha256 === "string" && image.sha256.length === 64,
          `У ${article.article_number}/${image.image_id ?? "—"} нет SHA-256.`,
        );
        assert(
          !usedSourceDigests.has(image.sha256),
          `Повторно включён уже обработанный или дублирующийся исходник: ${image.source_path}.`,
        );
        usedSourceDigests.add(image.sha256);

        assert(
          Array.isArray(record.outputs) && record.outputs.length === ADDITIONAL_MODEL_ORDER.length,
          `У ${article.article_number}/${image.image_id} должно быть три ролика.`,
        );
        const outputsByModel = new Map(record.outputs.map((output) => [output.model_id, output]));
        assert(
          outputsByModel.size === ADDITIONAL_MODEL_ORDER.length,
          `У ${article.article_number}/${image.image_id} повторяются модели.`,
        );
        const outputs = ADDITIONAL_MODEL_ORDER.map((modelId) => {
          const output = outputsByModel.get(modelId);
          assert(output, `У ${article.article_number}/${image.image_id} нет модели ${modelId}.`);
          validateOutput(
            article.article_number,
            output,
            videoPaths,
            `${image.image_id} · ${modelId}`,
          );
          outputCount += 1;
          return { ...output, delivery: "repository-raw" };
        });

        imageCount += 1;
        return {
          ...record,
          image: { ...image, delivery: "repository-raw" },
          outputs,
          displayOutputs: outputs,
        };
      });

      return { ...article, images };
    });

    assert(
      imageCount === EXPECTED_ADDITIONAL_IMAGE_COUNT,
      `Проверено дополнительных изображений: ${imageCount}, ожидалось 20.`,
    );
    assert(
      outputCount === EXPECTED_ADDITIONAL_OUTPUT_COUNT &&
        videoPaths.size === EXPECTED_ADDITIONAL_OUTPUT_COUNT,
      "Проверены не все 60 уникальных дополнительных MP4 и positive prompts.",
    );
    return normalizedArticles;
  };

  const validatePromopages10060Manifest = (manifest, historicalArticles) => {
    assert(
      manifest && typeof manifest === "object",
      "Манифест PROMOPAGES-10060 имеет неверный формат.",
    );
    assert(manifest.schema_version === 1, "PROMOPAGES-10060 должен использовать schema_version 1.");
    assert(
      manifest.manifest_role === "promopages-10060-all-images",
      "PROMOPAGES-10060 имеет неверный manifest_role.",
    );
    assert(manifest.ticket === "PROMOPAGES-10060", "PROMOPAGES-10060 имеет неверный ticket.");
    assert(
      manifest.agent_id === "clipmaker-lite",
      "PROMOPAGES-10060 должен быть подготовлен clipmaker-lite.",
    );
    assert(
      JSON.stringify(manifest.models) === JSON.stringify(MODEL_ORDER),
      "PROMOPAGES-10060 должен содержать Wan 2.2, Wan 2.7 и Veo 3.1 Lite.",
    );
    assert(
      manifest.article_count === EXPECTED_PROMOPAGES_10060_ARTICLE_COUNT,
      `PROMOPAGES-10060 должен содержать ${EXPECTED_PROMOPAGES_10060_ARTICLE_COUNT} доступных статей.`,
    );
    assert(
      manifest.image_count === EXPECTED_PROMOPAGES_10060_IMAGE_COUNT,
      `PROMOPAGES-10060 должен содержать все ${EXPECTED_PROMOPAGES_10060_IMAGE_COUNT} изображений.`,
    );
    assert(
      manifest.expected_outputs === EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT,
      `PROMOPAGES-10060 должен содержать ${EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT} роликов.`,
    );
    const providerFilteredOutputCount = manifest.provider_filtered_output_count;
    const providerUnavailableOutputCount = manifest.provider_unavailable_output_count;
    assert(
      Number.isInteger(providerFilteredOutputCount) &&
        providerFilteredOutputCount >= 0 &&
        Number.isInteger(providerUnavailableOutputCount) &&
        providerUnavailableOutputCount >= 0 &&
        manifest.accepted_output_count ===
          EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT -
            providerFilteredOutputCount -
            providerUnavailableOutputCount &&
        manifest.terminal_accounted_output_count ===
          EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT,
      "PROMOPAGES-10060 имеет неверные accepted/terminal/no-media счётчики.",
    );
    assert(
      manifest.status_summary &&
        typeof manifest.status_summary === "object" &&
        manifest.status_summary[PROVIDER_FILTERED_STATUS] ===
          providerFilteredOutputCount &&
        (manifest.status_summary[PROVIDER_UNAVAILABLE_STATUS] ?? 0) ===
          providerUnavailableOutputCount &&
        Object.values(manifest.status_summary).every(
          (count) => Number.isInteger(count) && count >= 0,
        ) &&
        Object.values(manifest.status_summary).reduce((sum, count) => sum + count, 0) ===
          EXPECTED_PROMOPAGES_10060_OUTPUT_COUNT,
      "PROMOPAGES-10060 status_summary не совпадает с 276 logical outputs.",
    );
    assert(
      manifest.acceptance_policy?.requires_mp4_and_media === true &&
        manifest.acceptance_policy?.provider_filtered_requires_exhausted_retry_v1 === true &&
        manifest.acceptance_policy
          ?.provider_unavailable_requires_ambiguous_submit_retry_v1 === true &&
        Array.isArray(
          manifest.acceptance_policy?.provider_unavailable_requires_retry_v1,
        ) &&
        manifest.acceptance_policy.provider_unavailable_requires_retry_v1.length === 2 &&
        [AMBIGUOUS_SUBMIT_RETRY_KIND, NORMALIZED_INPUT_RETRY_KIND].every((retryKind) =>
          manifest.acceptance_policy.provider_unavailable_requires_retry_v1.includes(
            retryKind,
          ),
        ) &&
        Array.isArray(manifest.acceptance_policy?.terminal_accounted_without_media) &&
        manifest.acceptance_policy.terminal_accounted_without_media.length === 2 &&
        [PROVIDER_FILTERED_STATUS, PROVIDER_UNAVAILABLE_STATUS].every((status) =>
          manifest.acceptance_policy.terminal_accounted_without_media.includes(status),
        ),
      "PROMOPAGES-10060 acceptance policy не фиксирует audited no-media outputs.",
    );
    assert(
      Array.isArray(manifest.articles) &&
        manifest.articles.length === manifest.article_count,
      "Число статей PROMOPAGES-10060 не совпадает с article_count.",
    );

    const knownSourcePaths = new Set(
      historicalArticles.flatMap((article) =>
        article.images.map((record) => record.image.source_path),
      ),
    );
    const usedVideoPaths = new Set(
      historicalArticles.flatMap((article) =>
        article.images.flatMap((record) => [
          ...(record.displayOutputs || record.outputs),
          ...(record.loopExperiment?.outputs || []),
          ...(record.smoothExperiment?.outputs || []),
        ]).map((output) => output.video_path),
      ),
    );
    const articleNumbers = new Set();
    const articleSlugs = new Set();
    const nestedOutputs = [];
    let previousArticleNumber = 0;
    let imageCount = 0;
    let outputCount = 0;
    let filteredOutputCount = 0;
    let unavailableProviderOutputCount = 0;
    let normalizedInputRetryOutputCount = 0;
    let normalizedInputAssetIdentity = null;

    const articles = manifest.articles.map((article) => {
      assert(
        typeof article.article_number === "string" && /^\d{2}$/.test(article.article_number),
        "PROMOPAGES-10060 содержит некорректный локальный номер статьи.",
      );
      const numericArticleNumber = Number(article.article_number);
      assert(
        numericArticleNumber > previousArticleNumber,
        `Нарушен порядок PROMOPAGES-10060 около статьи ${article.article_number}.`,
      );
      previousArticleNumber = numericArticleNumber;
      assert(
        !articleNumbers.has(article.article_number),
        `Локальный номер PROMOPAGES-10060 повторяется: ${article.article_number}.`,
      );
      articleNumbers.add(article.article_number);
      assert(
        typeof article.article_slug === "string" && article.article_slug.trim(),
        `У PROMOPAGES-10060/${article.article_number} нет slug.`,
      );
      assert(
        !articleSlugs.has(article.article_slug),
        `Slug PROMOPAGES-10060 повторяется: ${article.article_slug}.`,
      );
      articleSlugs.add(article.article_slug);
      assert(
        typeof article.title === "string" && article.title.trim(),
        `У PROMOPAGES-10060/${article.article_number} нет заголовка.`,
      );
      assert(
        typeof article.url === "string" && /^https:\/\//.test(article.url),
        `У PROMOPAGES-10060/${article.article_number} нет URL статьи.`,
      );
      assert(
        typeof article.context_path === "string" && article.context_path.trim(),
        `У PROMOPAGES-10060/${article.article_number} нет пути к контексту.`,
      );
      assert(
        Array.isArray(article.images) && article.images.length > 0,
        `У PROMOPAGES-10060/${article.article_number} нет изображений.`,
      );
      assert(
        article.image_count === article.images.length,
        `У PROMOPAGES-10060/${article.article_number} image_count не совпадает с images[].`,
      );

      const imageIds = new Set();

      const images = article.images.map((record) => {
        const image = record?.image;
        assert(
          image && typeof image === "object" && image.image_id && image.source_path,
          `У PROMOPAGES-10060/${article.article_number} нет данных изображения.`,
        );
        assert(
          typeof image.image_id === "string" && /^\d{2}$/.test(image.image_id),
          `У PROMOPAGES-10060/${article.article_number} некорректный image_id.`,
        );
        assert(
          !imageIds.has(image.image_id),
          `У PROMOPAGES-10060/${article.article_number} повторяется image_id ${image.image_id}.`,
        );
        imageIds.add(image.image_id);
        assert(
          !hasOwn(image, "delivery") || image.delivery === "repository-raw",
          `Исходник PROMOPAGES-10060/${article.article_number}/${image.image_id} имеет неверный delivery.`,
        );
        assert(
          typeof image.manifest_file_path === "string" && image.manifest_file_path.trim(),
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} нет manifest_file_path.`,
        );
        assert(
          Number(image.width) > 0 && Number(image.height) > 0,
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} нет геометрии.`,
        );
        assert(
          typeof image.sha256 === "string" && /^[a-f0-9]{64}$/.test(image.sha256),
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} нет SHA-256.`,
        );
        assert(
          !knownSourcePaths.has(image.source_path),
          `Путь исходника PROMOPAGES-10060 уже использован: ${image.source_path}.`,
        );
        knownSourcePaths.add(image.source_path);

        const planning = record.lite_planning;
        assert(
          planning &&
            typeof planning.run_id === "string" &&
            planning.run_id.trim() &&
            typeof planning.result_path === "string" &&
            planning.result_path.trim() &&
            planning.structured_intent &&
            typeof planning.structured_intent === "object",
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} нет Lite planning.`,
        );
        assert(
          planning.provenance?.verified === true &&
            planning.provenance?.agent_id === "clipmaker-lite",
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} не подтверждён Lite provenance.`,
        );
        assert(
          Array.isArray(record.outputs) && record.outputs.length === MODEL_ORDER.length,
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} должно быть три ролика.`,
        );
        const outputsByModel = new Map(record.outputs.map((output) => [output.model_id, output]));
        assert(
          outputsByModel.size === MODEL_ORDER.length,
          `У PROMOPAGES-10060/${article.article_number}/${image.image_id} повторяются модели.`,
        );
        const outputs = MODEL_ORDER.map((modelId) => {
          const output = outputsByModel.get(modelId);
          assert(
            output,
            `У PROMOPAGES-10060/${article.article_number}/${image.image_id} нет ${modelId}.`,
          );
          assert(
            !hasOwn(output, "delivery") || output.delivery === "repository-raw",
            `У PROMOPAGES-10060/${article.article_number}/${image.image_id}/${modelId} неверный delivery.`,
          );
          assert(
            output.article_slug === article.article_slug &&
              output.image_id === image.image_id,
            `У PROMOPAGES-10060/${article.article_number}/${image.image_id}/${modelId} неверный output key.`,
          );
          let normalizedOutput;
          if (output.status === PROVIDER_FILTERED_STATUS) {
            normalizedOutput = validateProviderFilteredOutput(
              articleIdentityLabel({
                sourceTicket: manifest.ticket,
                article_number: article.article_number,
              }),
              output,
              `${image.image_id} · ${modelId}`,
            );
            filteredOutputCount += 1;
          } else if (output.status === PROVIDER_UNAVAILABLE_STATUS) {
            if (output.retry?.retry_kind === NORMALIZED_INPUT_RETRY_KIND) {
              normalizedOutput = validateNormalizedInputProviderUnavailable(
                articleIdentityLabel({
                  sourceTicket: manifest.ticket,
                  article_number: article.article_number,
                }),
                output,
                image,
                `${image.image_id} · ${modelId}`,
              );
              normalizedInputRetryOutputCount += 1;
            } else {
              normalizedOutput = validateProviderUnavailableOutput(
                articleIdentityLabel({
                  sourceTicket: manifest.ticket,
                  article_number: article.article_number,
                }),
                output,
                `${image.image_id} · ${modelId}`,
              );
            }
            unavailableProviderOutputCount += 1;
          } else {
            assert(
              ["succeeded", "verification-failed"].includes(output.status),
              `У PROMOPAGES-10060/${article.article_number}/${image.image_id}/${modelId} неверный статус.`,
            );
            validateOutput(
              articleIdentityLabel({
                sourceTicket: manifest.ticket,
                article_number: article.article_number,
              }),
              output,
              usedVideoPaths,
              `${image.image_id} · ${modelId}`,
            );
            const hasAmbiguousRetryMarker =
              (typeof output.selected_attempt === "string" &&
                output.selected_attempt.startsWith(AMBIGUOUS_SUBMIT_RETRY_SELECTION)) ||
              output.retry?.retry_kind === AMBIGUOUS_SUBMIT_RETRY_KIND;
            if (hasAmbiguousRetryMarker) {
              validateAmbiguousSubmitRetry(
                output,
                `${articleIdentityLabel({
                  sourceTicket: manifest.ticket,
                  article_number: article.article_number,
                })} / ${image.image_id} · ${modelId}`,
                { exhausted: false },
              );
            }
            const hasNormalizedInputRetryMarker =
              (typeof output.selected_attempt === "string" &&
                output.selected_attempt.startsWith(NORMALIZED_INPUT_RETRY_SELECTION)) ||
              output.retry?.retry_kind === NORMALIZED_INPUT_RETRY_KIND;
            if (hasNormalizedInputRetryMarker) {
              validateNormalizedInputRetry(
                output,
                image,
                `${articleIdentityLabel({
                  sourceTicket: manifest.ticket,
                  article_number: article.article_number,
                })} / ${image.image_id} · ${modelId}`,
                { exhausted: false },
              );
              normalizedInputRetryOutputCount += 1;
            }
            normalizedOutput = {
              ...output,
              availableVideo: true,
              providerFiltered: false,
              providerUnavailable: false,
              normalizedInputRetry: hasNormalizedInputRetryMarker,
            };
          }
          if (normalizedOutput.normalizedInputRetry === true) {
            const transform = normalizedOutput.retry.source_transform;
            const assetIdentity = JSON.stringify({
              strategy: transform.strategy,
              original: transform.original,
              normalized: transform.normalized,
            });
            assert(
              normalizedInputAssetIdentity === null ||
                normalizedInputAssetIdentity === assetIdentity,
              "PROMOPAGES-10060 normalized-input retries должны использовать один frozen asset.",
            );
            normalizedInputAssetIdentity = assetIdentity;
          }
          nestedOutputs.push(output);
          outputCount += 1;
          return { ...normalizedOutput, delivery: "repository-raw" };
        });

        imageCount += 1;
        return {
          ...record,
          image: { ...image, delivery: "repository-raw" },
          outputs,
          displayOutputs: outputs,
        };
      });

      const hasWarnings = images.some((record) =>
        record.outputs.some((output) => output.status === "verification-failed"),
      );
      const unavailableOutputCount = images.reduce(
        (total, record) =>
          total + record.outputs.filter((output) => output.availableVideo === false).length,
        0,
      );
      return {
        ...article,
        case_key: makeCaseKey(manifest.ticket, article.article_slug),
        sourceTicket: manifest.ticket,
        sourceStatus: unavailableOutputCount
          ? `Готово частично · ${images.length} изобр. · ${unavailableOutputCount} видео недоступно`
          : hasWarnings
            ? `Готово с media-предупреждениями · ${images.length} изобр.`
            : `Готово к просмотру · ${images.length} изобр.`,
        images,
      };
    });

    assert(
      JSON.stringify([...articleNumbers]) ===
        JSON.stringify(EXPECTED_PROMOPAGES_10060_ARTICLE_NUMBERS),
      "PROMOPAGES-10060 должен содержать доступные статьи 01 и 03–14.",
    );

    assert(
      imageCount === manifest.image_count,
      `PROMOPAGES-10060 содержит изображений: ${imageCount}, заявлено ${manifest.image_count}.`,
    );
    assert(
      outputCount === manifest.expected_outputs &&
        manifest.expected_outputs === manifest.image_count * MODEL_ORDER.length,
      `PROMOPAGES-10060 содержит роликов: ${outputCount}, заявлено ${manifest.expected_outputs}.`,
    );
    assert(
      filteredOutputCount === providerFilteredOutputCount,
      `PROMOPAGES-10060 provider-filtered outputs: ${filteredOutputCount}, заявлено ${providerFilteredOutputCount}.`,
    );
    assert(
      unavailableProviderOutputCount === providerUnavailableOutputCount,
      `PROMOPAGES-10060 provider-unavailable outputs: ${unavailableProviderOutputCount}, заявлено ${providerUnavailableOutputCount}.`,
    );
    if (normalizedInputRetryOutputCount > 0) {
      const retryCost = manifest.cost;
      const retryPolicy = manifest.generation_policy?.normalized_input_retry;
      assert(
        retryCost?.normalized_input_retry_version === 1 &&
          typeof retryCost.normalized_input_retry_accounting_cost_usd === "number" &&
          Number.isFinite(retryCost.normalized_input_retry_accounting_cost_usd) &&
          retryCost.normalized_input_retry_accounting_cost_usd > 0 &&
          retryCost.normalized_input_retry_reservations ===
            normalizedInputRetryOutputCount,
        "PROMOPAGES-10060 normalized-input retry cost accounting не совпадает с outputs.",
      );
      assert(
        retryPolicy?.version === 1 &&
          typeof retryPolicy.namespace === "string" &&
          retryPolicy.namespace.trim() &&
          typeof retryPolicy.shared_asset_namespace === "string" &&
          retryPolicy.shared_asset_namespace.trim() &&
          retryPolicy.eligible_source?.article_slug ===
            "12-dream-island-7-fishek" &&
          retryPolicy.eligible_source?.image_id === "08" &&
          JSON.stringify(retryPolicy.models) ===
            JSON.stringify(["alibaba/wan-2.2", "alibaba/wan-2.7"]) &&
          retryPolicy.explicit_operator_command_required === true &&
          retryPolicy.maximum_new_paid_submissions_per_eligible_output === 1 &&
          retryPolicy.retry2_forbidden === true &&
          retryPolicy.automatic_paid_retries === false &&
          retryPolicy.fallback === false &&
          retryPolicy.primary_receipts_immutable === true &&
          retryPolicy.request_delta_only_image_pointer === true,
        "PROMOPAGES-10060 normalized-input generation policy некорректна.",
      );
      articles.forEach((article) => {
        article.images.forEach((record) => {
          record.outputs
            .filter((output) => output.normalizedInputRetry === true)
            .forEach((output) => {
              assert(
                output.retry.namespace.startsWith(`${retryPolicy.namespace}/`) &&
                  output.retry.source_transform.normalized.metadata_path.startsWith(
                    `${retryPolicy.shared_asset_namespace}/`,
                  ),
                "PROMOPAGES-10060 normalized-input retry вышел за разрешённые namespaces.",
              );
            });
        });
      });
    }
    assert(
      Array.isArray(manifest.outputs) && manifest.outputs.length === outputCount,
      "Плоский outputs PROMOPAGES-10060 не совпадает с вложенными роликами.",
    );
    const outputKey = (output) =>
      `${output?.article_slug ?? ""}\u0000${output?.image_id ?? ""}\u0000${output?.model_id ?? ""}`;
    const nestedOutputKeys = new Set(nestedOutputs.map(outputKey));
    const flatOutputKeys = new Set(manifest.outputs.map(outputKey));
    assert(
      flatOutputKeys.size === outputCount &&
        nestedOutputKeys.size === outputCount &&
        [...flatOutputKeys].every((key) => nestedOutputKeys.has(key)),
      "Плоский outputs PROMOPAGES-10060 ссылается не на вложенные logical outputs.",
    );

    const nestedByKey = new Map(nestedOutputs.map((output) => [outputKey(output), output]));
    manifest.outputs.forEach((output) => {
      const nestedOutput = nestedByKey.get(outputKey(output));
      assert(
        nestedOutput &&
          output.status === nestedOutput.status &&
          output.video_path === nestedOutput.video_path &&
          output.provider_run_id === nestedOutput.provider_run_id &&
          output.recorded_status === nestedOutput.recorded_status &&
          output.selected_attempt === nestedOutput.selected_attempt &&
          output.error === nestedOutput.error &&
          JSON.stringify(output.media ?? null) ===
            JSON.stringify(nestedOutput.media ?? null) &&
          JSON.stringify(output.contract_check ?? null) ===
            JSON.stringify(nestedOutput.contract_check ?? null) &&
          JSON.stringify(output.retry ?? null) === JSON.stringify(nestedOutput.retry ?? null),
        "Плоский output PROMOPAGES-10060 не совпадает с вложенным статусом или retry audit.",
      );
    });

    const unavailableArticles = manifest.unavailable_articles ?? [];
    assert(
      Array.isArray(unavailableArticles) && unavailableArticles.length === 1,
      "PROMOPAGES-10060 должен содержать одну недоступную статью.",
    );
    const unavailableNumbers = new Set();
    const unavailableSlugs = new Set();
    unavailableArticles.forEach((article) => {
      assert(
        typeof article.article_number === "string" && /^\d{2}$/.test(article.article_number),
        "Недоступная статья PROMOPAGES-10060 имеет неверный номер.",
      );
      assert(
        typeof article.article_slug === "string" && article.article_slug.trim(),
        "Недоступная статья PROMOPAGES-10060 не имеет slug.",
      );
      assert(
        typeof article.url === "string" && /^https:\/\//.test(article.url),
        "Недоступная статья PROMOPAGES-10060 не имеет URL.",
      );
      assert(
        article.status === "source-unavailable" &&
          typeof article.error === "string" &&
          article.error.trim(),
        `Недоступная статья PROMOPAGES-10060/${article.article_number} не объясняет статус.`,
      );
      assert(
        !articleNumbers.has(article.article_number) &&
          !unavailableNumbers.has(article.article_number) &&
          !articleSlugs.has(article.article_slug) &&
          !unavailableSlugs.has(article.article_slug),
        "Недоступная статья PROMOPAGES-10060 дублирует доступную или другую недоступную статью.",
      );
      unavailableNumbers.add(article.article_number);
      unavailableSlugs.add(article.article_slug);
    });
    assert(
      unavailableNumbers.has(EXPECTED_PROMOPAGES_10060_UNAVAILABLE_ARTICLE_NUMBER),
      "Недоступной статьёй PROMOPAGES-10060 должна быть статья 02.",
    );

    return {
      articles,
      unavailableArticles,
      filteredOutputCount,
      providerUnavailableOutputCount,
      unavailableOutputCount: filteredOutputCount + unavailableProviderOutputCount,
      normalizedInputRetryOutputCount,
    };
  };

  const validateLoopExperiment = (loopExperiment, usedVideoPaths) => {
    assert(
      loopExperiment && typeof loopExperiment === "object",
      "Loop-эксперимент кейса 21 имеет неверный формат.",
    );
    assert(
      typeof loopExperiment.experiment_id === "string" &&
        loopExperiment.experiment_id.trim(),
      "У loop-эксперимента нет experiment_id.",
    );
    assert(
      loopExperiment.model_id === LOOP_MODEL_ID,
      "Loop-эксперимент разрешён только для alibaba/wan-2.7.",
    );

    const requestContract = loopExperiment.request_contract;
    assert(
      requestContract &&
        requestContract.classification === LOOP_REQUEST_CLASSIFICATION &&
        requestContract.verified_lite_planning === true &&
        requestContract.canonical_lite_runtime === false &&
        requestContract.request_mechanism === LOOP_REQUEST_MECHANISM &&
        requestContract.last_frame_is_source === true &&
        requestContract.same_source_for_endpoints === true &&
        requestContract.provider_native_loop_parameter === false &&
        requestContract.browser_playback_loop === true &&
        JSON.stringify(requestContract.frame_types) === JSON.stringify(LOOP_FRAME_TYPES),
      "Loop-эксперимент должен честно описывать API conditioning одинаковым first/last source.",
    );

    const cost = loopExperiment.cost;
    assert(
      cost &&
        cost.currency === "USD" &&
        Number(cost.operator_budget_cap_usd) > 0 &&
        Number(cost.operator_budget_cap_usd) <= 5 &&
        Number(cost.reserved_usd) >= 0 &&
        Number(cost.reserved_usd) <= Number(cost.operator_budget_cap_usd) &&
        cost.automatic_paid_retries === false &&
        cost.actual_billing_available === false,
      "Бюджет loop-эксперимента должен оставаться внутри отдельного лимита $5.",
    );
    assert(
      Array.isArray(loopExperiment.outputs) &&
        Array.isArray(loopExperiment.attempt_history),
      "У loop-эксперимента нет outputs или attempt_history.",
    );

    const attempts = loopExperiment.attempt_history;
    const availableAttempts = attempts.filter((attempt) => attempt.available_video === true);
    const failedAttempts = attempts.filter((attempt) => attempt.available_video !== true);
    assert(
      loopExperiment.attempt_count === attempts.length &&
        loopExperiment.attempts_without_video_count === failedAttempts.length &&
        loopExperiment.available_output_count === loopExperiment.outputs.length &&
        availableAttempts.length === loopExperiment.outputs.length,
      "Счётчики loop-эксперимента не совпадают с полной историей запусков.",
    );

    const attemptByRunId = new Map();
    attempts.forEach((attempt, attemptIndex) => {
      assert(
        attempt &&
          attempt.activity === "loop-closure-experiment" &&
          attempt.experiment_id === loopExperiment.experiment_id &&
          attempt.model_id === LOOP_MODEL_ID &&
          typeof attempt.provider_run_id === "string" &&
          attempt.provider_run_id.trim() &&
          !attemptByRunId.has(attempt.provider_run_id),
        `Неверная identity loop-попытки ${attemptIndex + 1}.`,
      );
      assert(
        attempt.selected_for_display === attempt.available_video,
        `Loop-попытка ${attemptIndex + 1} неверно помечена для показа.`,
      );
      const attemptNumber =
        attempt.experiment_attempt_number ?? attempt.model_attempt_number ?? attemptIndex + 1;
      assert(
        Number.isInteger(attemptNumber) && attemptNumber > 0,
        `У loop-попытки ${attemptIndex + 1} нет номера.`,
      );
      attemptByRunId.set(attempt.provider_run_id, {
        ...attempt,
        experimentAttemptNumber: attemptNumber,
      });
    });

    const outputs = loopExperiment.outputs
      .map((output, outputIndex) => {
        const attempt = attemptByRunId.get(output?.provider_run_id);
        assert(
          output &&
            output.model_id === LOOP_MODEL_ID &&
            output.delivery === "repository-raw" &&
            output.available === true &&
            attempt?.available_video === true,
          `Loop-output ${outputIndex + 1} не связан с доступной Wan 2.7 попыткой.`,
        );
        const selection = output.selection;
        assert(
          selection &&
            selection.activity === "loop-closure-experiment" &&
            selection.experiment_id === loopExperiment.experiment_id &&
            typeof selection.variant_id === "string" &&
            selection.variant_id.trim(),
          `У loop-output ${outputIndex + 1} нет точной experiment selection.`,
        );
        const closure = output.loop_closure;
        const seamReview = closure?.seam_review;
        assert(
          closure &&
            typeof closure.request_sha256 === "string" &&
            closure.request_sha256.length === 64 &&
            JSON.stringify(closure.frame_types) === JSON.stringify(LOOP_FRAME_TYPES) &&
            closure.same_source_for_endpoints === true &&
            closure.browser_playback_loop === true &&
            seamReview &&
            hasOwn(LOOP_SEAM_PRESENTATION, seamReview.status) &&
            typeof seamReview.summary === "string" &&
            seamReview.summary.trim(),
          `Loop-output ${outputIndex + 1} не содержит честного seam review.`,
        );
        validateOutput("21", output, usedVideoPaths, `loop ${outputIndex + 1}`);
        const label = selection.variant_label || selection.variant_id;
        return {
          ...output,
          experimentAttemptNumber: attempt.experimentAttemptNumber,
          showcaseLabel: `${label} · API first/last · попытка ${attempt.experimentAttemptNumber}`,
          showcaseVariant: "loop",
        };
      })
      .sort(
        (left, right) =>
          left.experimentAttemptNumber - right.experimentAttemptNumber,
      );

    const outputRunIds = new Set(outputs.map((output) => output.provider_run_id));
    const availableRunIds = new Set(
      availableAttempts.map((attempt) => attempt.provider_run_id),
    );
    assert(
      outputRunIds.size === outputs.length &&
        outputRunIds.size === availableRunIds.size &&
        [...outputRunIds].every((runId) => availableRunIds.has(runId)),
      "Не все доступные loop-результаты включены в демо.",
    );

    return {
      ...loopExperiment,
      outputs,
      failedAttempts: failedAttempts.map((attempt) => attemptByRunId.get(attempt.provider_run_id)),
      requestContract,
    };
  };

  const validateSmoothExperiment = (smoothExperiment, usedVideoPaths) => {
    assert(
      smoothExperiment && typeof smoothExperiment === "object",
      "Smooth-эксперимент кейса 21 имеет неверный формат.",
    );
    assert(
      typeof smoothExperiment.experiment_id === "string" &&
        smoothExperiment.experiment_id.trim(),
      "У smooth-эксперимента нет experiment_id.",
    );
    assert(
      smoothExperiment.model_id === LOOP_MODEL_ID,
      "Smooth-эксперимент разрешён только для alibaba/wan-2.7.",
    );

    const requestContract = smoothExperiment.request_contract;
    assert(
      requestContract &&
        requestContract.classification === SMOOTH_REQUEST_CLASSIFICATION &&
        requestContract.verified_lite_planning === true &&
        requestContract.canonical_lite_runtime === true &&
        requestContract.request_mechanism === SMOOTH_REQUEST_MECHANISM &&
        requestContract.last_frame_is_source === false &&
        requestContract.same_source_for_endpoints === false &&
        requestContract.provider_native_loop_parameter === false &&
        requestContract.browser_playback_loop === false &&
        JSON.stringify(requestContract.frame_types) ===
          JSON.stringify(SMOOTH_FRAME_TYPES) &&
        typeof requestContract.first_frame_url === "string" &&
        requestContract.first_frame_url.trim() &&
        requestContract.last_frame_url === null,
      "Smooth-эксперимент должен честно описывать canonical first-frame-only запрос без loop.",
    );

    const cost = smoothExperiment.cost;
    const reservedUsd = Number(cost?.reserved_usd ?? cost?.initial_reserved_usd);
    assert(
      cost &&
        cost.currency === "USD" &&
        Number(cost.operator_budget_cap_usd) > 0 &&
        Number(cost.operator_budget_cap_usd) <= 3 &&
        reservedUsd >= 0 &&
        reservedUsd <= Number(cost.operator_budget_cap_usd) &&
        cost.automatic_paid_retries === false &&
        cost.actual_billing_available === false,
      "Бюджет smooth-эксперимента должен оставаться внутри отдельного лимита $3.",
    );
    assert(
      Array.isArray(smoothExperiment.outputs) &&
        Array.isArray(smoothExperiment.attempt_history),
      "У smooth-эксперимента нет outputs или attempt_history.",
    );

    const attempts = smoothExperiment.attempt_history;
    const availableAttempts = attempts.filter((attempt) => attempt.available_video === true);
    const failedAttempts = attempts.filter((attempt) => attempt.available_video !== true);
    const selectedAttempts = attempts.filter(
      (attempt) => attempt.selected_for_display === true,
    );
    const availableAttemptCount =
      smoothExperiment.available_attempt_count ?? smoothExperiment.available_output_count;
    const displayOutputCount =
      smoothExperiment.display_output_count ?? smoothExperiment.available_output_count;
    const excludedFromDemoCount =
      smoothExperiment.excluded_from_demo_count ??
      availableAttempts.length - selectedAttempts.length;
    assert(
      smoothExperiment.attempt_count === attempts.length &&
        smoothExperiment.attempts_without_video_count === failedAttempts.length &&
        availableAttemptCount === availableAttempts.length &&
        smoothExperiment.available_output_count === smoothExperiment.outputs.length &&
        displayOutputCount === smoothExperiment.outputs.length &&
        excludedFromDemoCount === availableAttempts.length - selectedAttempts.length &&
        selectedAttempts.length === smoothExperiment.outputs.length &&
        smoothExperiment.outputs.length === EXPECTED_CASE_21_SMOOTH_OUTPUT_COUNT,
      "Smooth-эксперимент должен содержать четыре выбранных результата и полную историю запусков.",
    );

    const attemptByRunId = new Map();
    const baseAttempts = [];
    const retryAttempts = [];
    attempts.forEach((attempt, attemptIndex) => {
      const isBaseAttempt =
        attempt?.activity === "smooth-motion-experiment" &&
        attempt.experiment_id === smoothExperiment.experiment_id;
      const isRetryAttempt =
        attempt?.activity === SMOOTH_RETRY_ACTIVITY &&
        typeof attempt.experiment_id === "string" &&
        attempt.experiment_id.trim() &&
        attempt.experiment_id !== smoothExperiment.experiment_id &&
        attempt.series_experiment_id === smoothExperiment.experiment_id &&
        attempt.variant_id === SMOOTH_RETRY_VARIANT_ID &&
        attempt.retry_of === SMOOTH_RETRY_OF_PROVIDER_RUN_ID &&
        attempt.supersedes_for_demo === SMOOTH_RETRY_OF_PROVIDER_RUN_ID;
      assert(
        attempt &&
          (isBaseAttempt || isRetryAttempt) &&
          attempt.model_id === LOOP_MODEL_ID &&
          typeof attempt.provider_run_id === "string" &&
          attempt.provider_run_id.trim() &&
          attempt.provider_may_be_active === false &&
          !attemptByRunId.has(attempt.provider_run_id),
        `Неверная identity smooth-попытки ${attemptIndex + 1}.`,
      );
      if (isRetryAttempt) retryAttempts.push(attempt);
      else baseAttempts.push(attempt);
      assert(
        typeof attempt.selected_for_display === "boolean" &&
          (!attempt.selected_for_display || attempt.available_video === true),
        `Недоступная smooth-попытка ${attemptIndex + 1} не может быть выбрана для показа.`,
      );
      const attemptNumber =
        attempt.experiment_attempt_number ?? attempt.model_attempt_number ?? attemptIndex + 1;
      assert(
        Number.isInteger(attemptNumber) && attemptNumber > 0,
        `У smooth-попытки ${attemptIndex + 1} нет номера.`,
      );
      attemptByRunId.set(attempt.provider_run_id, {
        ...attempt,
        isExplicitRetry: isRetryAttempt,
        experimentAttemptNumber: attemptNumber,
      });
    });
    assert(
      baseAttempts.length === EXPECTED_CASE_21_SMOOTH_OUTPUT_COUNT &&
        retryAttempts.length === 1,
      "Smooth-история должна содержать четыре main-попытки и один explicit retry.",
    );
    const retryAttempt = retryAttempts[0];
    const replacedAttempt = attemptByRunId.get(retryAttempt.retry_of);
    assert(
      replacedAttempt &&
        replacedAttempt.variant_id === SMOOTH_REPLACED_VARIANT_ID &&
        replacedAttempt.isExplicitRetry === false &&
        replacedAttempt.available_video === true &&
        replacedAttempt.selected_for_display === false &&
        retryAttempt.available_video === true &&
        retryAttempt.selected_for_display === true,
      "Explicit retry должен заменить исходный staggered-ease только в demo selection.",
    );

    const featuredReview = smoothExperiment.featured_review;
    const featuredPractices = featuredReview?.practices;
    const featuredPracticeIds = Array.isArray(featuredPractices)
      ? featuredPractices.map((practice) => practice?.id)
      : [];
    assert(
      featuredReview &&
        featuredReview.schema_version === SMOOTH_FEATURED_REVIEW_SCHEMA &&
        featuredReview.status === "visual-winner" &&
        featuredReview.label === "Визуальный победитель" &&
        featuredReview.reviewer === "operator-visual-selection" &&
        featuredReview.selection_basis ===
          "operator-visual-review-not-proxy-rank" &&
        featuredReview.variant_id === SMOOTH_RETRY_VARIANT_ID &&
        featuredReview.provider_run_id === retryAttempt.provider_run_id &&
        typeof featuredReview.summary === "string" &&
        featuredReview.summary.trim() &&
        typeof featuredReview.prompt_distinction === "string" &&
        featuredReview.prompt_distinction.trim() &&
        JSON.stringify(featuredPracticeIds) ===
          JSON.stringify(SMOOTH_FEATURED_PRACTICE_IDS) &&
        featuredPractices.every(
          (practice) =>
            practice &&
            typeof practice.title === "string" &&
            practice.title.trim() &&
            typeof practice.description === "string" &&
            practice.description.trim(),
        ),
      "Smooth featured review должен точно описывать выбранный staggered retry.",
    );
    const featuredRawOutput = smoothExperiment.outputs.find(
      (output) => output?.provider_run_id === featuredReview.provider_run_id,
    );
    const featuredOutputProxy = featuredRawOutput?.smooth_motion?.proxy_review;
    const featuredEvidence = featuredReview.evidence;
    assert(
      featuredRawOutput?.selection?.variant_id === featuredReview.variant_id &&
        featuredEvidence &&
        featuredEvidence.analysis_status === "measured" &&
        featuredEvidence.regions_with_detected_motion === 7 &&
        featuredEvidence.requested_region_count === 7 &&
        featuredEvidence.abrupt_transition_count === 0 &&
        featuredEvidence.motion_energy_spike_count === 0 &&
        featuredEvidence.proxy_rank === 2 &&
        featuredEvidence.proxy_rank_scale === attempts.length &&
        featuredOutputProxy?.analysis_status === featuredEvidence.analysis_status &&
        featuredOutputProxy.proxy_rank === featuredEvidence.proxy_rank &&
        featuredOutputProxy.motion_coverage?.regions_with_detected_motion ===
          featuredEvidence.regions_with_detected_motion &&
        featuredOutputProxy.motion_coverage?.requested_region_count ===
          featuredEvidence.requested_region_count &&
        featuredOutputProxy.requested_union_smoothness?.acceleration_proxy_mae_rgb
          ?.abrupt_transition_count === featuredEvidence.abrupt_transition_count &&
        featuredOutputProxy.requested_union_smoothness?.motion_energy_mae_rgb
          ?.spike_count === featuredEvidence.motion_energy_spike_count,
      "Smooth featured review не связан с выбранным output.",
    );

    const outputs = smoothExperiment.outputs
      .map((output, outputIndex) => {
        const attempt = attemptByRunId.get(output?.provider_run_id);
        assert(
          output &&
            output.model_id === LOOP_MODEL_ID &&
            output.delivery === "repository-raw" &&
            output.available === true &&
            attempt?.available_video === true &&
            attempt.selected_for_display === true,
          `Smooth-output ${outputIndex + 1} не связан с выбранной Wan 2.7 попыткой.`,
        );
        assert(
          !hasOwn(output, "loop_closure"),
          `Smooth-output ${outputIndex + 1} не должен содержать loop_closure.`,
        );
        const selection = output.selection;
        assert(
          selection &&
            selection.activity === "smooth-motion-experiment" &&
            selection.experiment_id === smoothExperiment.experiment_id &&
            typeof selection.variant_id === "string" &&
            selection.variant_id.trim(),
          `У smooth-output ${outputIndex + 1} нет точной experiment selection.`,
        );
        assert(
          attempt.isExplicitRetry
            ? selection.retry_of === attempt.retry_of &&
                selection.supersedes_for_demo === attempt.supersedes_for_demo
            : selection.retry_of == null && selection.supersedes_for_demo == null,
          `Smooth-output ${outputIndex + 1} неверно описывает retry selection.`,
        );
        const smoothMotion = output.smooth_motion;
        const proxyReview = smoothMotion?.proxy_review;
        const motionCoverage = proxyReview?.motion_coverage;
        assert(
          smoothMotion &&
            typeof smoothMotion.request_sha256 === "string" &&
            smoothMotion.request_sha256.length === 64 &&
            JSON.stringify(smoothMotion.frame_types) ===
              JSON.stringify(SMOOTH_FRAME_TYPES) &&
            smoothMotion.browser_playback_loop === false &&
            proxyReview &&
            proxyReview.analysis_status === "measured" &&
            Number.isInteger(proxyReview.proxy_rank) &&
            proxyReview.proxy_rank >= 1 &&
            proxyReview.proxy_rank <= attempts.length &&
            motionCoverage &&
            motionCoverage.requested_region_count === 7 &&
            Number.isInteger(motionCoverage.regions_with_detected_motion) &&
            motionCoverage.regions_with_detected_motion >= 0 &&
            motionCoverage.regions_with_detected_motion <= 7 &&
            Array.isArray(motionCoverage.missing_motion_regions),
          `Smooth-output ${outputIndex + 1} не содержит честного motion proxy review.`,
        );
        const visualReview = output.visual_review;
        assert(
          visualReview &&
            typeof visualReview.status === "string" &&
            visualReview.status.trim() &&
            typeof visualReview.summary === "string" &&
            visualReview.summary.trim() &&
            typeof visualReview.human_semantic_review_complete === "boolean",
          `Smooth-output ${outputIndex + 1} не содержит честного visual review.`,
        );
        validateOutput("21", output, usedVideoPaths, `smooth ${outputIndex + 1}`);
        const label = selection.variant_label || selection.variant_id;
        return {
          ...output,
          isFeaturedWinner:
            output.provider_run_id === featuredReview.provider_run_id,
          experimentAttemptNumber: attempt.experimentAttemptNumber,
          motionProxy: {
            status: proxyReview.analysis_status,
            rank: proxyReview.proxy_rank,
            rankScale: attempts.length,
            ...motionCoverage,
          },
          showcaseLabel: `${label} · first-frame only · попытка ${attempt.experimentAttemptNumber}`,
          showcaseVariant: "smooth",
        };
      })
      .sort(
        (left, right) =>
          left.experimentAttemptNumber - right.experimentAttemptNumber,
      );

    const outputRunIds = new Set(outputs.map((output) => output.provider_run_id));
    const selectedRunIds = new Set(
      selectedAttempts.map((attempt) => attempt.provider_run_id),
    );
    assert(
      outputRunIds.size === outputs.length &&
        outputRunIds.size === selectedRunIds.size &&
        [...outputRunIds].every((runId) => selectedRunIds.has(runId)),
      "Не все выбранные smooth-результаты включены в демо.",
    );
    assert(
      outputs.filter((output) => output.isFeaturedWinner).length === 1,
      "Smooth featured review должен выделять ровно один output.",
    );
    assert(
      smoothExperiment.accepted_output_count ===
        outputs.filter((output) => output.accepted === true).length,
      "Счётчик принятых smooth-результатов не совпадает с outputs.",
    );

    return {
      ...smoothExperiment,
      outputs,
      featuredReview,
      failedAttempts: failedAttempts.map((attempt) => attemptByRunId.get(attempt.provider_run_id)),
      requestContract,
    };
  };

  const validateCase21Manifest = (manifest, baseArticles, additionalArticles) => {
    assert(manifest && typeof manifest === "object", "Манифест кейса 21 имеет неверный формат.");
    assert(
      manifest.manifest_role === "case-21-extension",
      "Sidecar должен иметь manifest_role case-21-extension.",
    );
    assert(manifest.agent_id === "clipmaker-lite", "Кейс 21 должен быть создан clipmaker-lite.");
    assert(
      manifest.article_count === EXPECTED_CASE_21_ARTICLE_COUNT,
      "В sidecar должна быть ровно одна статья.",
    );
    assert(
      manifest.image_count === EXPECTED_CASE_21_IMAGE_COUNT,
      "В sidecar должно быть ровно одно изображение.",
    );
    assert(
      manifest.expected_outputs === EXPECTED_CASE_21_OUTPUT_COUNT,
      "В sidecar должно быть заявлено три ролика.",
    );
    assert(
      manifest.canonical_output_count === EXPECTED_CASE_21_OUTPUT_COUNT &&
        manifest.research_output_count === EXPECTED_CASE_21_RESEARCH_OUTPUT_COUNT &&
        manifest.display_output_count === EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT,
      "Sidecar должен разделять три canonical и четыре research-ролика.",
    );
    assert(
      manifest.attempt_count === EXPECTED_CASE_21_ATTEMPT_COUNT &&
        manifest.attempts_without_video_count === 4 &&
        manifest.available_output_count === EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT,
      "История кейса 21 должна содержать 11 запусков и семь MP4.",
    );
    assert(
      JSON.stringify(manifest.models) === JSON.stringify(MODEL_ORDER),
      "Sidecar должен содержать Wan 2.2, Wan 2.7 и Veo 3.1 Lite.",
    );
    assert(
      Array.isArray(manifest.articles) &&
        manifest.articles.length === EXPECTED_CASE_21_ARTICLE_COUNT,
      "В sidecar должен быть список из одной статьи.",
    );
    assert(
      Array.isArray(manifest.outputs) &&
        manifest.outputs.length === EXPECTED_CASE_21_OUTPUT_COUNT,
      "В sidecar должен быть плоский список из трёх роликов.",
    );
    assert(
      Array.isArray(manifest.research_outputs) &&
        manifest.research_outputs.length === EXPECTED_CASE_21_RESEARCH_OUTPUT_COUNT,
      "В sidecar должен быть плоский список из четырёх research-роликов.",
    );
    assert(
      Array.isArray(manifest.attempt_history) &&
        manifest.attempt_history.length === EXPECTED_CASE_21_ATTEMPT_COUNT &&
        manifest.attempt_history.filter((attempt) => attempt.available_video).length ===
          EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT &&
        manifest.attempt_history.filter((attempt) => attempt.selected_for_display).length ===
          EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT,
      "История попыток кейса 21 не совпадает с полным набором MP4.",
    );

    const article = manifest.articles[0];
    assert(article.article_number === "21", "Sidecar должен описывать кейс 21.");
    assert(article.article_slug && article.title, "У кейса 21 нет slug или заголовка.");
    assert(article.context_path, "У кейса 21 нет пути к контексту статьи.");
    assert(
      !baseArticles.some((baseArticle) => baseArticle.article_slug === article.article_slug),
      `Slug кейса 21 уже занят: ${article.article_slug}.`,
    );
    assert(
      Array.isArray(article.images) && article.images.length === EXPECTED_CASE_21_IMAGE_COUNT,
      "У кейса 21 должно быть ровно одно выбранное изображение.",
    );

    const knownSourceDigests = new Set([
      ...baseArticles.map((baseArticle) => baseArticle.selected_image.sha256),
      ...additionalArticles.flatMap((additionalArticle) =>
        additionalArticle.images.map((record) => record.image.sha256),
      ),
    ]);
    const knownSourcePaths = new Set([
      ...baseArticles.map((baseArticle) => baseArticle.selected_image.source_path),
      ...additionalArticles.flatMap((additionalArticle) =>
        additionalArticle.images.map((record) => record.image.source_path),
      ),
    ]);
    const usedVideoPaths = new Set(
      baseArticles.flatMap((baseArticle) => [
        ...baseArticle.outputs,
        ...(baseArticle.comparison_outputs || []),
        ...(baseArticle.external_outputs || []),
      ]).map((output) => output.video_path),
    );
    additionalArticles.forEach((additionalArticle) => {
      additionalArticle.images.forEach((record) => {
        record.outputs.forEach((output) => usedVideoPaths.add(output.video_path));
      });
    });

    const record = article.images[0];
    const image = record?.image;
    assert(image && typeof image === "object", "У кейса 21 нет данных изображения.");
    assert(image.image_id && image.source_path, "У изображения кейса 21 нет ID или source_path.");
    assert(
      Number(image.width) > 0 && Number(image.height) > 0,
      "У изображения кейса 21 нет геометрии.",
    );
    assert(
      typeof image.sha256 === "string" && image.sha256.length === 64,
      "У изображения кейса 21 нет SHA-256.",
    );
    assert(image.delivery === "repository-raw", "Исходник кейса 21 должен доставляться из main.");
    assert(!knownSourceDigests.has(image.sha256), "Исходник кейса 21 дублирует прежнюю выборку.");
    assert(!knownSourcePaths.has(image.source_path), "Путь исходника кейса 21 уже использован.");
    assert(
      Array.isArray(record.outputs) && record.outputs.length === EXPECTED_CASE_21_OUTPUT_COUNT,
      "У изображения кейса 21 должно быть три ролика.",
    );

    const outputsByModel = new Map(record.outputs.map((output) => [output.model_id, output]));
    assert(outputsByModel.size === MODEL_ORDER.length, "У кейса 21 повторяются модели.");
    const outputs = MODEL_ORDER.map((modelId) => {
      const output = outputsByModel.get(modelId);
      assert(output, `У кейса 21 нет модели ${modelId}.`);
      assert(output.delivery === "repository-raw", `Ролик ${modelId} должен доставляться из main.`);
      validateOutput("21", output, usedVideoPaths, modelId);
      return output;
    });
    assert(
      Array.isArray(record.research_outputs) &&
        record.research_outputs.length === EXPECTED_CASE_21_RESEARCH_OUTPUT_COUNT,
      "У изображения кейса 21 должно быть четыре дополнительных research-ролика.",
    );
    const researchOutputs = record.research_outputs.map((output, outputIndex) => {
      assert(
        MODEL_ORDER.includes(output.model_id),
        `У research-ролика ${outputIndex + 1} неизвестная модель ${output.model_id}.`,
      );
      assert(
        output.delivery === "repository-raw",
        `Research-ролик ${output.model_id} должен доставляться из main.`,
      );
      assert(
        output.available === true &&
          output.accepted === false &&
          output.visual_review?.status === "fidelity-failed",
        `Research-ролик ${output.model_id} должен оставаться доступным, но отклонённым по fidelity.`,
      );
      assert(
        Number.isInteger(output.model_attempt_number) && output.model_attempt_number > 0,
        `У research-ролика ${output.model_id} нет номера попытки.`,
      );
      validateOutput("21", output, usedVideoPaths, `research ${outputIndex + 1}`);
      return output;
    });

    const flatOutputsByModel = new Map(
      manifest.outputs.map((output) => [output.model_id, output]),
    );
    assert(flatOutputsByModel.size === MODEL_ORDER.length, "В плоском списке sidecar повторяются модели.");
    MODEL_ORDER.forEach((modelId) => {
      const flatOutput = flatOutputsByModel.get(modelId);
      assert(flatOutput, `В плоском списке sidecar нет модели ${modelId}.`);
      assert(flatOutput.delivery === "repository-raw", `Плоский output ${modelId} должен ссылаться на main.`);
      const nestedOutput = outputsByModel.get(modelId);
      assert(
        JSON.stringify(flatOutput) === JSON.stringify(nestedOutput),
        `Плоский output ${modelId} не совпадает с записью статьи.`,
      );
    });
    assert(
      JSON.stringify(manifest.research_outputs) === JSON.stringify(researchOutputs),
      "Плоский список research_outputs не совпадает с записью статьи.",
    );

    const displayOutputs = [...outputs, ...researchOutputs]
      .map((output) => {
        const selection = output.selection || {};
        const variantKey = `${selection.activity || ""}:${selection.variant_id || ""}`;
        const variantLabel = CASE_21_VARIANT_LABELS[variantKey];
        assert(variantLabel, `У case 21 нет подписи варианта ${variantKey}.`);
        assert(
          Number.isInteger(output.model_attempt_number) && output.model_attempt_number > 0,
          `У case 21 / ${output.model_id} нет номера попытки.`,
        );
        return {
          ...output,
          showcaseLabel: `${variantLabel} · попытка ${output.model_attempt_number}`,
          showcaseVariant: "research",
        };
      })
      .sort((left, right) => {
        const modelDelta = MODEL_ORDER.indexOf(left.model_id) - MODEL_ORDER.indexOf(right.model_id);
        return modelDelta || left.model_attempt_number - right.model_attempt_number;
      });
    assert(
      displayOutputs.length === EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT &&
        new Set(displayOutputs.map((output) => output.video_path)).size ===
          EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT,
      "Полный case 21 должен показывать семь уникальных MP4.",
    );
    const loopExperiment = hasOwn(manifest, "loop_experiment")
      ? validateLoopExperiment(manifest.loop_experiment, usedVideoPaths)
      : null;
    const smoothExperiment = hasOwn(manifest, "smooth_experiment")
      ? validateSmoothExperiment(manifest.smooth_experiment, usedVideoPaths)
      : null;

    return [
      {
        ...article,
        case_key: makeCaseKey(manifest.ticket, article.article_slug),
        legacy_case_key: article.article_number,
        sourceTicket: manifest.ticket,
        sourceStatus: "Исследовательский кейс",
        images: [
          {
            ...record,
            image,
            outputs,
            research_outputs: researchOutputs,
            displayOutputs,
            loopExperiment,
            smoothExperiment,
            attemptSummary: {
              total: manifest.attempt_count,
              available: manifest.available_output_count,
              unavailable: manifest.attempts_without_video_count,
            },
          },
        ],
      },
    ];
  };

  const mergeArticleImages = (baseArticles, additionalArticles, case21Articles) => {
    const additionalBySlug = new Map(
      additionalArticles.map((article) => [article.article_slug, article]),
    );
    const merged = baseArticles.map((article) => {
      const additional = additionalBySlug.get(article.article_slug);
      assert(additional, `Нет дополнительных результатов для статьи ${article.article_slug}.`);
      const firstImage = {
        image: { ...article.selected_image, delivery: "site" },
        outputs: article.outputs,
        displayOutputs: article.displayOutputs,
        comparison_outputs: article.comparison_outputs,
        external_outputs: article.external_outputs,
        baseline: true,
      };
      return {
        ...article,
        sourceTicket: `${article.sourceTicket} + PROMOPAGES-9930`,
        images: [firstImage, ...additional.images],
      };
    });
    merged.push(...case21Articles);
    const canonicalOutputCount = merged.reduce(
      (articleTotal, article) =>
        articleTotal +
        article.images.reduce(
          (imageTotal, imageRecord) => imageTotal + imageRecord.outputs.length,
          0,
        ),
      0,
    );
    const canonicalVideoPaths = new Set(
      merged.flatMap((article) =>
        article.images.flatMap((imageRecord) =>
          imageRecord.outputs.map((output) => output.video_path),
        ),
      ),
    );
    assert(
      canonicalVideoPaths.size === canonicalOutputCount,
      "После объединения canonical MP4 должны быть уникальны.",
    );
    const caseKeys = new Set(merged.map((article) => article.case_key));
    assert(caseKeys.size === merged.length, "После объединения case key должны быть уникальны.");
    return merged;
  };

  const mergeArticleCollections = (historicalArticles, reviewArticles) => {
    const merged = [...historicalArticles, ...reviewArticles];
    const caseKeys = new Set();
    merged.forEach((article) => {
      assert(
        typeof article.case_key === "string" && article.case_key.trim(),
        `У статьи ${article.article_slug ?? "—"} нет collision-safe case key.`,
      );
      assert(!caseKeys.has(article.case_key), `Case key повторяется: ${article.case_key}.`);
      caseKeys.add(article.case_key);
      assert(
        Array.isArray(article.images) && article.images.length > 0,
        `У ${article.case_key} нет изображений для демо.`,
      );
    });
    return merged;
  };

  const datasetCounts = (items) => {
    const videoPaths = new Set();
    let imageCount = 0;
    let outputCount = 0;
    items.forEach((article) => {
      imageCount += article.images.length;
      article.images.forEach((record) => {
        const outputs = [
          ...record.outputs,
          ...(record.research_outputs || []),
          ...(record.loopExperiment?.outputs || []),
          ...(record.smoothExperiment?.outputs || []),
        ];
        outputCount += outputs.length;
        outputs.forEach((output) => {
          if (typeof output.video_path === "string" && output.video_path) {
            videoPaths.add(output.video_path);
          }
        });
      });
    });
    return {
      articleCount: items.length,
      imageCount,
      // Keep the existing property for the summary binding, but count logical
      // outputs: a terminal provider-filtered result is still one of the 276
      // requested model outputs even though it has no MP4.
      videoCount: outputCount,
      availableVideoCount: videoPaths.size,
      unavailableOutputCount: outputCount - videoPaths.size,
    };
  };

  const availableOutputCount = (outputs) =>
    outputs.filter(
      (output) => typeof output.video_path === "string" && output.video_path.trim(),
    ).length;

  const resolveRequestedArticleIndex = (items, requestedCase) => {
    if (!requestedCase) return -1;
    const exactIndex = items.findIndex((article) => article.case_key === requestedCase);
    if (exactIndex >= 0) return exactIndex;
    return items.findIndex(
      (article) => article.legacy_case_key === requestedCase,
    );
  };

  const resolveRequestedImageIndex = (article, requestedImageId) => {
    if (!requestedImageId) return -1;
    return article.images.findIndex(
      (record) => record.image.image_id === requestedImageId,
    );
  };

  const renderFacts = (facts) => `
    <dl class="mediaFacts">
      ${facts
        .map(
          ([label, value]) => `
            <div>
              <dt>${escapeHtml(label)}</dt>
              <dd>${escapeHtml(value)}</dd>
            </div>
          `,
        )
        .join("")}
    </dl>
  `;

  const renderSource = (article, imageRecord) => {
    const image = imageRecord.image;
    const imageUrl = asAssetUrl(image.source_path, image.delivery);
    const imageFile = image.file || image.source_path.split("/").pop();
    const caseId = asDomIdPart(article.case_key);
    const panelId = `sourcePanel-${caseId}-${image.image_id}`;
    const titleId = `sourceTitle-${caseId}-${image.image_id}`;

    return `
      <article
        class="mediaPanel sourcePanel"
        id="${panelId}"
        data-source-panel
        aria-labelledby="${titleId}"
        hidden
      >
        <a
          class="mediaStage mediaStageLink"
          style="--media-aspect: ${image.width} / ${image.height}"
          href="${escapeHtml(imageUrl)}"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Открыть исходное изображение статьи «${escapeHtml(article.title)}»"
        >
          <img
            data-original-src="${escapeHtml(imageUrl)}"
            width="${image.width}"
            height="${image.height}"
            alt="Исходное изображение к статье «${escapeHtml(article.title)}»"
            decoding="async"
            loading="lazy"
          />
        </a>
        <div class="panelIdentity">
          <div>
            <p class="panelKicker">Исходник</p>
            <h3 id="${titleId}">Оригинал</h3>
          </div>
        </div>
        ${renderFacts([
          ["Файл", imageFile],
          ["Источник", article.sourceTicket],
          ["Статус", article.sourceStatus],
          ["Позиция", image.role || "изображение статьи"],
          ["Геометрия", `${image.width}×${image.height}`],
        ])}
      </article>
    `;
  };

  const providerAuditValue = (value, fallback = "Не зафиксировано") =>
    typeof value === "string" && value.trim() ? value : fallback;

  const renderProviderAttemptAudit = (label, attempt) => `
    <li class="providerAttempt">
      <div class="providerAttemptHeader">
        <strong>${escapeHtml(label)}</strong>
        <span>${escapeHtml(attempt.status)}</span>
      </div>
      <p class="providerAttemptError">${escapeHtml(
        attempt.error || attempt.ambiguity_reason || "Provider detail не зафиксирован.",
      )}</p>
      <dl class="providerAttemptFacts">
        <div>
          <dt>Provider job</dt>
          <dd><code>${escapeHtml(providerAuditValue(attempt.provider_job_id, "Не выдан"))}</code></dd>
        </div>
        <div>
          <dt>Provider run</dt>
          <dd><code>${escapeHtml(attempt.provider_run_id)}</code></dd>
        </div>
        <div>
          <dt>Отправлено</dt>
          <dd>${escapeHtml(providerAuditValue(attempt.submitted_at || attempt.provider_submit_time))}</dd>
        </div>
        <div>
          <dt>Завершено</dt>
          <dd>${escapeHtml(providerAuditValue(attempt.completed_at || attempt.provider_end_time))}</dd>
        </div>
        ${attempt.outcome_unknown === true
          ? "<div><dt>Provider outcome</dt><dd>Unknown · provider может оставаться активным</dd></div>"
          : ""}
      </dl>
      <details class="providerAttemptTechnical">
        <summary>Техническая привязка попытки</summary>
        <dl>
          <div><dt>Run receipt</dt><dd><code>${escapeHtml(attempt.run_path)}</code></dd></div>
          <div><dt>Run SHA-256</dt><dd><code>${escapeHtml(attempt.run_sha256)}</code></dd></div>
          <div><dt>Prompt receipt</dt><dd><code>${escapeHtml(attempt.prompt_path)}</code></dd></div>
          <div><dt>Prompt SHA-256</dt><dd><code>${escapeHtml(attempt.prompt_sha256)}</code></dd></div>
          <div><dt>Request SHA-256</dt><dd><code>${escapeHtml(attempt.request_sha256)}</code></dd></div>
        </dl>
      </details>
    </li>
  `;

  const renderNormalizedInputAudit = (retry) => {
    const transform = retry.source_transform;
    const original = transform.original;
    const normalized = transform.normalized;
    const delta = transform.request_delta;
    return `
      <section class="providerFilterAudit" aria-label="Аудит нормализации provider input">
        <div class="providerFilterAuditHeader">
          <p class="panelKicker">Input audit</p>
          <h4>Исходник нормализован из-за размера больше 20 MiB</h4>
          <p>
            Prompt и модель сохранены. В provider request изменён ровно один leaf:
            ${escapeHtml(delta.json_pointer)}.
          </p>
        </div>
        ${renderFacts([
          ["Original", `${formatMiB(original.bytes)} · ${original.width}×${original.height}`],
          ["Normalized", `${formatMiB(normalized.bytes)} · ${normalized.width}×${normalized.height}`],
          ["Request delta", "1 image URL leaf"],
        ])}
        <details class="providerAttemptTechnical">
          <summary>Техническая привязка normalized input</summary>
          <dl>
            <div><dt>Original URL</dt><dd><code>${escapeHtml(original.url)}</code></dd></div>
            <div><dt>Original SHA-256</dt><dd><code>${escapeHtml(original.sha256)}</code></dd></div>
            <div><dt>Normalized URL</dt><dd><code>${escapeHtml(normalized.url)}</code></dd></div>
            <div><dt>Normalized SHA-256</dt><dd><code>${escapeHtml(normalized.sha256)}</code></dd></div>
            <div><dt>Metadata</dt><dd><code>${escapeHtml(normalized.metadata_path)}</code></dd></div>
            <div><dt>Metadata SHA-256</dt><dd><code>${escapeHtml(normalized.metadata_sha256)}</code></dd></div>
            <div><dt>Envelope</dt><dd><code>${escapeHtml(retry.envelope_path)}</code></dd></div>
            <div><dt>Envelope SHA-256</dt><dd><code>${escapeHtml(retry.envelope_sha256)}</code></dd></div>
          </dl>
        </details>
      </section>
    `;
  };

  const renderProviderFilteredModel = (
    article,
    imageRecord,
    output,
    modelIndex,
    { idPrefix, headingLevel },
  ) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    const titleId = `${idPrefix}-${asDomIdPart(article.case_key)}-${imageRecord.image.image_id}-${modelIndex + 1}`;
    const headingTag = headingLevel === 4 ? "h4" : "h3";
    const retry = output.retry;
    const primaryAttempt = retry.primary_attempt;
    const retryAttempt = retry.retry_attempt;
    const sourceAspect = `${imageRecord.image.width} / ${imageRecord.image.height}`;
    const negativePromptDetails =
      typeof output.negative_prompt === "string" && output.negative_prompt.trim()
        ? `<details class="promptDetails negativePromptDetails">
            <summary>Дословный negative prompt</summary>
            <p class="promptText" lang="en">${escapeHtml(output.negative_prompt)}</p>
          </details>`
        : "";

    return `
      <article
        class="mediaPanel modelPanel providerFilteredPanel"
        data-output-kind="provider-filtered"
        data-provider-filtered="true"
        aria-labelledby="${titleId}"
      >
        <div
          class="mediaStage providerFilteredStage"
          style="--media-aspect: ${sourceAspect}"
          role="status"
          aria-label="${escapeHtml(presentation.name)}: видео недоступно после двух provider-попыток"
        >
          <div class="providerFilteredMessage">
            <p class="providerFilteredKicker">Видео недоступно</p>
            <strong>Две попытки завершились без MP4</strong>
            <p>
              Провайдер сообщил, что результат мог быть отфильтрован. Подмена моделью
              или скрытый третий запуск не выполнялись.
            </p>
          </div>
        </div>

        <div class="panelIdentity">
          <div>
            <p class="contractWarning providerFilteredWarning">
              Terminal provider-filtered · primary + immutable retry-v1 exhausted
            </p>
            <p class="panelKicker">Модель ${String(modelIndex + 1).padStart(2, "0")}</p>
            <${headingTag} id="${titleId}">${escapeHtml(presentation.name)}</${headingTag}>
            <code class="modelId">${escapeHtml(output.model_id)}</code>
          </div>
          <strong class="modelCost providerFilteredCost">
            Недоступно
            <span>после 2 попыток</span>
          </strong>
        </div>

        ${renderFacts([
          ["Статус", output.status],
          ["Recorded status", output.recorded_status],
          ["Выбрана", "terminal retry-v1 · exhausted"],
          ["Видео", "MP4 не получен"],
        ])}

        <section class="providerFilterAudit" aria-label="Аудит двух provider-попыток">
          <div class="providerFilterAuditHeader">
            <p class="panelKicker">Provider audit</p>
            <h4>Основная попытка и retry-v1</h4>
            <p>
              Обе попытки terminal; immutable request SHA-256 совпадает. Ошибки
              сохранены дословно из provider receipts.
            </p>
          </div>
          <ol class="providerAttemptList">
            ${renderProviderAttemptAudit("Основная попытка", primaryAttempt)}
            ${renderProviderAttemptAudit("Retry-v1 · исчерпан", retryAttempt)}
          </ol>
          <dl class="providerFilterBinding">
            <div><dt>Retry namespace</dt><dd><code>${escapeHtml(retry.namespace)}</code></dd></div>
            <div><dt>Envelope</dt><dd><code>${escapeHtml(retry.envelope_path)}</code></dd></div>
            <div><dt>Immutable request SHA-256</dt><dd><code>${escapeHtml(retryAttempt.request_sha256)}</code></dd></div>
          </dl>
        </section>

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
        ${negativePromptDetails}
      </article>
    `;
  };

  const renderProviderUnavailableModel = (
    article,
    imageRecord,
    output,
    modelIndex,
    { idPrefix, headingLevel },
  ) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    const titleId = `${idPrefix}-${asDomIdPart(article.case_key)}-${imageRecord.image.image_id}-${modelIndex + 1}`;
    const headingTag = headingLevel === 4 ? "h4" : "h3";
    const retry = output.retry;
    const primaryAttempt = retry.primary_attempt;
    const retryAttempt = retry.retry_attempt;
    const sourceAspect = `${imageRecord.image.width} / ${imageRecord.image.height}`;
    const negativePromptDetails =
      typeof output.negative_prompt === "string" && output.negative_prompt.trim()
        ? `<details class="promptDetails negativePromptDetails">
            <summary>Дословный negative prompt</summary>
            <p class="promptText" lang="en">${escapeHtml(output.negative_prompt)}</p>
          </details>`
        : "";

    return `
      <article
        class="mediaPanel modelPanel providerFilteredPanel"
        data-output-kind="provider-unavailable"
        data-provider-unavailable="true"
        aria-labelledby="${titleId}"
      >
        <div
          class="mediaStage providerFilteredStage"
          style="--media-aspect: ${sourceAspect}"
          role="status"
          aria-label="${escapeHtml(presentation.name)}: основная отправка имеет неизвестный outcome, retry-v1 завершился без видео"
        >
          <div class="providerFilteredMessage">
            <p class="providerFilteredKicker">Видео недоступно</p>
            <strong>Outcome основной отправки неизвестен</strong>
            <p>
              Синхронный submit мог достичь провайдера, но его результат не был
              зафиксирован. Явный retry-v1 завершился provider-failed без MP4.
            </p>
          </div>
        </div>

        <div class="panelIdentity">
          <div>
            <p class="contractWarning providerFilteredWarning">
              Provider unavailable · primary outcome unknown + explicit retry-v1 exhausted
            </p>
            <p class="panelKicker">Модель ${String(modelIndex + 1).padStart(2, "0")}</p>
            <${headingTag} id="${titleId}">${escapeHtml(presentation.name)}</${headingTag}>
            <code class="modelId">${escapeHtml(output.model_id)}</code>
          </div>
          <strong class="modelCost providerFilteredCost">
            Недоступно
            <span>retry provider-failed</span>
          </strong>
        </div>

        ${renderFacts([
          ["Статус", output.status],
          ["Recorded status", output.recorded_status],
          ["Primary outcome", "unknown · provider может быть активен"],
          ["Выбрана", "ambiguous-submit retry-v1 · exhausted"],
          ["Видео", "MP4 не получен"],
        ])}

        <section class="providerFilterAudit" aria-label="Аудит ambiguous submit и retry-v1">
          <div class="providerFilterAuditHeader">
            <p class="panelKicker">Provider audit</p>
            <h4>Неоднозначная отправка и terminal retry-v1</h4>
            <p>
              Primary не объявлен terminal: его outcome остаётся unknown. Retry-v1
              завершён provider-failed; immutable request SHA-256 совпадает.
            </p>
          </div>
          <ol class="providerAttemptList">
            ${renderProviderAttemptAudit("Основная попытка · outcome unknown", primaryAttempt)}
            ${renderProviderAttemptAudit("Retry-v1 · provider-failed", retryAttempt)}
          </ol>
          <dl class="providerFilterBinding">
            <div><dt>Retry namespace</dt><dd><code>${escapeHtml(retry.namespace)}</code></dd></div>
            <div><dt>Envelope</dt><dd><code>${escapeHtml(retry.envelope_path)}</code></dd></div>
            <div><dt>Envelope SHA-256</dt><dd><code>${escapeHtml(retry.envelope_sha256)}</code></dd></div>
            <div><dt>Immutable request SHA-256</dt><dd><code>${escapeHtml(retryAttempt.request_sha256)}</code></dd></div>
          </dl>
        </section>

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
        ${negativePromptDetails}
      </article>
    `;
  };

  const renderNormalizedInputUnavailableModel = (
    article,
    imageRecord,
    output,
    modelIndex,
    { idPrefix, headingLevel },
  ) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    const titleId = `${idPrefix}-${asDomIdPart(article.case_key)}-${imageRecord.image.image_id}-${modelIndex + 1}`;
    const headingTag = headingLevel === 4 ? "h4" : "h3";
    const retry = output.retry;
    const primaryAttempt = retry.primary_attempt;
    const retryAttempt = retry.retry_attempt;
    const sourceAspect = `${imageRecord.image.width} / ${imageRecord.image.height}`;

    return `
      <article
        class="mediaPanel modelPanel providerFilteredPanel"
        data-output-kind="provider-unavailable"
        data-provider-unavailable="true"
        data-retry-kind="normalized-input"
        aria-labelledby="${titleId}"
      >
        <div
          class="mediaStage providerFilteredStage"
          style="--media-aspect: ${sourceAspect}"
          role="status"
          aria-label="${escapeHtml(presentation.name)}: normalized-input retry завершился без видео"
        >
          <div class="providerFilteredMessage">
            <p class="providerFilteredKicker">Видео недоступно</p>
            <strong>Normalized-input retry завершился без MP4</strong>
            <p>
              Исходник больше 20 MiB был заменён frozen page-вариантом только в
              provider request. Явный retry-v1 завершился provider-failed.
            </p>
          </div>
        </div>

        <div class="panelIdentity">
          <div>
            <p class="contractWarning providerFilteredWarning">
              Source normalized · one image URL delta · retry-v1 exhausted
            </p>
            <p class="panelKicker">Модель ${String(modelIndex + 1).padStart(2, "0")}</p>
            <${headingTag} id="${titleId}">${escapeHtml(presentation.name)}</${headingTag}>
            <code class="modelId">${escapeHtml(output.model_id)}</code>
          </div>
          <strong class="modelCost providerFilteredCost">
            Недоступно
            <span>retry provider-failed</span>
          </strong>
        </div>

        ${renderFacts([
          ["Статус", output.status],
          ["Recorded status", output.recorded_status],
          ["Выбрана", "normalized-input retry-v1 · exhausted"],
          ["Видео", "MP4 не получен"],
        ])}

        ${renderNormalizedInputAudit(retry)}

        <section class="providerFilterAudit" aria-label="Аудит primary и normalized-input retry-v1">
          <div class="providerFilterAuditHeader">
            <p class="panelKicker">Provider attempts</p>
            <h4>Primary failure и normalized-input retry-v1</h4>
            <p>Обе попытки terminal; исходный logical source сохранён.</p>
          </div>
          <ol class="providerAttemptList">
            ${renderProviderAttemptAudit("Primary · provider-failed", primaryAttempt)}
            ${renderProviderAttemptAudit("Normalized-input retry-v1 · provider-failed", retryAttempt)}
          </ol>
        </section>

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
      </article>
    `;
  };

  const renderModel = (
    article,
    imageRecord,
    output,
    modelIndex,
    {
      idPrefix = "model",
      loopPlayback = false,
      smoothExperiment = false,
      headingLevel = 3,
    } = {},
  ) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    assert(presentation, `Нет presentation для ${output.model_id}.`);
    if (output.providerFiltered === true) {
      return renderProviderFilteredModel(article, imageRecord, output, modelIndex, {
        idPrefix,
        headingLevel,
      });
    }
    if (output.providerUnavailable === true) {
      if (output.retry?.retry_kind === NORMALIZED_INPUT_RETRY_KIND) {
        return renderNormalizedInputUnavailableModel(
          article,
          imageRecord,
          output,
          modelIndex,
          { idPrefix, headingLevel },
        );
      }
      return renderProviderUnavailableModel(article, imageRecord, output, modelIndex, {
        idPrefix,
        headingLevel,
      });
    }
    const titleId = `${idPrefix}-${asDomIdPart(article.case_key)}-${imageRecord.image.image_id}-${modelIndex + 1}`;
    const videoUrl = asAssetUrl(output.video_path, output.delivery);
    const promptLabel = output.showcaseLabel
      ? `<p class="promptLabel">${escapeHtml(output.showcaseLabel)}</p>`
      : "";
    const isFeaturedWinner = smoothExperiment && output.isFeaturedWinner === true;
    const winnerBadge = isFeaturedWinner
      ? '<p class="winnerBadge">Визуальный победитель</p>'
      : "";
    const negativePromptDetails =
      typeof output.negative_prompt === "string" && output.negative_prompt.trim()
        ? `<details class="promptDetails negativePromptDetails">
            <summary>Дословный negative prompt</summary>
            <p class="promptText" lang="en">${escapeHtml(output.negative_prompt)}</p>
          </details>`
        : "";
    const variant = output.showcaseVariant || "canonical";
    const accessibleVariant = output.showcaseLabel ? ` · ${output.showcaseLabel}` : "";
    const accessibleWinner = isFeaturedWinner ? " · визуальный победитель" : "";
    const contractWarning =
      output.status === "verification-failed"
        ? '<p class="contractWarning">Raw output · media contract warning</p>'
        : "";
    const normalizedInputWarning = output.normalizedInputRetry
      ? '<p class="contractWarning providerFilteredWarning">Source normalized · original больше 20 MiB · prompt/model сохранены</p>'
      : "";
    const fidelityWarning =
      !smoothExperiment && output.visual_review?.status === "fidelity-failed"
        ? `<p class="contractWarning fidelityWarning"><strong>Visual review · fidelity failed.</strong> ${escapeHtml(output.visual_review.summary)}</p>`
        : "";
    const seamReview = output.loop_closure?.seam_review;
    const seamLabel = seamReview ? LOOP_SEAM_PRESENTATION[seamReview.status] : null;
    const loopStatus = loopPlayback
      ? `
        <p class="loopMechanism">
          <strong>API loop-closure.</strong> Один исходник передан как first и last frame;
          native loop-параметр не использовался.
        </p>
        <p class="loopSeamStatus" data-seam-status="${escapeHtml(seamReview.status)}">
          <strong>${escapeHtml(seamLabel)}.</strong> ${escapeHtml(seamReview.summary)}
        </p>
      `
      : "";
    const motionProxy = output.motionProxy;
    const smoothStatus = smoothExperiment
      ? `
        <p
          class="smoothProxyStatus"
          data-motion-proxy-status="${escapeHtml(motionProxy.status)}"
        >
          <strong>Motion proxy · ${escapeHtml(motionProxy.status)}.</strong>
          Движение найдено в ${motionProxy.regions_with_detected_motion} из
          ${motionProxy.requested_region_count} заданных зон; proxy rank
          ${motionProxy.rank} из ${motionProxy.rankScale}.
        </p>
        <p
          class="smoothVisualStatus"
          data-visual-review-status="${escapeHtml(output.visual_review.status)}"
        >
          <strong>Visual review · ${escapeHtml(output.visual_review.status)}.</strong>
          ${escapeHtml(output.visual_review.summary)}
        </p>
      `
      : "";
    const panelKind = loopPlayback
      ? "Loop-вариант"
      : smoothExperiment
        ? "Smooth-вариант"
      : output.showcaseLabel
        ? "Вариант"
        : "Модель";
    const headingTag = headingLevel === 4 ? "h4" : "h3";
    const playbackAttributes = loopPlayback
      ? `${prefersReducedMotion ? "" : " loop"} muted data-loop-output`
      : smoothExperiment
        ? "muted"
        : "";

    return `
      <article
        class="mediaPanel modelPanel"
        data-output-kind="${escapeHtml(variant)}"
        data-featured-winner="${isFeaturedWinner ? "true" : "false"}"
        aria-labelledby="${titleId}"
      >
        <div
          class="mediaStage"
          style="--media-aspect: ${output.media.width} / ${output.media.height}"
          data-media-stage
          data-model-id="${escapeHtml(output.model_id)}"
        >
          <video
            src="${escapeHtml(videoUrl)}"
            width="${output.media.width}"
            height="${output.media.height}"
            controls
            playsinline
            preload="metadata"
            ${playbackAttributes}
            aria-label="${escapeHtml(presentation.name + accessibleVariant + accessibleWinner)}: результат для статьи «${escapeHtml(article.title)}»"
          >
            Ваш браузер не поддерживает MP4-видео.
          </video>
          <p class="mediaError" data-media-error hidden>
            Ролик не загрузился. Проверьте путь к MP4.
          </p>
        </div>

        <div class="panelIdentity">
          <div>
            ${winnerBadge}
            ${promptLabel}
            ${contractWarning}
            ${normalizedInputWarning}
            ${fidelityWarning}
            ${smoothStatus}
            ${loopStatus}
            <p class="panelKicker">${panelKind} ${String(modelIndex + 1).padStart(2, "0")}</p>
            <${headingTag} id="${titleId}">${escapeHtml(presentation.name)}</${headingTag}>
            <code class="modelId">${escapeHtml(output.model_id)}</code>
          </div>
          <strong class="modelCost">
            ${escapeHtml(presentation.cost)}
            <span>за ролик</span>
          </strong>
        </div>

        ${renderFacts([
          ["Статус", output.status || "готово"],
          ["Длительность", formatDuration(output.media.duration_seconds)],
          ["Геометрия", `${output.media.width}×${output.media.height}`],
          ["Размер", formatMiB(output.media.bytes)],
          ...(output.route_label
            ? [["Маршрут", output.route_label]]
            : []),
          ...(loopPlayback
            ? [
                ["API-замыкание", "same-source first + last"],
                ["Шов", seamLabel],
              ]
            : []),
          ...(smoothExperiment
            ? [
                ["Conditioning", "first frame only"],
                ["Повтор", "нет · остановка в конце"],
                [
                  "Motion proxy",
                  `${motionProxy.regions_with_detected_motion}/${motionProxy.requested_region_count}`,
                ],
                ["Visual review", output.visual_review.status],
              ]
            : []),
        ])}

        ${output.normalizedInputRetry ? renderNormalizedInputAudit(output.retry) : ""}

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
        ${negativePromptDetails}
      </article>
    `;
  };

  const renderLoopAttemptHistory = (loopExperiment) => {
    const failures = loopExperiment.failedAttempts;
    const summary = failures.length
      ? `История неудач · ${failures.length} без MP4 из ${loopExperiment.attempt_count}`
      : `История неудач · все ${loopExperiment.attempt_count} запусков вернули MP4`;
    const content = failures.length
      ? `<ol class="loopAttemptList">
          ${failures
            .map((attempt) => {
              const variant = attempt.variant_id || attempt.sample_id || "без variant_id";
              const error = attempt.error || "Провайдер не вернул доступный MP4.";
              return `<li>
                <p>
                  <strong>Попытка ${attempt.experimentAttemptNumber}</strong>
                  <span>${escapeHtml(variant)} · ${escapeHtml(attempt.status || "unknown")}</span>
                </p>
                <p>${escapeHtml(error)}</p>
              </li>`;
            })
            .join("")}
        </ol>`
      : '<p class="loopAttemptEmpty">Неудачных запусков в этой серии нет.</p>';

    return `
      <details class="loopAttemptHistory">
        <summary>${escapeHtml(summary)}</summary>
        ${content}
      </details>
    `;
  };

  const renderLoopSection = (article, imageRecord) => {
    const loopExperiment = imageRecord.loopExperiment;
    if (!loopExperiment) return "";
    const outputCount = loopExperiment.outputs.length;
    const cap = numberFormatter.format(loopExperiment.cost.operator_budget_cap_usd);
    const outputSummary = outputCount
      ? `Получено ${outputCount} MP4 из ${loopExperiment.attempt_count} запусков.`
      : `Ни один из ${loopExperiment.attempt_count} запусков не вернул MP4.`;
    const playbackNote = prefersReducedMotion
      ? "Автоповтор отключён системной настройкой reduced motion."
      : "Браузер повторяет MP4 для проверки шва.";

    return `
      <section class="loopExperimentSection" aria-labelledby="loopExperimentTitle">
        <header class="loopExperimentHeader">
          <p class="loopExperimentKicker">Wan 2.7 · контрольная исследовательская серия</p>
          <h3 id="loopExperimentTitle">API loop-closure: одинаковый first и last frame</h3>
          <p>
            Это контроль для сравнения с non-loop вариантами: endpoint-conditioning,
            а не native loop-параметр и не canonical Lite runtime.
            ${escapeHtml(playbackNote)} Бесшовность подтверждает только статус seam review
            на каждой карточке. ${escapeHtml(outputSummary)} Лимит серии — $${escapeHtml(cap)}.
          </p>
        </header>
        <div class="loopExperimentActions">
          <button
            class="controlButton strong"
            type="button"
            data-play-loop
            data-video-group-control="loop"
            data-play-label="Воспроизвести ${outputCount} loop-видео"
            data-pause-label="Пауза loop-видео"
            aria-pressed="false"
            aria-describedby="navigatorStatus"
            disabled
            ${outputCount ? "" : 'aria-disabled="true"'}
          >
            ${outputCount ? `Воспроизвести ${outputCount} loop-видео` : "Loop-видео недоступны"}
          </button>
        </div>
        ${
          outputCount
            ? `<div class="modelGrid loopGrid" data-video-group="loop">
                ${loopExperiment.outputs
                  .map((output, outputIndex) =>
                    renderModel(article, imageRecord, output, outputIndex, {
                      idPrefix: "loopModel",
                      loopPlayback: true,
                      headingLevel: 4,
                    }),
                  )
                  .join("")}
              </div>`
            : '<p class="loopEmptyState">Видео нет; причины сохранены в истории запусков.</p>'
        }
        ${renderLoopAttemptHistory(loopExperiment)}
      </section>
    `;
  };

  const renderSmoothFeaturedReview = (featuredReview) => {
    const evidence = featuredReview.evidence;
    return `
      <aside class="smoothWinnerCallout" aria-labelledby="smoothWinnerTitle">
        <div class="smoothWinnerLead">
          <p class="smoothWinnerKicker">${escapeHtml(featuredReview.label)} · Staggered retry</p>
          <h4 id="smoothWinnerTitle">Почему этот вариант выглядит сильнее</h4>
          <p>${escapeHtml(featuredReview.summary)}</p>
          <dl class="smoothWinnerEvidence" aria-label="Данные motion proxy для победителя">
            <div>
              <dt>Motion coverage</dt>
              <dd>${evidence.regions_with_detected_motion}/${evidence.requested_region_count}</dd>
            </div>
            <div>
              <dt>Abrupt transitions</dt>
              <dd>${evidence.abrupt_transition_count}</dd>
            </div>
            <div>
              <dt>Motion spikes</dt>
              <dd>${evidence.motion_energy_spike_count}</dd>
            </div>
            <div>
              <dt>Proxy rank</dt>
              <dd>${evidence.proxy_rank}/${evidence.proxy_rank_scale}</dd>
            </div>
          </dl>
          <p class="smoothWinnerEvidenceNote">
            Победитель выбран визуально; proxy rank приведён как диагностика, а не
            как основание выбора.
          </p>
        </div>
        <div class="smoothWinnerMethod">
          <p class="smoothWinnerMethodTitle">Практики постановки движения</p>
          <ol class="smoothWinnerPractices">
            ${featuredReview.practices
              .map(
                (practice) => `<li>
                  <strong>${escapeHtml(practice.title)}</strong>
                  <span>${escapeHtml(practice.description)}</span>
                </li>`,
              )
              .join("")}
          </ol>
          <p class="smoothWinnerDistinction">
            <strong>Ключевое отличие prompt.</strong>
            ${escapeHtml(featuredReview.prompt_distinction)}
          </p>
        </div>
      </aside>
    `;
  };

  const renderSmoothSection = (article, imageRecord) => {
    const smoothExperiment = imageRecord.smoothExperiment;
    if (!smoothExperiment) return "";
    const outputCount = smoothExperiment.outputs.length;
    const cap = numberFormatter.format(smoothExperiment.cost.operator_budget_cap_usd);
    const availableAttemptCount =
      smoothExperiment.available_attempt_count ?? outputCount;
    const outputSummary =
      `Получено ${availableAttemptCount} MP4 из ${smoothExperiment.attempt_count} запусков; ` +
      `для демо выбрано ${outputCount}.`;

    return `
      <section class="smoothExperimentSection" aria-labelledby="smoothExperimentTitle">
        <header class="smoothExperimentHeader">
          <p class="smoothExperimentKicker">Wan 2.7 · smooth motion · first-frame only</p>
          <h3 id="smoothExperimentTitle">Точечная анимация без зацикливания</h3>
          <p>
            Это canonical Lite runtime с одним first frame: last frame и loop-параметр
            не передавались. Каждый ролик останавливается в финальном кадре. Motion proxy
            и visual review на карточках дословно взяты из манифеста и сами по себе не
            означают human acceptance. ${escapeHtml(outputSummary)} Лимит серии —
            $${escapeHtml(cap)}.
          </p>
        </header>
        ${renderSmoothFeaturedReview(smoothExperiment.featuredReview)}
        <div class="smoothExperimentActions">
          <button
            class="controlButton strong"
            type="button"
            data-play-smooth
            data-video-group-control="smooth"
            data-play-label="Воспроизвести ${outputCount} smooth-видео"
            data-pause-label="Пауза smooth-видео"
            aria-pressed="false"
            aria-describedby="navigatorStatus"
            disabled
          >
            Воспроизвести ${outputCount} smooth-видео
          </button>
        </div>
        <div class="modelGrid smoothGrid" data-video-group="smooth">
          ${smoothExperiment.outputs
            .map((output, outputIndex) =>
              renderModel(article, imageRecord, output, outputIndex, {
                idPrefix: "smoothModel",
                loopPlayback: false,
                smoothExperiment: true,
                headingLevel: 4,
              }),
            )
            .join("")}
        </div>
      </section>
    `;
  };

  let articles = [];
  let activeIndex = 0;
  let activeImageIndex = 0;
  let renderSequence = 0;
  const rememberedImageByArticle = new Map();

  const detachCurrentVideos = () => {
    elements.caseViewport.querySelectorAll("video").forEach((video) => {
      video.pause();
      video.removeAttribute("src");
      video.load();
    });
  };

  const updateUrl = (caseKey, imageId) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("case", caseKey);
      url.searchParams.set("image", imageId);
      window.history.replaceState(null, "", url);
    } catch {
      // The comparison remains usable when history is unavailable (for example file://).
    }
  };

  const monitorSelectedVideos = (article, imageRecord, sequence) => {
    const allVideos = [...elements.caseViewport.querySelectorAll("video")];
    const playbackGroups = [
      {
        name: "основная серия",
        videos: [
          ...elements.caseViewport.querySelectorAll(
            '[data-video-group="primary"] video',
          ),
        ],
        button: elements.caseViewport.querySelector("[data-play-all]"),
      },
      {
        name: "loop-серия",
        videos: [
          ...elements.caseViewport.querySelectorAll('[data-video-group="loop"] video'),
        ],
        button: elements.caseViewport.querySelector("[data-play-loop]"),
      },
      {
        name: "smooth-серия",
        videos: [
          ...elements.caseViewport.querySelectorAll('[data-video-group="smooth"] video'),
        ],
        button: elements.caseViewport.querySelector("[data-play-smooth]"),
      },
    ].filter((group) => group.button && group.videos.length > 0);
    const sourceToggle = elements.caseViewport.querySelector("[data-source-toggle]");
    const sourcePanel = elements.caseViewport.querySelector("[data-source-panel]");
    const ready = new Set();
    const failed = new Set();
    const mutedBeforeCoordinatedPlayback = new Map();
    let coordinatedPlaybackActive = false;

    const restoreCoordinatedMuteState = () => {
      if (!coordinatedPlaybackActive) return;
      allVideos.forEach((video) => {
        if (mutedBeforeCoordinatedPlayback.has(video)) {
          video.muted = mutedBeforeCoordinatedPlayback.get(video);
        }
      });
      mutedBeforeCoordinatedPlayback.clear();
      coordinatedPlaybackActive = false;
    };

    const muteCoordinatedPlayback = (videos) => {
      restoreCoordinatedMuteState();
      videos.forEach((video) => {
        mutedBeforeCoordinatedPlayback.set(video, video.muted);
        video.muted = true;
      });
      coordinatedPlaybackActive = true;
    };

    const setPlaybackState = () => {
      if (sequence !== renderSequence) return;
      const anyPlaying = allVideos.some((video) => !video.paused && !video.ended);
      if (!anyPlaying) restoreCoordinatedMuteState();
      playbackGroups.forEach((group) => {
        const groupPlaying = group.videos.some(
          (video) => !video.paused && !video.ended,
        );
        group.button.setAttribute("aria-pressed", String(groupPlaying));
        group.button.textContent = groupPlaying
          ? group.button.dataset.pauseLabel
          : group.button.dataset.playLabel;
      });
    };

    const pauseAll = () => {
      allVideos.forEach((video) => video.pause());
      restoreCoordinatedMuteState();
      setPlaybackState();
    };

    const playGroup = async (group) => {
      const { button, videos } = group;
      const videoCount = videos.length;
      if (button.disabled) return;

      if (videos.some((video) => !video.paused && !video.ended)) {
        pauseAll();
        elements.navigatorStatus.textContent =
          `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: ${group.name} на паузе.`;
        return;
      }

      pauseAll();
      button.disabled = true;
      elements.navigatorStatus.textContent =
        `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: запускаем ${videoCount} видео — ${group.name}…`;
      videos.forEach((video) => {
        video.currentTime = 0;
      });
      // A coordinated comparison is visual: prevent provider audio tracks from overlapping.
      muteCoordinatedPlayback(videos);
      // Keep all play() calls in the original click gesture for consistent browser behavior.
      const results = await Promise.allSettled(videos.map((video) => video.play()));
      if (sequence !== renderSequence) return;

      button.disabled = false;
      if (results.some((result) => result.status === "rejected")) {
        pauseAll();
        elements.navigatorStatus.textContent =
          `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: браузер не разрешил воспроизвести группу «${group.name}».`;
        return;
      }

      setPlaybackState();
      elements.navigatorStatus.textContent =
        `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: ${videoCount} видео группы «${group.name}» запущены одновременно без звука.`;
    };

    const announce = () => {
      if (sequence !== renderSequence) return;

      const complete = ready.size + failed.size === allVideos.length;
      elements.caseViewport.setAttribute("aria-busy", String(!complete));
      playbackGroups.forEach((group) => {
        const groupComplete = group.videos.every(
          (video) => ready.has(video) || failed.has(video),
        );
        const groupFailed = group.videos.some((video) => failed.has(video));
        group.button.disabled = !groupComplete || groupFailed;
      });

      if (failed.size > 0) {
        elements.navigatorStatus.textContent = `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: загружено ${ready.size} из ${allVideos.length}, ошибок — ${failed.size}.`;
      } else if (ready.size === allVideos.length) {
        elements.navigatorStatus.textContent =
          `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: ${allVideos.length} видео подключены. Серии запускаются отдельно.`;
      } else {
        elements.navigatorStatus.textContent =
          `${articleIdentityLabel(article)}, изображение ${imageRecord.image.image_id}: загружаем метаданные · ${ready.size} из ${allVideos.length}.`;
      }
    };

    allVideos.forEach((video) => {
      const markReady = () => {
        if (sequence !== renderSequence || failed.has(video)) return;
        ready.add(video);
        announce();
      };

      if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        markReady();
      } else {
        video.addEventListener("loadedmetadata", markReady, { once: true });
      }

      video.addEventListener(
        "error",
        () => {
          if (sequence !== renderSequence) return;
          failed.add(video);
          ready.delete(video);
          const stage = video.closest("[data-media-stage]");
          const error = stage?.querySelector("[data-media-error]");
          if (error) error.hidden = false;
          announce();
        },
        { once: true },
      );

      ["play", "pause", "ended"].forEach((eventName) => {
        video.addEventListener(eventName, setPlaybackState);
      });
    });

    playbackGroups.forEach((group) => {
      group.button.addEventListener("click", () => playGroup(group));
    });
    sourceToggle?.addEventListener("click", () => {
      if (!sourcePanel) return;
      const shouldShow = sourcePanel.hidden;
      const originalImage = sourcePanel.querySelector("[data-original-src]");

      if (shouldShow && originalImage && !originalImage.hasAttribute("src")) {
        originalImage.setAttribute("src", originalImage.dataset.originalSrc);
      }

      sourcePanel.hidden = !shouldShow;
      sourceToggle.setAttribute("aria-expanded", String(shouldShow));
      sourceToggle.textContent = shouldShow ? "Скрыть оригинал" : "Показать оригинал";
    });

    announce();
  };

  const renderSelection = () => {
    const article = articles[activeIndex];
    const imageRecord = article.images[activeImageIndex];
    const sequence = ++renderSequence;
    const displayOutputs = imageRecord.displayOutputs || imageRecord.outputs;
    const availablePrimaryVideoCount = availableOutputCount(displayOutputs);
    const gridClass = displayOutputs.length > MODEL_ORDER.length ? " hasExperiment" : "";
    const multiRowClass = displayOutputs.length >= 6 ? " multiRow" : "";
    const modelCountClass = displayOutputs.length === 2 ? " twoModels" : "";
    const researchSummary = imageRecord.attemptSummary
      ? `<p class="researchSummary"><strong>Полный журнал кейса 21.</strong> Получено ${imageRecord.attemptSummary.available} MP4 из ${imageRecord.attemptSummary.total} запусков; ${imageRecord.attemptSummary.unavailable} запуска завершились без видео. Все семь результатов имеют статус fidelity failed.</p>`
      : "";
    const loopSection = renderLoopSection(article, imageRecord);
    const smoothSection = renderSmoothSection(article, imageRecord);

    detachCurrentVideos();
    elements.currentNumber.textContent = String(activeIndex + 1).padStart(2, "0");
    elements.totalNumber.textContent = String(articles.length);
    elements.caseTitle.textContent = article.title;
    elements.caseDatasetMeta.textContent =
      `Источник · ${article.sourceTicket} · Локальный № ${article.article_number} · Статус · ${article.sourceStatus}`;
    elements.caseSelect.value = article.case_key;
    elements.previousCase.disabled = activeIndex === 0;
    elements.nextCase.disabled = activeIndex === articles.length - 1;
    elements.currentImageNumber.textContent = String(activeImageIndex + 1);
    elements.totalImageNumber.textContent = String(article.images.length);
    elements.imageSelect.value = imageRecord.image.image_id;
    elements.previousImage.disabled = activeImageIndex === 0;
    elements.nextImage.disabled = activeImageIndex === article.images.length - 1;
    elements.caseViewport.setAttribute("aria-busy", "true");
    elements.caseViewport.setAttribute("data-case-key", article.case_key);
    elements.caseViewport.setAttribute("data-source-ticket", article.sourceTicket);
    elements.caseViewport.setAttribute("data-source-status", article.sourceStatus);
    elements.caseViewport.innerHTML = `
      <div class="comparisonWorkspace">
        <div class="comparisonActions" aria-label="Управление сравнением">
          <button
            class="controlButton strong"
            type="button"
            data-play-all
            data-video-group-control="primary"
            data-play-label="Воспроизвести ${availablePrimaryVideoCount} доступных"
            data-pause-label="Пауза основных"
            aria-pressed="false"
            aria-describedby="navigatorStatus"
            disabled
          >
            Воспроизвести ${availablePrimaryVideoCount} доступных
          </button>
          <button
            class="controlButton"
            type="button"
            data-source-toggle
            aria-expanded="false"
            aria-controls="sourcePanel-${asDomIdPart(article.case_key)}-${imageRecord.image.image_id}"
          >
            Показать оригинал
          </button>
        </div>
        ${renderSource(article, imageRecord)}
        ${researchSummary}
        <div
          class="modelGrid${modelCountClass}${gridClass}${multiRowClass}"
          data-video-group="primary"
        >
          ${displayOutputs
            .map((output, modelIndex) => renderModel(article, imageRecord, output, modelIndex))
            .join("")}
        </div>
        ${loopSection}
        ${smoothSection}
      </div>
    `;

    rememberedImageByArticle.set(article.case_key, activeImageIndex);
    updateUrl(article.case_key, imageRecord.image.image_id);
    monitorSelectedVideos(article, imageRecord, sequence);
  };

  const renderImage = (index) => {
    const article = articles[activeIndex];
    activeImageIndex = Math.min(Math.max(index, 0), article.images.length - 1);
    renderSelection();
  };

  const renderCase = (index, requestedImageId = null) => {
    activeIndex = Math.min(Math.max(index, 0), articles.length - 1);
    const article = articles[activeIndex];
    elements.imageSelect.replaceChildren(
      ...article.images.map((record, imageIndex) => {
        const role = record.image.role === "cover" ? "обложка" : "в статье";
        return new Option(
          `${String(imageIndex + 1).padStart(2, "0")} · ${record.image.file} · ${role}`,
          record.image.image_id,
        );
      }),
    );
    elements.imageSelect.disabled = false;

    const requestedIndex = resolveRequestedImageIndex(article, requestedImageId);
    const rememberedIndex = rememberedImageByArticle.get(article.case_key) ?? 0;
    activeImageIndex = requestedIndex >= 0 ? requestedIndex : rememberedIndex;
    renderSelection();
  };

  const showError = (error) => {
    detachCurrentVideos();
    elements.caseViewport.innerHTML = "";
    elements.caseViewport.setAttribute("aria-busy", "false");
    elements.datasetError.hidden = false;
    elements.datasetErrorText.textContent = `${error.message} Откройте демо через локальный сервер и обновите страницу.`;
    elements.caseTitle.textContent = "Данные недоступны";
    elements.navigatorStatus.textContent = "Сравнение не загружено.";
  };

  const initialise = async () => {
    try {
      const [baseResponse, additionalResponse, case21Response, reviewResponse] = await Promise.all([
        fetch(BASE_MANIFEST_PATH, { cache: "no-store" }),
        fetch(ADDITIONAL_MANIFEST_PATH, { cache: "no-store" }),
        fetch(CASE_21_MANIFEST_PATH, { cache: "no-store" }),
        fetch(PROMOPAGES_10060_MANIFEST_PATH, { cache: "no-store" }),
      ]);
      if (!baseResponse.ok) {
        throw new Error(`Базовый манифест вернул HTTP ${baseResponse.status}.`);
      }
      if (!additionalResponse.ok) {
        throw new Error(
          `Манифест PROMOPAGES-9930 вернул HTTP ${additionalResponse.status}.`,
        );
      }
      if (!case21Response.ok) {
        throw new Error(`Манифест кейса 21 вернул HTTP ${case21Response.status}.`);
      }
      if (!reviewResponse.ok && reviewResponse.status !== 404) {
        throw new Error(
          `Манифест PROMOPAGES-10060 вернул HTTP ${reviewResponse.status}.`,
        );
      }

      const [baseManifest, additionalManifest, case21Manifest] = await Promise.all([
        baseResponse.json(),
        additionalResponse.json(),
        case21Response.json(),
      ]);
      const reviewManifest = reviewResponse.ok ? await reviewResponse.json() : null;
      const baseArticles = validateBaseManifest(baseManifest);
      const additionalArticles = validateAdditionalManifest(
        additionalManifest,
        baseArticles,
      );
      const case21Articles = validateCase21Manifest(
        case21Manifest,
        baseArticles,
        additionalArticles,
      );
      const historicalArticles = mergeArticleImages(
        baseArticles,
        additionalArticles,
        case21Articles,
      );
      const reviewDataset = reviewManifest
        ? validatePromopages10060Manifest(reviewManifest, historicalArticles)
        : { articles: [], unavailableArticles: [] };
      articles = mergeArticleCollections(historicalArticles, reviewDataset.articles);
      const counts = datasetCounts(articles);
      elements.articleCountSummary.textContent = String(counts.articleCount);
      elements.imageCountSummary.textContent = String(counts.imageCount);
      elements.videoCountSummary.textContent = String(counts.videoCount);
      elements.datasetSourceStatus.textContent = reviewManifest
        ? `PROMOPAGES-10060 · ${reviewDataset.articles.length} статей / ${reviewManifest.image_count} изображений / ${reviewManifest.expected_outputs} результатов · MP4 ${reviewManifest.expected_outputs - reviewDataset.unavailableOutputCount} · provider-filtered ${reviewDataset.filteredOutputCount} · provider-unavailable ${reviewDataset.providerUnavailableOutputCount} · недоступно статей ${reviewDataset.unavailableArticles.length}`
        : "PROMOPAGES-10060 · sidecar ещё не опубликован; показана историческая выборка";
      elements.caseSelect.replaceChildren(
        ...articles.map(
          (article) =>
            new Option(
              `${article.sourceTicket} · ${article.article_number} · ${article.title}`,
              article.case_key,
            ),
        ),
      );
      elements.caseSelect.disabled = false;
      elements.previousCase.disabled = false;
      elements.nextCase.disabled = false;

      const requestedCase = new URL(window.location.href).searchParams.get("case");
      const requestedImage = new URL(window.location.href).searchParams.get("image");
      const requestedIndex = resolveRequestedArticleIndex(articles, requestedCase);
      renderCase(requestedIndex >= 0 ? requestedIndex : 0, requestedImage);
    } catch (error) {
      showError(error instanceof Error ? error : new Error("Неизвестная ошибка данных."));
    }
  };

  elements.previousCase.addEventListener("click", () => renderCase(activeIndex - 1));
  elements.nextCase.addEventListener("click", () => renderCase(activeIndex + 1));
  elements.previousImage.addEventListener("click", () => renderImage(activeImageIndex - 1));
  elements.nextImage.addEventListener("click", () => renderImage(activeImageIndex + 1));
  elements.caseSelect.addEventListener("change", () => {
    const selectedIndex = articles.findIndex(
      (article) => article.case_key === elements.caseSelect.value,
    );
    if (selectedIndex >= 0) renderCase(selectedIndex);
  });
  elements.imageSelect.addEventListener("change", () => {
    const article = articles[activeIndex];
    const selectedIndex = article.images.findIndex(
      (record) => record.image.image_id === elements.imageSelect.value,
    );
    if (selectedIndex >= 0) renderImage(selectedIndex);
  });

  initialise();
})();
