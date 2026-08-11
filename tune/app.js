(() => {
  "use strict";

  const MANIFEST_URL = "../clipmaker-lite-test/tune-manifest.json";
  const RAW_REPOSITORY_BASE =
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/main/";
  const REVIEW_STORAGE_PREFIX = "alice-live:tune-review:v1:";
  const REVIEW_OUTCOMES = Object.freeze(["helped", "same-or-unclear", "worse"]);

  const MODEL_LABELS = Object.freeze({
    "alibaba/wan-2.2": "Wan 2.2",
    "alibaba/wan-2.7": "Wan 2.7",
    "google/veo-3.1-lite": "Veo 3.1 Lite",
  });

  const CATEGORY_LABELS = Object.freeze({
    source_identity_graphic_continuity: "Целостность источника",
    wrong_action_or_physics: "Действие / физика",
    camera_shot_tempo: "Камера / темп",
    insufficient_motion: "Недостаточно движения",
    optical_accent: "Оптический акцент",
    no_feedback: "Нет комментария",
  });

  const CONTENT_CLASS_LABELS = Object.freeze({
    ui_chart: "UI / chart",
    graphic: "Графика",
    product: "Продукт",
    people: "Люди",
    architecture: "Архитектура",
    landscape: "Среда",
  });

  const MODE_LABELS = Object.freeze({
    i2v: "Eliza I2V",
    "eliza-i2v": "Eliza I2V",
    "deterministic-compositor": "Deterministic compositor",
    "deterministic-compositor-fallback": "Deterministic fallback",
    "image-to-video": "Image-to-video",
    "camera-only": "Camera-only",
  });

  const RATING_LABELS = Object.freeze({
    regenerate: "Перегенерация",
    blank: "Пустая оценка",
  });

  const INTENT_LABELS = Object.freeze({
    editorial_meaning: "Редакционный смысл",
    initial_state: "Начальное состояние",
    motion_owner: "Владелец движения",
    primary_action: "Основное действие",
    terminal_state: "Конечное состояние",
    geometry_invariant: "Геометрия",
    identity_invariant: "Идентичность",
    semantic_invariant: "Смысловой инвариант",
    feasibility_assessment: "Feasibility gate",
    rendering_strategy: "Стратегия",
  });

  const INTENT_ORDER = Object.keys(INTENT_LABELS);
  const formatter = new Intl.NumberFormat("ru-RU");

  function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function cleanText(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function firstText(...values) {
    for (const value of values) {
      const normalized = cleanText(value);
      if (normalized) return normalized;
    }
    return "";
  }

  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function asObject(value) {
    return isRecord(value) ? value : {};
  }

  function toRecordArray(value) {
    if (Array.isArray(value)) return value.filter(isRecord);
    if (!isRecord(value)) return [];
    return Object.entries(value)
      .filter(([, item]) => isRecord(item))
      .map(([key, item]) => ({ ...item, model_id: item.model_id || key }));
  }

  function textList(value) {
    if (Array.isArray(value)) {
      return value.map(cleanText).filter(Boolean);
    }
    if (typeof value === "string" && value.trim()) return [value.trim()];
    if (!isRecord(value)) return [];

    const nestedComments = Array.isArray(value.comments) ? value.comments : [value.comments];
    const candidates = [value.comment, value.summary, value.text, ...nestedComments];
    return candidates.map(cleanText).filter(Boolean);
  }

  function collectCases(raw) {
    if (Array.isArray(raw.cases)) return raw.cases.filter(isRecord);
    if (Array.isArray(raw.items)) return raw.items.filter(isRecord);
    if (!Array.isArray(raw.articles)) return [];

    const cases = [];
    for (const article of raw.articles.filter(isRecord)) {
      for (const image of toRecordArray(article.images)) {
        cases.push({
          ...article,
          ...image,
          source: image.source || image.image,
          targets: image.targets || image.outputs,
        });
      }
    }
    return cases;
  }

  function normalizeRatingState(rawState, rawRating) {
    const state = firstText(rawState).toLowerCase();
    const rating = firstText(rawRating).toLowerCase();
    if (state === "regenerate" || state.includes("перегенер")) return "regenerate";
    if (state === "blank" || state === "empty") return "blank";
    if (!state && !rating) return "blank";
    if (rating.includes("перегенер")) return "regenerate";
    return state || rating || "unclassified";
  }

  function normalizeMode(target, tuned, planning) {
    const direct = firstText(
      tuned.execution_mode,
      tuned.mode,
      target.execution_mode,
      target.mode,
    );
    if (direct) return direct;

    const strategy = firstText(
      asObject(planning.structured_intent).rendering_strategy,
      planning.rendering_strategy,
    );
    return strategy === "deterministic-compositor" ? strategy : strategy ? "i2v" : "unknown";
  }

  function normalizeProviderAttempt(value) {
    const attempt = asObject(value);
    const promptEvaluated =
      typeof attempt.prompt_evaluated === "boolean"
        ? attempt.prompt_evaluated
        : typeof attempt.promptEvaluated === "boolean"
          ? attempt.promptEvaluated
          : null;
    return {
      status: firstText(attempt.status),
      promptEvaluated,
      runPath: firstText(attempt.run_path, attempt.runPath),
      runSha256: firstText(attempt.run_sha256, attempt.runSha256),
      providerJobId: firstText(attempt.provider_job_id, attempt.providerJobId),
      error: firstText(attempt.error, attempt.terminal_error),
    };
  }

  function actualVideoMethod(videoValue, executionMode = "") {
    const video = asObject(videoValue);
    const explicit = firstText(video.method);
    if (explicit) return explicit;
    if (executionMode === "deterministic-compositor") return executionMode;
    if (executionMode === "i2v") return "eliza-i2v";
    return executionMode || "unknown";
  }

  function inferPromptEvaluated(method, explicitValue) {
    if (typeof explicitValue === "boolean") return explicitValue;
    if (method === "eliza-i2v") return true;
    if (
      method === "deterministic-compositor" ||
      method === "deterministic-compositor-fallback"
    ) {
      return false;
    }
    return null;
  }

  function normalizeTunedVideo(tunedValue, executionMode = "") {
    const tuned = asObject(tunedValue);
    const videoValue = tuned.video;
    const video = asObject(videoValue);
    const qaValue =
      tuned.qa ?? tuned.video_qa ?? tuned.contract_check ?? video.qa ?? video.contract_check;
    const qa = asObject(qaValue);
    const media = asObject(tuned.media || video.media);
    const method = actualVideoMethod(
      { method: firstText(video.method, tuned.video_method) },
      executionMode,
    );
    const promptEvaluated = inferPromptEvaluated(
      method,
      typeof video.prompt_evaluated === "boolean"
        ? video.prompt_evaluated
        : tuned.prompt_evaluated,
    );
    return {
      url: firstText(
        tuned.video_url,
        typeof videoValue === "string" ? videoValue : "",
        video.url,
        video.video_url,
      ),
      repositoryPath: firstText(
        tuned.repository_video_path,
        tuned.video_path,
        tuned.path,
        video.repository_video_path,
        video.video_path,
        video.path,
      ),
      status: firstText(tuned.video_status, video.status, tuned.status),
      delivery: firstText(tuned.delivery, video.delivery),
      sha256: firstText(tuned.video_sha256, tuned.sha256, video.sha256, media.sha256),
      bytes: finiteNumber(tuned.video_bytes ?? tuned.bytes ?? video.bytes ?? media.bytes),
      media,
      qa,
      method,
      promptEvaluated,
      providerAttempt: normalizeProviderAttempt(
        video.provider_attempt ?? tuned.provider_attempt,
      ),
      qaStatus: firstText(tuned.qa_status, video.qa_status, qa.status),
      qaVerified:
        qa.verified === true || qa.passed === true || qa.conforms === true
          ? true
          : qa.verified === false || qa.passed === false || qa.conforms === false
            ? false
            : null,
    };
  }

  function tunedVideoState(videoValue, executionMode) {
    const video = asObject(videoValue);
    if (firstText(video.url, video.repositoryPath)) return "available";
    const status = firstText(video.status).toLowerCase();
    if (/pending|queued|running|generating|processing|uploading/.test(status)) return "pending";
    if (/unavailable|failed|error|blocked|rejected|missing|skipped|cancelled|aborted/.test(status)) return "unavailable";
    return "pending";
  }

  function normalizeManifest(raw) {
    if (!isRecord(raw)) throw new Error("Tune manifest должен быть JSON-объектом.");

    const cases = collectCases(raw);
    if (!cases.length) throw new Error("В tune manifest нет массива cases.");

    const items = [];
    const issues = [];

    cases.forEach((caseRecord, caseIndex) => {
      const source = asObject(caseRecord.source || caseRecord.image);
      const planning = asObject(caseRecord.planning);
      let targets = toRecordArray(caseRecord.targets);
      if (!targets.length && (caseRecord.baseline || caseRecord.tuned)) {
        targets = [caseRecord];
      }

      const caseId = firstText(
        caseRecord.case_id,
        caseRecord.caseId,
        `${firstText(caseRecord.article_number, String(caseIndex + 1).padStart(2, "0"))}#${firstText(source.image_id, caseRecord.image_id, "image")}`,
      );

      if (!targets.length) {
        issues.push(`${caseId}: нет targets`);
        return;
      }

      targets.forEach((target, targetIndex) => {
        const baseline = asObject(target.baseline || caseRecord.baseline);
        const tuned = asObject(target.tuned || caseRecord.tuned);
        const modelId = firstText(
          target.model_id,
          target.modelId,
          baseline.model_id,
          tuned.model_id,
        );
        if (!modelId) {
          issues.push(`${caseId}: target ${targetIndex + 1} без model_id`);
          return;
        }

        const ratingRaw = firstText(target.rating_raw, target.rating, target.score);
        const ratingState = normalizeRatingState(target.rating_state, ratingRaw);
        const failureCategory = firstText(
          target.primary_failure_category,
          target.failure_category,
          target.category,
          caseRecord.primary_failure_category,
        );
        const comments = [
          ...textList(target.comment),
          ...textList(target.feedback),
        ].filter((value, index, all) => all.indexOf(value) === index);
        const executionMode = normalizeMode(target, tuned, planning);
        const tunedVideo = normalizeTunedVideo(tuned, executionMode);
        const structuredIntent = asObject(
          planning.structured_intent || caseRecord.structured_intent || tuned.structured_intent,
        );
        const sourceWidth = finiteNumber(source.width || caseRecord.width);
        const sourceHeight = finiteNumber(source.height || caseRecord.height);

        items.push({
          id: `${caseId}::${modelId}`,
          caseId,
          articleNumber: firstText(caseRecord.article_number, caseRecord.articleNumber),
          articleSlug: firstText(caseRecord.article_slug, caseRecord.articleSlug),
          title: firstText(caseRecord.title, caseRecord.article_title, `Кейс ${caseId}`),
          brand: firstText(caseRecord.brand),
          publicationId: firstText(caseRecord.publication_id, caseRecord.publicationId),
          contentClass: firstText(caseRecord.content_class, caseRecord.contentClass, caseRecord.category),
          hypothesis: firstText(caseRecord.hypothesis),
          contextPath: firstText(caseRecord.context_path),
          acceptedSiblingModelIds: Array.isArray(caseRecord.accepted_sibling_model_ids)
            ? caseRecord.accepted_sibling_model_ids.map(cleanText).filter(Boolean)
            : [],
          source: {
            imageId: firstText(source.image_id, caseRecord.image_id),
            role: firstText(source.role, caseRecord.image_type),
            caption: firstText(source.caption, caseRecord.caption),
            path: firstText(source.path, source.source_path, caseRecord.source_path),
            url: firstText(source.url, source.orig_url, caseRecord.source_url),
            sha256: firstText(source.sha256),
            width: sourceWidth,
            height: sourceHeight,
          },
          modelId,
          modelLabel: firstText(target.model_label, MODEL_LABELS[modelId], modelId),
          sheetRow: finiteNumber(target.sheet_row),
          ratingState,
          ratingRaw,
          failureCategory: failureCategory || "unclassified",
          comments,
          baseline: {
            scenePlan: firstText(baseline.scene_plan, baseline.plan),
            positivePrompt: firstText(baseline.positive_prompt, baseline.prompt),
            negativePrompt:
              baseline.negative_prompt === null
                ? null
                : firstText(baseline.negative_prompt, baseline.negativePrompt),
            videoUrl: firstText(baseline.video_url, baseline.url, baseline.video),
            repositoryVideoPath: firstText(
              baseline.repository_video_path,
              baseline.video_path,
              baseline.path,
            ),
            media: asObject(baseline.media),
            status: firstText(baseline.status),
          },
          tuned: {
            executionMode,
            scenePlan: firstText(tuned.scene_plan, tuned.plan),
            positivePrompt:
              tuned.positive_prompt === null
                ? null
                : firstText(tuned.positive_prompt, tuned.prompt),
            negativePrompt:
              tuned.negative_prompt === null
                ? null
                : firstText(tuned.negative_prompt, tuned.negativePrompt),
            runtime: asObject(tuned.runtime),
            video: tunedVideo,
          },
          planning: {
            runId: firstText(planning.run_id, caseRecord.run_id),
            resultPath: firstText(planning.result_path, caseRecord.result_path),
            provenance: asObject(planning.provenance || caseRecord.provenance),
            structuredIntent,
            imageReading: textList(planning.image_reading || caseRecord.image_reading),
            articleContext: firstText(planning.article_context, caseRecord.article_context),
          },
        });
      });
    });

    if (!items.length) {
      throw new Error(`Tune manifest не содержит валидных model-targets. ${issues.join("; ")}`);
    }

    const uniqueCaseIds = new Set(items.map((item) => item.caseId));
    return {
      schemaVersion: raw.schema_version,
      role: firstText(raw.manifest_role),
      ticket: firstText(raw.ticket),
      batchId: firstText(raw.batch_id),
      agentId: firstText(raw.agent_id),
      contractVersion: firstText(raw.contract_version),
      generatedAt: firstText(raw.generated_at),
      scope: asObject(raw.scope),
      summary: asObject(raw.summary),
      caseCount: uniqueCaseIds.size,
      targetCount: items.length,
      items,
      issues,
    };
  }

  function encodeRepositoryPath(value) {
    const normalized = value
      .replace(/^(\.\.\/)+/, "")
      .replace(/^\.\//, "")
      .replace(/^\/+/, "");
    return normalized
      .split("/")
      .map((segment) => {
        try {
          return encodeURIComponent(decodeURIComponent(segment));
        } catch (_error) {
          return encodeURIComponent(segment);
        }
      })
      .join("/");
  }

  function resolveMediaUrl(value, runtime = {}) {
    const candidate = cleanText(value);
    if (!candidate) return "";

    try {
      const absolute = new URL(candidate);
      return absolute.protocol === "https:" || absolute.protocol === "http:"
        ? absolute.href
        : "";
    } catch (_error) {
      // Repository-relative path; handled below.
    }

    const path = encodeRepositoryPath(candidate);
    if (!path) return "";
    const hostname = cleanText(runtime.hostname) ||
      (typeof window !== "undefined" ? window.location.hostname : "");
    if (hostname.endsWith("github.io")) {
      return `${runtime.rawBase || RAW_REPOSITORY_BASE}${path}`;
    }
    return `../${path}`;
  }

  function applyFilters(items, filters = {}) {
    return items.filter((item) => {
      if (filters.category && filters.category !== "all" && item.failureCategory !== filters.category) {
        return false;
      }
      if (filters.model && filters.model !== "all" && item.modelId !== filters.model) {
        return false;
      }
      if (filters.mode && filters.mode !== "all" && item.tuned.executionMode !== filters.mode) {
        return false;
      }
      if (filters.rating && filters.rating !== "all" && item.ratingState !== filters.rating) {
        return false;
      }
      return true;
    });
  }

  function normalizeReviewEntry(value) {
    const review = asObject(value);
    const outcome = REVIEW_OUTCOMES.includes(review.outcome) ? review.outcome : "";
    const note = cleanText(review.note).slice(0, 2000);
    const updatedAt = firstText(review.updated_at, review.updatedAt);
    return { outcome, note, updatedAt };
  }

  function summarizeReviews(items, reviewValue) {
    const reviews = asObject(reviewValue);
    const summary = {
      target_count: items.length,
      saved_entry_count: 0,
      evaluated_count: 0,
      draft_count: 0,
      helped_count: 0,
      same_or_unclear_count: 0,
      worse_count: 0,
      unrated_count: items.length,
    };
    items.forEach((item) => {
      const review = normalizeReviewEntry(reviews[item.id]);
      if (!review.outcome && !review.note) return;
      summary.saved_entry_count += 1;
      if (!review.outcome) {
        summary.draft_count += 1;
        return;
      }
      summary.evaluated_count += 1;
      if (review.outcome === "helped") summary.helped_count += 1;
      if (review.outcome === "same-or-unclear") summary.same_or_unclear_count += 1;
      if (review.outcome === "worse") summary.worse_count += 1;
    });
    summary.unrated_count = summary.target_count - summary.evaluated_count;
    return summary;
  }

  function fallbackAudit(videoValue) {
    const video = asObject(videoValue);
    if (actualVideoMethod(video) !== "deterministic-compositor-fallback") return null;
    const attempt = normalizeProviderAttempt(video.providerAttempt || video.provider_attempt);
    return {
      title: "Prompt не оценён: provider filtered",
      status: attempt.status || "provider-failed",
      providerJobId: attempt.providerJobId,
      error: attempt.error || "Provider завершил попытку без reviewable output.",
    };
  }

  function exportProviderAttempt(value) {
    const attempt = normalizeProviderAttempt(value);
    if (!attempt.status && !attempt.providerJobId && !attempt.error) return null;
    return {
      status: attempt.status || null,
      prompt_evaluated: attempt.promptEvaluated,
      run_path: attempt.runPath || null,
      run_sha256: attempt.runSha256 || null,
      provider_job_id: attempt.providerJobId || null,
      error: attempt.error || null,
    };
  }

  function buildReviewExport(manifestValue, reviewValue, exportedAt = new Date().toISOString()) {
    const manifest = asObject(manifestValue);
    const items = Array.isArray(manifest.items) ? manifest.items : [];
    const reviews = asObject(reviewValue);
    const evaluations = [];
    items.forEach((item) => {
      const review = normalizeReviewEntry(reviews[item.id]);
      if (!review.outcome && !review.note) return;
      const method = actualVideoMethod(item.tuned.video, item.tuned.executionMode);
      const promptEvaluated = inferPromptEvaluated(
        method,
        item.tuned.video.promptEvaluated,
      );
      evaluations.push({
        evaluation_id: item.id,
        case_id: item.caseId,
        article_number: item.articleNumber || null,
        article_slug: item.articleSlug || null,
        image_id: item.source.imageId || null,
        model_id: item.modelId,
        planned_execution_mode: item.tuned.executionMode,
        method,
        prompt_evaluated: promptEvaluated,
        outcome: review.outcome || null,
        note: review.note || null,
        updated_at: review.updatedAt || null,
        tuned_video: {
          state: tunedVideoState(item.tuned.video, item.tuned.executionMode),
          status: item.tuned.video.status || null,
          delivery: item.tuned.video.delivery || null,
          url: item.tuned.video.url || null,
          repository_video_path: item.tuned.video.repositoryPath || null,
          sha256: item.tuned.video.sha256 || null,
          method,
          prompt_evaluated: promptEvaluated,
          provider_attempt: exportProviderAttempt(item.tuned.video.providerAttempt),
          qa_status: item.tuned.video.qaStatus || null,
          qa_verified: item.tuned.video.qaVerified,
        },
      });
    });
    return {
      schema_version: 1,
      export_role: "clipmaker-lite-tune-evaluation",
      exported_at: exportedAt,
      dataset: {
        ticket: manifest.ticket || null,
        batch_id: manifest.batchId || null,
        contract_version: manifest.contractVersion || null,
        manifest_generated_at: manifest.generatedAt || null,
      },
      summary: summarizeReviews(items, reviews),
      evaluations,
    };
  }

  const testHooks = Object.freeze({
    actualVideoMethod,
    applyFilters,
    buildReviewExport,
    encodeRepositoryPath,
    fallbackAudit,
    inferPromptEvaluated,
    modeLabel,
    normalizeManifest,
    normalizeProviderAttempt,
    normalizeReviewEntry,
    normalizeRatingState,
    normalizeTunedVideo,
    resolveMediaUrl,
    summarizeReviews,
    tunedVideoState,
  });
  globalThis.__tuneTestHooks = testHooks;

  if (typeof document === "undefined") return;

  const dom = {
    datasetStatus: document.querySelector("#datasetStatus"),
    caseCountSummary: document.querySelector("#caseCountSummary"),
    targetCountSummary: document.querySelector("#targetCountSummary"),
    regenerateCountSummary: document.querySelector("#regenerateCountSummary"),
    blankCountSummary: document.querySelector("#blankCountSummary"),
    compositorCountSummary: document.querySelector("#compositorCountSummary"),
    filterForm: document.querySelector("#filterForm"),
    categoryFilter: document.querySelector("#categoryFilter"),
    modelFilter: document.querySelector("#modelFilter"),
    modeFilter: document.querySelector("#modeFilter"),
    ratingFilter: document.querySelector("#ratingFilter"),
    resetFilters: document.querySelector("#resetFilters"),
    filterResult: document.querySelector("#filterResult"),
    reviewProgress: document.querySelector("#reviewProgress"),
    reviewBreakdown: document.querySelector("#reviewBreakdown"),
    storageStatus: document.querySelector("#storageStatus"),
    exportReviews: document.querySelector("#exportReviews"),
    currentNumber: document.querySelector("#currentNumber"),
    totalNumber: document.querySelector("#totalNumber"),
    caseTitle: document.querySelector("#caseTitle"),
    caseMeta: document.querySelector("#caseMeta"),
    previousTarget: document.querySelector("#previousTarget"),
    nextTarget: document.querySelector("#nextTarget"),
    targetSelect: document.querySelector("#targetSelect"),
    loadState: document.querySelector("#loadState"),
    targetView: document.querySelector("#targetView"),
  };

  const state = {
    manifest: null,
    items: [],
    filtered: [],
    currentIndex: 0,
    requestedCase: "",
    requestedModel: "",
    reviews: {},
    reviewStorageKey: "",
    storageAvailable: true,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value) {
    const number = finiteNumber(value);
    return number === null ? "—" : formatter.format(number);
  }

  function formatBytes(value) {
    const bytes = finiteNumber(value);
    if (bytes === null || bytes < 0) return "—";
    if (bytes < 1024) return `${formatNumber(bytes)} B`;
    const units = ["KB", "MB", "GB"];
    let amount = bytes / 1024;
    let unit = units[0];
    for (let index = 1; index < units.length && amount >= 1024; index += 1) {
      amount /= 1024;
      unit = units[index];
    }
    return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(amount)} ${unit}`;
  }

  function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function setStorageStatus(message, stateName = "ready") {
    dom.storageStatus.textContent = message;
    dom.storageStatus.dataset.state = stateName;
  }

  function loadStoredReviews() {
    const datasetId = state.manifest.batchId || state.manifest.ticket || "default";
    state.reviewStorageKey = `${REVIEW_STORAGE_PREFIX}${datasetId}`;
    state.reviews = {};
    state.storageAvailable = true;
    try {
      const raw = window.localStorage.getItem(state.reviewStorageKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        const entries = asObject(parsed.entries || parsed);
        const validIds = new Set(state.items.map((item) => item.id));
        Object.entries(entries).forEach(([id, value]) => {
          if (!validIds.has(id)) return;
          const review = normalizeReviewEntry(value);
          if (review.outcome || review.note) state.reviews[id] = review;
        });
      }
      setStorageStatus("Оценки сохраняются только в этом браузере.");
    } catch (_error) {
      state.storageAvailable = false;
      setStorageStatus(
        "LocalStorage недоступен: оценки сохранятся только до перезагрузки.",
        "error",
      );
    }
  }

  function persistReviews() {
    if (!state.storageAvailable) return false;
    try {
      window.localStorage.setItem(
        state.reviewStorageKey,
        JSON.stringify({
          schema_version: 1,
          dataset_id: state.manifest.batchId || state.manifest.ticket || null,
          entries: state.reviews,
        }),
      );
      return true;
    } catch (_error) {
      state.storageAvailable = false;
      setStorageStatus(
        "LocalStorage недоступен: текущие оценки остаются только в памяти.",
        "error",
      );
      return false;
    }
  }

  function renderReviewOverview() {
    if (!state.manifest) return;
    const summary = summarizeReviews(state.items, state.reviews);
    dom.reviewProgress.textContent = `Оценено ${formatNumber(summary.evaluated_count)} из ${formatNumber(summary.target_count)} целей`;
    dom.reviewBreakdown.textContent = [
      `Helped ${formatNumber(summary.helped_count)}`,
      `Same / unclear ${formatNumber(summary.same_or_unclear_count)}`,
      `Worse ${formatNumber(summary.worse_count)}`,
      summary.draft_count ? `Черновики ${formatNumber(summary.draft_count)}` : "",
    ].filter(Boolean).join(" · ");
    dom.exportReviews.disabled = summary.saved_entry_count === 0;
  }

  function saveReview(item, outcome, note) {
    const normalized = normalizeReviewEntry({
      outcome,
      note,
      updated_at: new Date().toISOString(),
    });
    if (!normalized.outcome && !normalized.note) delete state.reviews[item.id];
    else state.reviews[item.id] = normalized;
    const persisted = persistReviews();
    renderReviewOverview();
    return persisted;
  }

  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value.replaceAll("_", " ");
  }

  function contentClassLabel(value) {
    return CONTENT_CLASS_LABELS[value] || value.replaceAll("_", " ") || "—";
  }

  function modeLabel(value) {
    return MODE_LABELS[value] || value || "Не указан";
  }

  function ratingLabel(item) {
    return item.ratingRaw || RATING_LABELS[item.ratingState] || item.ratingState || "—";
  }

  function setControlState(enabled) {
    [
      dom.categoryFilter,
      dom.modelFilter,
      dom.modeFilter,
      dom.ratingFilter,
      dom.resetFilters,
      dom.targetSelect,
    ].forEach((element) => {
      element.disabled = !enabled;
    });
    if (!enabled) dom.exportReviews.disabled = true;
  }

  function setOptions(select, options, selectedValue) {
    const fragment = document.createDocumentFragment();
    options.forEach(({ value, label }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      fragment.append(option);
    });
    select.replaceChildren(fragment);
    if (options.some((option) => option.value === selectedValue)) {
      select.value = selectedValue;
    }
  }

  function populateFilters() {
    const previous = {
      category: dom.categoryFilter.value,
      model: dom.modelFilter.value,
      mode: dom.modeFilter.value,
      rating: dom.ratingFilter.value,
    };
    const unique = (selector) => [...new Set(state.items.map(selector).filter(Boolean))].sort();

    setOptions(
      dom.categoryFilter,
      [
        { value: "all", label: "Все проблемы" },
        ...unique((item) => item.failureCategory).map((value) => ({
          value,
          label: categoryLabel(value),
        })),
      ],
      previous.category,
    );
    setOptions(
      dom.modelFilter,
      [
        { value: "all", label: "Все модели" },
        ...unique((item) => item.modelId).map((value) => ({
          value,
          label: MODEL_LABELS[value] || value,
        })),
      ],
      previous.model,
    );
    setOptions(
      dom.modeFilter,
      [
        { value: "all", label: "Все режимы" },
        ...unique((item) => item.tuned.executionMode).map((value) => ({
          value,
          label: modeLabel(value),
        })),
      ],
      previous.mode,
    );
    setOptions(
      dom.ratingFilter,
      [
        { value: "all", label: "Все оценки" },
        ...unique((item) => item.ratingState).map((value) => ({
          value,
          label: RATING_LABELS[value] || value,
        })),
      ],
      previous.rating,
    );
  }

  function readFilters() {
    return {
      category: dom.categoryFilter.value,
      model: dom.modelFilter.value,
      mode: dom.modeFilter.value,
      rating: dom.ratingFilter.value,
    };
  }

  function updateSummary() {
    const ratingSummary = asObject(state.manifest.summary.rating);
    const modeSummary = asObject(state.manifest.summary.execution_mode_counts);
    const regenerate = finiteNumber(ratingSummary.regenerate_count) ??
      state.items.filter((item) => item.ratingState === "regenerate").length;
    const blank = finiteNumber(ratingSummary.blank_count) ??
      state.items.filter((item) => item.ratingState === "blank").length;
    const compositor = finiteNumber(modeSummary["deterministic-compositor"]) ??
      state.items.filter((item) => item.tuned.executionMode === "deterministic-compositor").length;

    dom.caseCountSummary.textContent = formatNumber(
      finiteNumber(state.manifest.scope.case_count) ?? state.manifest.caseCount,
    );
    dom.targetCountSummary.textContent = formatNumber(
      finiteNumber(state.manifest.scope.target_count) ?? state.manifest.targetCount,
    );
    dom.regenerateCountSummary.textContent = formatNumber(regenerate);
    dom.blankCountSummary.textContent = formatNumber(blank);
    dom.compositorCountSummary.textContent = formatNumber(compositor);
  }

  function updateTargetSelect(selectedId) {
    const options = state.filtered.map((item, index) => ({
      value: item.id,
      label: `${String(index + 1).padStart(2, "0")} · ${item.caseId} · ${item.modelLabel}`,
    }));
    setOptions(dom.targetSelect, options, selectedId);
  }

  function updateUrl(item) {
    if (!item || !window.history?.replaceState) return;
    const url = new URL(window.location.href);
    url.searchParams.set("case", item.caseId);
    url.searchParams.set("model", item.modelId);
    const filters = readFilters();
    ["category", "mode", "rating"].forEach((key) => {
      if (filters[key] && filters[key] !== "all") url.searchParams.set(key, filters[key]);
      else url.searchParams.delete(key);
    });
    window.history.replaceState({}, "", url);
  }

  function inlineFacts(facts) {
    return facts
      .filter(([, value]) => value !== "" && value !== null && value !== undefined)
      .map(
        ([label, value]) =>
          `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`,
      )
      .join("");
  }

  function promptBlock(title, value, emptyMessage) {
    const content = value
      ? `<pre>${escapeHtml(value)}</pre>`
      : `<p class="promptEmpty">${escapeHtml(emptyMessage)}</p>`;
    return `<section class="promptBlock"><h4>${escapeHtml(title)}</h4>${content}</section>`;
  }

  function mediaRatio(width, height) {
    return width && height && width > 0 && height > 0 ? `${width} / ${height}` : "16 / 9";
  }

  function renderIntent(intent) {
    const rows = INTENT_ORDER.filter((key) => cleanText(intent[key])).map(
      (key) =>
        `<div><dt>${escapeHtml(INTENT_LABELS[key])}</dt><dd>${escapeHtml(intent[key])}</dd></div>`,
    );
    return rows.length
      ? `<dl class="intentGrid">${rows.join("")}</dl>`
      : '<p class="promptEmpty">Structured intent не передан.</p>';
  }

  function tunedQaLabel(video) {
    if (video.qaVerified === true) return "verified";
    if (video.qaVerified === false) return "failed";
    return video.qaStatus || "не указан";
  }

  function tunedMediaPlaceholder(videoState, videoStatus) {
    const copy = {
      pending: {
        title: "Tuned MP4 ожидается",
        note: "План и prompt готовы; remote delivery ещё не добавлен в manifest.",
      },
      unavailable: {
        title: "Tuned MP4 недоступен",
        note: videoStatus || "Manifest помечает результат как недоступный.",
      },
      "not-applicable": {
        title: "MP4 не требуется",
        note: "Deterministic compositor — осознанный abstention от generative I2V.",
      },
    }[videoState] || {
      title: "Tuned MP4 не указан",
      note: "Добавьте HTTPS URL или repository video path в manifest.",
    };
    return `
      <div class="mediaState" data-state="${escapeHtml(videoState)}">
        <div class="mediaStateInner">
          <span class="mediaStateMark" aria-hidden="true"></span>
          <strong>${escapeHtml(copy.title)}</strong>
          <small>${escapeHtml(copy.note)}</small>
        </div>
      </div>
    `;
  }

  function fallbackNoticeMarkup(video) {
    const audit = fallbackAudit(video);
    if (!audit) return "";
    const terminal = [audit.status, audit.providerJobId && `job ${audit.providerJobId}`]
      .filter(Boolean)
      .join(" · ");
    return `
      <aside class="fallbackNotice" aria-label="Provider fallback audit">
        <strong>${escapeHtml(audit.title)}</strong>
        <p>provider_attempt terminal${terminal ? ` · ${escapeHtml(terminal)}` : ""}</p>
        <small>${escapeHtml(audit.error)}</small>
      </aside>
    `;
  }

  function reviewEditorMarkup(item) {
    const review = normalizeReviewEntry(state.reviews[item.id]);
    const videoState = tunedVideoState(item.tuned.video, item.tuned.executionMode);
    const method = actualVideoMethod(item.tuned.video, item.tuned.executionMode);
    const reviewPrompt = videoState === "available"
      ? method === "deterministic-compositor-fallback"
        ? "Сравните deterministic fallback с baseline. Оценка относится к fallback MP4; исходный I2V prompt provider не оценил."
        : "Сравните tuned MP4 с baseline и оцените, помогло ли изменение Clipmaker Lite."
      : "Tuned MP4 ещё нельзя сравнить с baseline; оценку и заметку можно сохранить сейчас и уточнить после delivery.";
    const checked = (outcome) => review.outcome === outcome ? " checked" : "";
    const saved = review.updatedAt
      ? `Сохранено ${formatDate(review.updatedAt)}`
      : "Ещё не оценено.";
    return `
      <section class="reviewWorkbench" aria-labelledby="tuneReviewTitle">
        <div>
          <p class="sectionKicker">Human review · local only</p>
          <h3 id="tuneReviewTitle">Помог ли tune?</h3>
          <p class="reviewPrompt">${escapeHtml(reviewPrompt)}</p>
        </div>
        <div class="reviewEditor" data-review-editor>
          <fieldset class="outcomeFieldset">
            <legend class="visuallyHidden">Результат tune для ${escapeHtml(item.caseId)} и ${escapeHtml(item.modelLabel)}</legend>
            <div class="outcomeChoices">
              <label class="outcomeChoice">
                <input type="radio" name="tuneOutcome" value="helped"${checked("helped")} />
                <span>Helped</span>
              </label>
              <label class="outcomeChoice">
                <input type="radio" name="tuneOutcome" value="same-or-unclear"${checked("same-or-unclear")} />
                <span>Same / unclear</span>
              </label>
              <label class="outcomeChoice">
                <input type="radio" name="tuneOutcome" value="worse"${checked("worse")} />
                <span>Worse</span>
              </label>
            </div>
          </fieldset>
          <label class="reviewNote">
            <span>Комментарий к tune</span>
            <textarea maxlength="2000" placeholder="Что именно стало лучше или хуже?">${escapeHtml(review.note)}</textarea>
          </label>
          <div class="reviewActions">
            <button class="controlButton" data-clear-review type="button"${review.outcome || review.note ? "" : " disabled"}>Очистить оценку</button>
            <p class="reviewSaveStatus" data-review-save-status aria-live="polite">${escapeHtml(saved)}</p>
          </div>
        </div>
      </section>
    `;
  }

  function bindReviewEditor(item) {
    const editor = dom.targetView.querySelector("[data-review-editor]");
    if (!editor) return;
    const radios = [...editor.querySelectorAll('input[name="tuneOutcome"]')];
    const note = editor.querySelector("textarea");
    const clear = editor.querySelector("[data-clear-review]");
    const status = editor.querySelector("[data-review-save-status]");
    const commit = () => {
      const outcome = radios.find((radio) => radio.checked)?.value || "";
      const persisted = saveReview(item, outcome, note.value);
      clear.disabled = !outcome && !cleanText(note.value);
      status.dataset.state = persisted || !state.storageAvailable ? "ready" : "error";
      status.textContent = state.storageAvailable
        ? `Сохранено в браузере · ${new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(new Date())}`
        : "Сохранено только в памяти до перезагрузки.";
    };
    radios.forEach((radio) => radio.addEventListener("change", commit));
    note.addEventListener("input", commit);
    clear.addEventListener("click", () => {
      radios.forEach((radio) => { radio.checked = false; });
      note.value = "";
      commit();
      status.textContent = "Оценка очищена.";
    });
  }

  function renderItem(item) {
    const sourceUrl = resolveMediaUrl(item.source.url || item.source.path);
    const baselineVideoUrl = resolveMediaUrl(
      item.baseline.videoUrl || item.baseline.repositoryVideoPath,
    );
    const tunedVideo = item.tuned.video;
    const tunedMethod = actualVideoMethod(tunedVideo, item.tuned.executionMode);
    const tunedVideoUrl = resolveMediaUrl(tunedVideo.url || tunedVideo.repositoryPath);
    const tunedState = tunedVideoState(tunedVideo, item.tuned.executionMode);
    const sourceDimensions = item.source.width && item.source.height
      ? `${formatNumber(item.source.width)} × ${formatNumber(item.source.height)}`
      : "Размер не указан";
    const media = item.baseline.media;
    const comparisonRatio = mediaRatio(item.source.width, item.source.height);
    const baselineDimensions = finiteNumber(media.width) && finiteNumber(media.height)
      ? `${formatNumber(media.width)} × ${formatNumber(media.height)}`
      : "—";
    const baselineDuration = finiteNumber(media.duration_seconds);
    const tunedMedia = tunedVideo.media;
    const tunedDimensions = finiteNumber(tunedMedia.width) && finiteNumber(tunedMedia.height)
      ? `${formatNumber(tunedMedia.width)} × ${formatNumber(tunedMedia.height)}`
      : "—";
    const tunedDuration = finiteNumber(tunedMedia.duration_seconds);
    const runtime = item.tuned.runtime;
    const intent = item.planning.structuredIntent;
    const strategy = firstText(intent.rendering_strategy);
    const isCompositor = item.tuned.executionMode === "deterministic-compositor";
    const sourceMedia = sourceUrl
      ? `<img data-source-image src="${escapeHtml(sourceUrl)}" alt="${escapeHtml(item.source.caption || item.title)}" decoding="async" /><p class="mediaUnavailable" data-source-error hidden>Исходник не удалось загрузить. Проверьте URL или repository path в manifest.</p>`
      : '<p class="mediaUnavailable">В manifest нет URL или repository path исходника.</p>';
    const baselineMedia = baselineVideoUrl
      ? `<video data-media-video data-media-role="baseline" data-media-src="${escapeHtml(baselineVideoUrl)}" controls playsinline preload="metadata"${sourceUrl ? ` poster="${escapeHtml(sourceUrl)}"` : ""} aria-label="Baseline ${escapeHtml(item.modelLabel)}"></video><p class="mediaUnavailable" data-media-error="baseline" hidden>Baseline MP4 не удалось загрузить. Проверьте delivery URL в manifest.</p>`
      : '<p class="mediaUnavailable">В manifest нет existing baseline MP4.</p>';
    const tunedMediaMarkup = tunedState === "available"
      ? `<video data-media-video data-media-role="tuned" data-media-src="${escapeHtml(tunedVideoUrl)}" controls playsinline preload="metadata"${sourceUrl ? ` poster="${escapeHtml(sourceUrl)}"` : ""} aria-label="Tuned ${escapeHtml(item.modelLabel)}"></video><p class="mediaUnavailable" data-media-error="tuned" hidden>Tuned MP4 не удалось загрузить. Проверьте remote delivery URL в manifest.</p>`
      : tunedMediaPlaceholder(tunedState, tunedVideo.status);
    const tunedQaDetails = Object.keys(tunedVideo.qa).length
      ? `<details class="mediaQa"><summary>QA tuned MP4</summary><pre>${escapeHtml(JSON.stringify(tunedVideo.qa, null, 2))}</pre></details>`
      : "";
    const tunedDelivery = [
      tunedVideo.delivery,
      tunedVideo.url || tunedVideo.repositoryPath,
    ].filter(Boolean).join(" · ");
    const fallbackNotice = fallbackNoticeMarkup(tunedVideo);
    const feedback = item.comments.length
      ? item.comments.map((comment) => `<p>${escapeHtml(comment)}</p>`).join("")
      : '<p class="feedbackMissing">Комментарий в исходной оценке отсутствует.</p>';
    const acceptedSiblings = item.acceptedSiblingModelIds.length
      ? item.acceptedSiblingModelIds.map((modelId) => MODEL_LABELS[modelId] || modelId).join(", ")
      : "нет";
    const verified = item.planning.provenance.verified === true;
    const provenanceState = verified ? "verified" : "not verified";
    const feasibility = firstText(intent.feasibility_assessment);
    const decisionDescription = isCompositor
      ? "Generative I2V намеренно не получает prompt. Scene plan передаёт один ограниченный 2D-эффект детерминированному compositor и сохраняет точный текст, UI или графическое состояние."
      : `Clipmaker Lite оставил цель в generative I2V${strategy ? ` со стратегией ${modeLabel(strategy)}` : ""}.`;
    const tunedPromptEmpty = isCompositor
      ? "null — prompt для video provider не создаётся"
      : "Tuned prompt не передан.";

    dom.targetView.innerHTML = `
      <header class="caseIdentity">
        <div>
          <p class="caseLabel">Статья ${escapeHtml(item.articleNumber || "—")} · изображение ${escapeHtml(item.source.imageId || "—")}</p>
          <h3>${escapeHtml(item.title)}</h3>
          <p class="caseHypothesis">${escapeHtml(item.hypothesis || "Гипотеза для кейса не указана.")}</p>
        </div>
        <dl class="caseFacts">
          ${inlineFacts([
            ["Модель", item.modelLabel],
            ["Категория", categoryLabel(item.failureCategory)],
            ["Класс", contentClassLabel(item.contentClass)],
            ["Режим", modeLabel(item.tuned.executionMode)],
          ])}
        </dl>
      </header>

      <section class="mediaComparison" aria-label="Исходник, baseline и tuned video">
        <figure class="mediaPanel">
          <div class="mediaPanelHeading">
            <h3>Исходник</h3>
            <p>${escapeHtml(sourceDimensions)} · ${escapeHtml(item.source.role || "image")}</p>
          </div>
          <div class="mediaFrame" style="--media-ratio: ${escapeHtml(comparisonRatio)}">
            ${sourceMedia}
          </div>
          <figcaption class="mediaCaption">
            <p class="sourceCaption">${escapeHtml(item.source.caption || "Подпись отсутствует.")}</p>
          </figcaption>
        </figure>

        <figure class="mediaPanel">
          <div class="mediaPanelHeading">
            <h3>Baseline · existing MP4</h3>
            <p>${escapeHtml(item.modelLabel)} · ${escapeHtml(item.baseline.status || "status —")}</p>
          </div>
          <div class="mediaFrame" style="--media-ratio: ${escapeHtml(comparisonRatio)}">
            ${baselineMedia}
          </div>
          <figcaption class="mediaCaption">
            <dl class="mediaFacts">
              ${inlineFacts([
                ["Размер", baselineDimensions],
                ["Длительность", baselineDuration === null ? "—" : `${baselineDuration.toFixed(1)} с`],
                ["Вес", formatBytes(media.bytes)],
                ["Звук", media.has_audio === true ? "есть" : media.has_audio === false ? "нет" : "—"],
              ])}
            </dl>
          </figcaption>
        </figure>

        <figure class="mediaPanel">
          <div class="mediaPanelHeading">
            <h3>Tuned · MP4</h3>
            <p class="methodBadge" data-method="${escapeHtml(tunedMethod)}">${escapeHtml(modeLabel(tunedMethod))}</p>
          </div>
          <div class="mediaFrame" style="--media-ratio: ${escapeHtml(comparisonRatio)}">
            ${tunedMediaMarkup}
          </div>
          <figcaption class="mediaCaption">
            <dl class="mediaFacts">
              ${inlineFacts([
                ["Статус", tunedVideo.status || tunedState],
                ["Метод", modeLabel(tunedMethod)],
                ["Prompt evaluated", tunedVideo.promptEvaluated === true ? "да" : tunedVideo.promptEvaluated === false ? "нет" : "—"],
                ["QA", tunedQaLabel(tunedVideo)],
                ["Размер", tunedDimensions],
                ["Длительность", tunedDuration === null ? "—" : `${tunedDuration.toFixed(1)} с`],
                ["Вес", formatBytes(tunedVideo.bytes)],
                ["Delivery", tunedDelivery || "—"],
              ])}
            </dl>
            ${tunedQaDetails}
          </figcaption>
        </figure>
      </section>

      <section class="analysisComparison" aria-label="Baseline и tuned prompt">
        <section class="textPanel">
          <header class="textPanelHeader">
            <div>
              <p class="sectionKicker">Baseline review</p>
              <h3>Обратная связь</h3>
            </div>
            <p class="statusText" data-rating="${escapeHtml(item.ratingState)}">${escapeHtml(ratingLabel(item))}</p>
          </header>
          <blockquote class="feedbackQuote">${feedback}</blockquote>
          <section class="hypothesisBlock">
            <h4>Рабочая гипотеза</h4>
            <p>${escapeHtml(item.hypothesis || "Не указана.")}</p>
          </section>
          ${promptBlock("Baseline prompt", item.baseline.positivePrompt, "Baseline prompt не передан.")}
          <details class="detailDisclosure">
            <summary>Baseline scene plan и технические поля</summary>
            <section class="planBlock">
              <h4>Scene plan</h4>
              <p>${escapeHtml(item.baseline.scenePlan || "Не передан.")}</p>
            </section>
            ${promptBlock("Negative prompt", item.baseline.negativePrompt, "null")}
          </details>
        </section>

        <section class="textPanel">
          <header class="textPanelHeader">
            <div>
              <p class="sectionKicker">Updated Clipmaker Lite</p>
              <h3>Tuned plan</h3>
            </div>
            <p class="statusText">${escapeHtml(modeLabel(item.tuned.executionMode))}</p>
          </header>
          ${fallbackNotice}
          <section class="decisionBlock" data-mode="${escapeHtml(item.tuned.executionMode)}">
            <span class="decisionMark" aria-hidden="true"></span>
            <div>
              <h4 class="decisionTitle">${isCompositor ? "Deterministic compositor · abstention" : "Generative I2V · продолжить"}</h4>
              <p class="decisionText">${escapeHtml(decisionDescription)}</p>
              ${feasibility ? `<p class="decisionNote">Gate: ${escapeHtml(feasibility)}</p>` : ""}
            </div>
          </section>
          <section class="planBlock">
            <h4>Model-specific scene plan</h4>
            <p>${escapeHtml(item.tuned.scenePlan || "Tuned scene plan не передан.")}</p>
          </section>
          ${promptBlock("Tuned prompt", item.tuned.positivePrompt, tunedPromptEmpty)}
          <details class="detailDisclosure">
            <summary>Structured intent и runtime</summary>
            ${renderIntent(intent)}
            <dl class="intentGrid">
              ${inlineFacts([
                ["Duration", finiteNumber(runtime.duration_seconds) === null ? "—" : `${runtime.duration_seconds} с`],
                ["Resolution", firstText(runtime.resolution) || "—"],
                ["Frames / FPS", finiteNumber(runtime.frames) === null ? "—" : `${runtime.frames} / ${runtime.fps || "—"}`],
                ["Audio", runtime.generate_audio === true ? "да" : runtime.generate_audio === false ? "нет" : "—"],
              ])}
            </dl>
          </details>
        </section>
      </section>

      ${reviewEditorMarkup(item)}

      <footer class="caseFootnotes">
        <p>Accepted sibling models: ${escapeHtml(acceptedSiblings)}. Они показаны как относительные контрпримеры, а не gold labels.</p>
        <p class="provenanceLine" data-verified="${verified}">Provenance: ${escapeHtml(provenanceState)} · ${escapeHtml(item.planning.runId || "run —")} · contract ${escapeHtml(state.manifest.contractVersion || "—")}</p>
      </footer>
    `;

    dom.targetView.querySelectorAll("[data-media-video]").forEach((video) => {
      const role = video.dataset.mediaRole;
      const errorMessage = dom.targetView.querySelector(`[data-media-error="${role}"]`);
      video.addEventListener("error", () => {
        video.hidden = true;
        if (errorMessage) errorMessage.hidden = false;
      });
      video.src = video.dataset.mediaSrc;
    });
    const sourceImage = dom.targetView.querySelector("[data-source-image]");
    if (sourceImage) {
      const sourceError = dom.targetView.querySelector("[data-source-error]");
      sourceImage.addEventListener("error", () => {
        sourceImage.hidden = true;
        if (sourceError) sourceError.hidden = false;
      });
    }
    bindReviewEditor(item);
  }

  function showEmptyFilterState() {
    dom.targetView.hidden = true;
    dom.loadState.hidden = false;
    dom.loadState.innerHTML = `
      <p class="loadStateTitle">Нет целей с такими фильтрами</p>
      <p>Сбросьте один или несколько фильтров, чтобы вернуться к выборке.</p>
      <button class="controlButton retryButton" id="clearEmptyFilters" type="button">Сбросить фильтры</button>
    `;
    dom.currentNumber.textContent = "0";
    dom.totalNumber.textContent = "0";
    dom.caseTitle.textContent = "Нет подходящих целей";
    dom.caseMeta.textContent = "Фильтры исключили всю выборку.";
    dom.previousTarget.disabled = true;
    dom.nextTarget.disabled = true;
    dom.targetSelect.disabled = true;
    dom.targetSelect.replaceChildren(new Option("Нет результатов", ""));
  }

  function renderCurrent({ focusTitle = false } = {}) {
    if (!state.filtered.length) {
      showEmptyFilterState();
      return;
    }

    state.currentIndex = Math.min(Math.max(state.currentIndex, 0), state.filtered.length - 1);
    const item = state.filtered[state.currentIndex];
    dom.loadState.hidden = true;
    dom.targetView.hidden = false;
    dom.targetSelect.disabled = false;
    dom.currentNumber.textContent = formatNumber(state.currentIndex + 1);
    dom.totalNumber.textContent = formatNumber(state.filtered.length);
    dom.caseTitle.textContent = item.title;
    dom.caseMeta.textContent = `${item.caseId} · ${item.modelLabel} · строка ${item.sheetRow ?? "—"}`;
    dom.previousTarget.disabled = state.currentIndex === 0;
    dom.nextTarget.disabled = state.currentIndex === state.filtered.length - 1;
    updateTargetSelect(item.id);
    renderItem(item);
    updateUrl(item);
    if (focusTitle) dom.caseTitle.focus({ preventScroll: true });
  }

  function applyCurrentFilters({ preserveId = "", focusTitle = false } = {}) {
    const current = state.filtered[state.currentIndex];
    const selectedId = preserveId || current?.id || "";
    state.filtered = applyFilters(state.items, readFilters());
    const preservedIndex = state.filtered.findIndex((item) => item.id === selectedId);
    const requestedIndex = state.filtered.findIndex(
      (item) =>
        item.caseId === state.requestedCase &&
        (!state.requestedModel || item.modelId === state.requestedModel),
    );
    state.currentIndex = preservedIndex >= 0 ? preservedIndex : requestedIndex >= 0 ? requestedIndex : 0;
    state.requestedCase = "";
    state.requestedModel = "";
    dom.filterResult.textContent = `Показано ${formatNumber(state.filtered.length)} из ${formatNumber(state.items.length)} целей`;
    renderCurrent({ focusTitle });
  }

  function applyQueryState() {
    const query = new URLSearchParams(window.location.search);
    state.requestedCase = cleanText(query.get("case"));
    state.requestedModel = cleanText(query.get("model"));
    const requestedFilters = {
      category: cleanText(query.get("category")),
      mode: cleanText(query.get("mode")),
      rating: cleanText(query.get("rating")),
    };
    Object.entries(requestedFilters).forEach(([key, value]) => {
      const select = dom[`${key}Filter`];
      if (value && [...select.options].some((option) => option.value === value)) {
        select.value = value;
      }
    });
  }

  function showLoadError(error) {
    setControlState(false);
    dom.datasetStatus.dataset.state = "error";
    dom.datasetStatus.textContent = "Tune manifest пока недоступен.";
    dom.loadState.hidden = false;
    dom.targetView.hidden = true;
    dom.loadState.innerHTML = `
      <p class="loadStateTitle">Manifest ещё не готов</p>
      <p>${escapeHtml(error.message || "Не удалось загрузить JSON.")}</p>
      <p>Ожидаемый путь: <code>clipmaker-lite-test/tune-manifest.json</code>.</p>
      <button class="controlButton retryButton" id="retryManifest" type="button">Повторить загрузку</button>
    `;
    dom.caseTitle.textContent = "Tune manifest недоступен";
    dom.caseMeta.textContent = "Демо автоматически оживёт после публикации manifest.";
  }

  async function loadManifest() {
    setControlState(false);
    dom.datasetStatus.dataset.state = "loading";
    dom.datasetStatus.textContent = "Загружаем tune manifest…";
    dom.loadState.hidden = false;
    dom.loadState.innerHTML = `
      <p class="loadStateTitle">Tune manifest загружается</p>
      <p>Ожидаем <code>clipmaker-lite-test/tune-manifest.json</code>.</p>
    `;

    try {
      const response = await fetch(MANIFEST_URL, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}: manifest не опубликован.`);
      const raw = await response.json();
      state.manifest = normalizeManifest(raw);
      state.items = state.manifest.items;
      state.filtered = [];
      state.currentIndex = 0;
      populateFilters();
      applyQueryState();
      updateSummary();
      loadStoredReviews();
      renderReviewOverview();
      setControlState(true);
      const generated = formatDate(state.manifest.generatedAt);
      const tunedAvailable = state.items.filter(
        (item) => tunedVideoState(item.tuned.video, item.tuned.executionMode) === "available",
      ).length;
      dom.datasetStatus.dataset.state = "ready";
      dom.datasetStatus.textContent = [
        state.manifest.ticket || "Tune",
        `${formatNumber(state.manifest.caseCount)} кейсов`,
        `${formatNumber(state.manifest.targetCount)} целей`,
        `${formatNumber(tunedAvailable)} tuned MP4`,
        generated ? `собрано ${generated}` : "",
      ].filter(Boolean).join(" · ");
      applyCurrentFilters();
    } catch (error) {
      showLoadError(error instanceof Error ? error : new Error(String(error)));
    }
  }

  function resetFilters({ focusTitle = true } = {}) {
    dom.filterForm.reset();
    [dom.categoryFilter, dom.modelFilter, dom.modeFilter, dom.ratingFilter].forEach((select) => {
      select.value = "all";
    });
    applyCurrentFilters({ focusTitle });
  }

  function exportReviewJson() {
    if (!state.manifest) return;
    const payload = buildReviewExport(state.manifest, state.reviews);
    if (!payload.summary.saved_entry_count) return;
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
      type: "application/json;charset=utf-8",
    });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const identity = (state.manifest.batchId || state.manifest.ticket || "tune")
      .replace(/[^a-z0-9._-]+/gi, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase();
    anchor.href = href;
    anchor.download = `${identity || "tune"}-evaluation.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 0);
    setStorageStatus(
      `Экспортировано ${formatNumber(payload.evaluations.length)} локальных записей.`,
    );
  }

  dom.filterForm.addEventListener("change", () => applyCurrentFilters());
  dom.resetFilters.addEventListener("click", () => resetFilters());
  dom.exportReviews.addEventListener("click", exportReviewJson);
  dom.targetSelect.addEventListener("change", () => {
    const index = state.filtered.findIndex((item) => item.id === dom.targetSelect.value);
    if (index >= 0) {
      state.currentIndex = index;
      renderCurrent({ focusTitle: true });
    }
  });
  dom.previousTarget.addEventListener("click", () => {
    if (state.currentIndex > 0) {
      state.currentIndex -= 1;
      renderCurrent({ focusTitle: true });
    }
  });
  dom.nextTarget.addEventListener("click", () => {
    if (state.currentIndex < state.filtered.length - 1) {
      state.currentIndex += 1;
      renderCurrent({ focusTitle: true });
    }
  });
  dom.loadState.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("#retryManifest")) loadManifest();
    if (event.target.closest("#clearEmptyFilters")) resetFilters();
  });
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const target = event.target;
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLSelectElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLButtonElement ||
      target instanceof HTMLVideoElement ||
      target instanceof HTMLElement && target.isContentEditable
    ) {
      return;
    }
    if (event.key === "[") dom.previousTarget.click();
    if (event.key === "]") dom.nextTarget.click();
  });

  loadManifest();
})();
