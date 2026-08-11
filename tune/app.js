(() => {
  "use strict";

  const MANIFEST_URL = "../clipmaker-lite-test/tune-manifest.json";
  const RAW_REPOSITORY_BASE =
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/main/";

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
    i2v: "Generative I2V",
    "deterministic-compositor": "Deterministic compositor",
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

  const testHooks = Object.freeze({
    applyFilters,
    encodeRepositoryPath,
    normalizeManifest,
    normalizeRatingState,
    resolveMediaUrl,
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

  function renderItem(item) {
    const sourceUrl = resolveMediaUrl(item.source.url || item.source.path);
    const videoUrl = resolveMediaUrl(
      item.baseline.videoUrl || item.baseline.repositoryVideoPath,
    );
    const sourceDimensions = item.source.width && item.source.height
      ? `${formatNumber(item.source.width)} × ${formatNumber(item.source.height)}`
      : "Размер не указан";
    const media = item.baseline.media;
    const comparisonRatio = mediaRatio(item.source.width, item.source.height);
    const videoDimensions = finiteNumber(media.width) && finiteNumber(media.height)
      ? `${formatNumber(media.width)} × ${formatNumber(media.height)}`
      : "—";
    const videoDuration = finiteNumber(media.duration_seconds);
    const runtime = item.tuned.runtime;
    const intent = item.planning.structuredIntent;
    const strategy = firstText(intent.rendering_strategy);
    const isCompositor = item.tuned.executionMode === "deterministic-compositor";
    const sourceMedia = sourceUrl
      ? `<img data-source-image src="${escapeHtml(sourceUrl)}" alt="${escapeHtml(item.source.caption || item.title)}" decoding="async" /><p class="mediaUnavailable" data-source-error hidden>Исходник не удалось загрузить. Проверьте URL или repository path в manifest.</p>`
      : '<p class="mediaUnavailable">В manifest нет URL или repository path исходника.</p>';
    const baselineMedia = videoUrl
      ? `<video controls playsinline preload="metadata"${sourceUrl ? ` poster="${escapeHtml(sourceUrl)}"` : ""} aria-label="Baseline ${escapeHtml(item.modelLabel)}"></video><p class="mediaUnavailable" data-media-error hidden>Baseline MP4 не удалось загрузить. Проверьте delivery URL в manifest.</p>`
      : '<p class="mediaUnavailable">В manifest нет existing baseline MP4.</p>';
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

      <section class="mediaComparison" aria-label="Исходник и baseline video">
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
                ["Размер", videoDimensions],
                ["Длительность", videoDuration === null ? "—" : `${videoDuration.toFixed(1)} с`],
                ["Вес", formatBytes(media.bytes)],
                ["Звук", media.has_audio === true ? "есть" : media.has_audio === false ? "нет" : "—"],
              ])}
            </dl>
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

      <footer class="caseFootnotes">
        <p>Accepted sibling models: ${escapeHtml(acceptedSiblings)}. Они показаны как относительные контрпримеры, а не gold labels.</p>
        <p class="provenanceLine" data-verified="${verified}">Provenance: ${escapeHtml(provenanceState)} · ${escapeHtml(item.planning.runId || "run —")} · contract ${escapeHtml(state.manifest.contractVersion || "—")}</p>
      </footer>
    `;

    const video = dom.targetView.querySelector("video");
    if (video && videoUrl) {
      const errorMessage = dom.targetView.querySelector("[data-media-error]");
      video.addEventListener("error", () => {
        video.hidden = true;
        if (errorMessage) errorMessage.hidden = false;
      });
      video.src = videoUrl;
    }
    const sourceImage = dom.targetView.querySelector("[data-source-image]");
    if (sourceImage) {
      const sourceError = dom.targetView.querySelector("[data-source-error]");
      sourceImage.addEventListener("error", () => {
        sourceImage.hidden = true;
        if (sourceError) sourceError.hidden = false;
      });
    }
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
      setControlState(true);
      const generated = formatDate(state.manifest.generatedAt);
      dom.datasetStatus.dataset.state = "ready";
      dom.datasetStatus.textContent = [
        state.manifest.ticket || "Tune",
        `${formatNumber(state.manifest.caseCount)} кейсов`,
        `${formatNumber(state.manifest.targetCount)} целей`,
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

  dom.filterForm.addEventListener("change", () => applyCurrentFilters());
  dom.resetFilters.addEventListener("click", () => resetFilters());
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
