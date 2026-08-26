(function () {
  "use strict";

  const MANIFEST_PATH = "../clipmaker-lite-test/wan-3.0-experiment/manifest.json";
  const EXPECTED_ARTICLE_COUNT = 21;
  const EXPECTED_MODEL_ORDER = Object.freeze([
    "google/veo-3.1-lite",
    "alibaba/wan-2.7",
    "alibaba/wan-3.0",
  ]);
  const MODEL_PRESENTATION = Object.freeze({
    "google/veo-3.1-lite": {
      name: "Veo 3.1 Lite",
      eyebrow: "Контрольная модель",
    },
    "alibaba/wan-2.7": {
      name: "Wan 2.7",
      eyebrow: "Предыдущая версия",
    },
    "alibaba/wan-3.0": {
      name: "Wan 3.0",
      eyebrow: "Новый эксперимент",
    },
  });

  const isObject = (value) =>
    value !== null && typeof value === "object" && !Array.isArray(value);

  const hasOwn = (value, key) =>
    Object.prototype.hasOwnProperty.call(value, key);

  const requireCondition = (condition, message) => {
    if (!condition) throw new Error(message);
  };

  const normalizeArticleNumber = (value) =>
    String(value === undefined || value === null ? "" : value).padStart(2, "0");

  const validateManifest = (manifest) => {
    requireCondition(isObject(manifest), "Манифест должен быть JSON-объектом.");
    requireCondition(
      typeof manifest.schema_version === "string" ||
        typeof manifest.schema_version === "number",
      "В манифесте отсутствует schema_version.",
    );
    requireCondition(
      typeof manifest.generated_at === "string" && manifest.generated_at.trim(),
      "В манифесте отсутствует generated_at.",
    );
    requireCondition(
      manifest.article_count === EXPECTED_ARTICLE_COUNT,
      "Ожидалось 21 статья, получено: " + String(manifest.article_count) + ".",
    );
    requireCondition(
      Array.isArray(manifest.model_order) &&
        manifest.model_order.length === EXPECTED_MODEL_ORDER.length &&
        manifest.model_order.every(
          (modelId, index) => modelId === EXPECTED_MODEL_ORDER[index],
        ),
      "model_order не совпадает с контрактом демо.",
    );
    requireCondition(isObject(manifest.summary), "В манифесте отсутствует summary.");
    requireCondition(
      Array.isArray(manifest.articles) &&
        manifest.articles.length === EXPECTED_ARTICLE_COUNT,
      "Массив articles должен содержать ровно 21 запись.",
    );

    const seenSlugs = new Set();
    const seenNumbers = new Set();
    manifest.articles.forEach((article, articleIndex) => {
      const position = articleIndex + 1;
      const expectedNumber = String(position).padStart(2, "0");
      requireCondition(isObject(article), "Статья " + position + " должна быть объектом.");
      requireCondition(
        normalizeArticleNumber(article.number) === expectedNumber,
        "Нарушен порядок статей: ожидался номер " + expectedNumber + ".",
      );
      requireCondition(
        typeof article.slug === "string" && article.slug.trim(),
        "У статьи " + expectedNumber + " отсутствует slug.",
      );
      requireCondition(
        typeof article.title === "string" && article.title.trim(),
        "У статьи " + expectedNumber + " отсутствует title.",
      );
      requireCondition(
        !seenSlugs.has(article.slug),
        "Повторяется slug статьи: " + article.slug + ".",
      );
      requireCondition(
        !seenNumbers.has(expectedNumber),
        "Повторяется номер статьи: " + expectedNumber + ".",
      );
      seenSlugs.add(article.slug);
      seenNumbers.add(expectedNumber);

      const source = article.source_image;
      requireCondition(
        isObject(source),
        "У статьи " + expectedNumber + " отсутствует source_image.",
      );
      requireCondition(
        typeof source.path === "string" && source.path.trim(),
        "У source_image статьи " + expectedNumber + " отсутствует path.",
      );
      requireCondition(
        typeof source.sha256 === "string" &&
          /^[a-f0-9]{64}$/i.test(source.sha256),
        "У source_image статьи " + expectedNumber + " некорректный sha256.",
      );
      requireCondition(
        Number.isFinite(source.width) && source.width > 0,
        "У source_image статьи " + expectedNumber + " некорректная width.",
      );
      requireCondition(
        Number.isFinite(source.height) && source.height > 0,
        "У source_image статьи " + expectedNumber + " некорректная height.",
      );
      requireCondition(
        typeof source.role === "string" && source.role.trim(),
        "У source_image статьи " + expectedNumber + " отсутствует role.",
      );

      requireCondition(
        isObject(article.outputs),
        "У статьи " + expectedNumber + " отсутствует outputs.",
      );
      const outputKeys = Object.keys(article.outputs);
      requireCondition(
        outputKeys.length === EXPECTED_MODEL_ORDER.length &&
          EXPECTED_MODEL_ORDER.every((modelId) => hasOwn(article.outputs, modelId)),
        "У статьи " + expectedNumber + " должен быть результат каждой из трёх моделей.",
      );

      EXPECTED_MODEL_ORDER.forEach((modelId) => {
        const output = article.outputs[modelId];
        const prefix = "Статья " + expectedNumber + ", " + modelId + ": ";
        requireCondition(isObject(output), prefix + "output должен быть объектом.");
        requireCondition(
          typeof output.status === "string" && output.status.trim(),
          prefix + "отсутствует status.",
        );
        requireCondition(
          output.video_path === null ||
            (typeof output.video_path === "string" && output.video_path.trim()),
          prefix + "video_path должен быть строкой или null.",
        );
        requireCondition(isObject(output.prompt), prefix + "отсутствует prompt.");
        requireCondition(
          typeof output.prompt.positive === "string",
          prefix + "prompt.positive должен быть строкой.",
        );
        requireCondition(
          output.prompt.negative === null || typeof output.prompt.negative === "string",
          prefix + "prompt.negative должен быть строкой или null.",
        );
        requireCondition(
          hasOwn(output, "scene_plan") && output.scene_plan !== undefined,
          prefix + "отсутствует scene_plan.",
        );
        requireCondition(
          output.media === null || isObject(output.media),
          prefix + "media должен быть объектом или null.",
        );
        requireCondition(
          hasOwn(output, "verification"),
          prefix + "отсутствует verification.",
        );
        requireCondition(
          hasOwn(output, "visual_review"),
          prefix + "отсутствует visual_review.",
        );
        if (output.status === "succeeded") {
          requireCondition(
            typeof output.video_path === "string" && output.video_path.trim(),
            prefix + "succeeded требует непустой video_path.",
          );
        }
      });
    });

    return manifest;
  };

  const resolveRepoAssetUrl = (repositoryPath, baseUrl) => {
    if (repositoryPath === null || repositoryPath === undefined) return null;
    const rawPath = String(repositoryPath).trim();
    if (!rawPath) return null;
    if (/^(?:https?:|data:|blob:)/i.test(rawPath)) return rawPath;

    const resolvedBase =
      baseUrl ||
      (typeof document !== "undefined"
        ? document.baseURI
        : "https://example.invalid/clipmaker-lite-wan30/");
    const slashNormalizedPath = rawPath.replace(/\\/g, "/");
    if (slashNormalizedPath.indexOf("../") === 0) {
      return new URL(slashNormalizedPath, resolvedBase).href;
    }
    const repositoryRoot = new URL("../", resolvedBase);
    const normalizedPath = slashNormalizedPath
      .replace(/^\.\/+/, "")
      .replace(/^\/+/, "");
    return new URL(normalizedPath, repositoryRoot).href;
  };

  const statusTone = (status, videoPath) => {
    const normalized = String(status || "").toLowerCase();
    if (
      normalized.indexOf("verification-failed") !== -1 ||
      normalized.indexOf("warning") !== -1 ||
      normalized.indexOf("contract-failed") !== -1
    ) {
      return "warning";
    }
    if (
      normalized.indexOf("pending") !== -1 ||
      normalized.indexOf("queued") !== -1 ||
      normalized.indexOf("running") !== -1 ||
      normalized.indexOf("processing") !== -1 ||
      normalized.indexOf("submitted") !== -1 ||
      normalized === "dry-run"
    ) {
      return "pending";
    }
    if (
      normalized.indexOf("failed") !== -1 ||
      normalized.indexOf("error") !== -1 ||
      normalized.indexOf("unavailable") !== -1 ||
      normalized.indexOf("missing") !== -1 ||
      normalized.indexOf("cancel") !== -1 ||
      normalized.indexOf("rejected") !== -1 ||
      normalized.indexOf("unknown") !== -1
    ) {
      return "failed";
    }
    if (
      normalized === "succeeded" ||
      normalized === "completed" ||
      normalized === "verified" ||
      normalized === "available"
    ) {
      return videoPath ? "success" : "missing";
    }
    return videoPath ? "neutral" : "missing";
  };

  const statusLabel = (status, videoPath) => {
    const known = {
      succeeded: "Успешно",
      completed: "Завершено",
      verified: "Проверено",
      "verification-failed": "Есть отклонения",
      "provider-failed": "Ошибка провайдера",
      "submit-unknown": "Submit не подтверждён",
      "dry-run": "Не отправлялся",
      "provider-unavailable": "Провайдер недоступен",
      "lite-result-missing": "Нет Lite result",
      "not-materialized": "Запрос не собран",
      "not-prepared": "Не подготовлено",
      pending: "Ожидает запуска",
      queued: "В очереди",
      running: "Генерируется",
      processing: "Обрабатывается",
      missing: "Отсутствует",
    };
    const normalized = String(status || "").toLowerCase();
    if (known[normalized]) return known[normalized];
    if (!videoPath && !normalized) return "Видео отсутствует";
    return normalized ? normalized.replace(/[-_]+/g, " ") : "Без статуса";
  };

  const keyboardAction = (event) => {
    if (!event || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) {
      return null;
    }
    const target = event.target || {};
    const tagName = String(target.tagName || "").toLowerCase();
    if (
      target.isContentEditable ||
      ["a", "button", "input", "select", "textarea", "summary"].includes(tagName)
    ) {
      return null;
    }
    const key = String(event.key || "");
    const lowerKey = key.toLowerCase();
    if (key === "ArrowLeft") return "previous";
    if (key === "ArrowRight") return "next";
    if (key === " " || key === "Spacebar" || event.code === "Space") return "play-pause";
    if (lowerKey === "r") return "restart";
    if (lowerKey === "m") return "mute";
    return null;
  };

  const publicApi = Object.freeze({
    MANIFEST_PATH,
    EXPECTED_ARTICLE_COUNT,
    EXPECTED_MODEL_ORDER,
    validateManifest,
    resolveRepoAssetUrl,
    statusTone,
    statusLabel,
    keyboardAction,
  });

  if (typeof module !== "undefined" && module.exports) {
    module.exports = publicApi;
    return;
  }
  if (typeof document === "undefined") return;

  const elements = {
    articleCountSummary: document.querySelector("#articleCountSummary"),
    availableCountSummary: document.querySelector("#availableCountSummary"),
    wan30CountSummary: document.querySelector("#wan30CountSummary"),
    datasetSourceStatus: document.querySelector("#datasetSourceStatus"),
    manifestSummary: document.querySelector("#manifestSummary"),
    currentNumber: document.querySelector("#currentNumber"),
    totalNumber: document.querySelector("#totalNumber"),
    caseTitle: document.querySelector("#caseTitle"),
    caseMeta: document.querySelector("#caseMeta"),
    previousCase: document.querySelector("#previousCase"),
    nextCase: document.querySelector("#nextCase"),
    caseSelect: document.querySelector("#caseSelect"),
    playPause: document.querySelector("#playPause"),
    restartVideos: document.querySelector("#restartVideos"),
    muteVideos: document.querySelector("#muteVideos"),
    navigatorStatus: document.querySelector("#navigatorStatus"),
    datasetError: document.querySelector("#datasetError"),
    datasetErrorText: document.querySelector("#datasetErrorText"),
    comparisonViewport: document.querySelector("#comparisonViewport"),
    comparisonGrid: document.querySelector("#comparisonGrid"),
  };

  if (Object.values(elements).some((element) => !element)) return;

  const state = {
    manifest: null,
    articles: [],
    index: 0,
    muted: true,
  };
  const numberFormatter = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  });
  const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const createElement = (tagName, className, text) => {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  };

  const safeDateLabel = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : dateFormatter.format(date);
  };

  const formatBytes = (value) => {
    if (!Number.isFinite(value) || value < 0) return "—";
    if (value < 1024) return numberFormatter.format(value) + " Б";
    if (value < 1024 * 1024) {
      return numberFormatter.format(value / 1024) + " КБ";
    }
    return numberFormatter.format(value / (1024 * 1024)) + " МБ";
  };

  const formatDuration = (value) =>
    Number.isFinite(value) ? numberFormatter.format(value) + " с" : "—";

  const basename = (value) => {
    const parts = String(value || "").split("/");
    return parts[parts.length - 1] || "—";
  };

  const shortHash = (value) =>
    typeof value === "string" && value.length > 12
      ? value.slice(0, 12) + "…"
      : String(value || "—");

  const activeVideos = () =>
    Array.from(elements.comparisonGrid.querySelectorAll("video[data-synced-video]"));

  const anyVideoPlaying = () =>
    activeVideos().some((video) => !video.paused && !video.ended);

  const updateTransportControls = () => {
    const videos = activeVideos();
    const disabled = videos.length === 0;
    elements.playPause.disabled = disabled;
    elements.restartVideos.disabled = disabled;
    elements.muteVideos.disabled = disabled;

    const playing = !disabled && anyVideoPlaying();
    elements.playPause.textContent = playing ? "Пауза" : "Воспроизвести";
    elements.playPause.setAttribute(
      "aria-label",
      playing
        ? "Приостановить все доступные видео"
        : "Синхронно воспроизвести все доступные видео",
    );
    elements.playPause.setAttribute("aria-pressed", String(playing));
    elements.muteVideos.textContent = state.muted ? "Включить звук" : "Выключить звук";
    elements.muteVideos.setAttribute("aria-pressed", String(state.muted));
    elements.muteVideos.setAttribute(
      "aria-label",
      state.muted ? "Включить звук во всех видео" : "Выключить звук во всех видео",
    );
  };

  const pauseVideos = () => {
    activeVideos().forEach((video) => video.pause());
    updateTransportControls();
  };

  const alignVideoTimes = (videos, targetTime) => {
    videos.forEach((video) => {
      try {
        video.currentTime = targetTime;
      } catch (_error) {
        // Metadata may not be ready yet. Playback remains available.
      }
    });
  };

  const playVideos = () => {
    const videos = activeVideos();
    if (!videos.length) {
      elements.navigatorStatus.textContent = "У этого кейса нет доступных видео.";
      return;
    }
    const reference = videos.find((video) => !video.ended) || videos[0];
    const targetTime = reference.ended ? 0 : reference.currentTime || 0;
    alignVideoTimes(videos, targetTime);
    const playResults = videos.map((video) => {
      try {
        return Promise.resolve(video.play());
      } catch (error) {
        return Promise.reject(error);
      }
    });
    Promise.allSettled(playResults).then((results) => {
      const started = results.filter((result) => result.status === "fulfilled").length;
      elements.navigatorStatus.textContent =
        started === videos.length
          ? "Синхронно воспроизводятся " + started + " видео."
          : "Запущено видео: " + started + " из " + videos.length + ".";
      updateTransportControls();
    });
    updateTransportControls();
  };

  const togglePlayback = () => {
    if (anyVideoPlaying()) {
      pauseVideos();
      elements.navigatorStatus.textContent = "Все видео приостановлены.";
    } else {
      playVideos();
    }
  };

  const restartVideos = () => {
    const videos = activeVideos();
    if (!videos.length) {
      elements.navigatorStatus.textContent = "У этого кейса нет доступных видео.";
      return;
    }
    const keepPlaying = anyVideoPlaying();
    alignVideoTimes(videos, 0);
    if (keepPlaying) {
      videos.forEach((video) => {
        try {
          const result = video.play();
          if (result && typeof result.catch === "function") result.catch(() => {});
        } catch (_error) {
          // The status below still confirms that the timeline was reset.
        }
      });
    }
    elements.navigatorStatus.textContent = "Все доступные видео возвращены к началу.";
    updateTransportControls();
  };

  const toggleMute = () => {
    state.muted = !state.muted;
    activeVideos().forEach((video) => {
      video.muted = state.muted;
    });
    elements.navigatorStatus.textContent = state.muted
      ? "Звук выключен во всех видео."
      : "Звук включён во всех видео.";
    updateTransportControls();
  };

  const appendFacts = (panel, facts) => {
    const list = createElement("dl", "mediaFacts");
    facts.forEach(([label, value]) => {
      const row = createElement("div");
      row.append(createElement("dt", "", label), createElement("dd", "", value));
      list.append(row);
    });
    panel.append(list);
  };

  const appendDetailSection = (container, title, value, emptyText) => {
    const section = createElement("section", "detailSection");
    section.append(createElement("h4", "", title));
    if (value === null || value === undefined || value === "") {
      section.append(createElement("p", "", emptyText || "Нет данных."));
    } else if (typeof value === "string") {
      section.append(createElement("p", "", value));
    } else {
      section.append(createElement("pre", "", JSON.stringify(value, null, 2)));
    }
    container.append(section);
  };

  const createDetails = (summaryText, sections) => {
    const details = createElement("details", "panelDetails");
    details.append(createElement("summary", "", summaryText));
    const body = createElement("div", "detailBody");
    sections.forEach((section) => {
      appendDetailSection(body, section[0], section[1], section[2]);
    });
    details.append(body);
    return details;
  };

  const verificationLabel = (verification) => {
    if (verification === null || verification === undefined) return "Не проводилась";
    if (typeof verification === "string") return verification;
    if (!isObject(verification)) return "Есть запись";
    if (verification.conforms === true) return "Контракт соблюдён";
    if (verification.conforms === false) return "Есть отклонения";
    if (typeof verification.status === "string") {
      return statusLabel(verification.status, true);
    }
    return "Есть запись";
  };

  const visualReviewSummary = (review) => {
    if (review === null || review === undefined) return "Визуальный ревью не выполнен.";
    if (typeof review === "string") return review || "Визуальный ревью не выполнен.";
    if (!isObject(review)) return "Визуальный ревью сохранён в манифесте.";
    return (
      review.summary ||
      review.notes ||
      review.comment ||
      (review.status ? "Визуальный ревью: " + review.status + "." : null) ||
      "Визуальный ревью сохранён в манифесте."
    );
  };

  const visualReviewTone = (review) => {
    if (!isObject(review)) return "neutral";
    return statusTone(review.status || "", true);
  };

  const createIdentity = (eyebrow, title, technicalId, badgeText, badgeTone) => {
    const identity = createElement("header", "panelIdentity");
    const copy = createElement("div");
    copy.append(createElement("p", "panelKicker", eyebrow));
    copy.append(createElement("h3", "", title));
    if (technicalId) copy.append(createElement("code", "modelId", technicalId));
    const badge = createElement("span", "statusBadge", badgeText);
    badge.dataset.tone = badgeTone || "neutral";
    identity.append(copy, badge);
    return identity;
  };

  const createSourcePanel = (article) => {
    const source = article.source_image;
    const panel = createElement("article", "mediaPanel sourcePanel");
    panel.setAttribute("aria-label", "Исходное изображение");
    panel.append(
      createIdentity(
        "First frame",
        "Исходник",
        null,
        source.role,
        "neutral",
      ),
    );

    const stage = createElement("div", "mediaStage");
    const sourceUrl = resolveRepoAssetUrl(source.path);
    const link = createElement("a", "sourceLink");
    link.href = sourceUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.setAttribute(
      "aria-label",
      "Открыть исходное изображение для статьи " + article.title,
    );
    const image = createElement("img");
    image.src = sourceUrl;
    image.alt = "Исходное изображение: " + article.title;
    image.decoding = "async";
    image.addEventListener("error", () => {
      const error = createElement(
        "p",
        "mediaError",
        "Исходное изображение не загрузилось.",
      );
      stage.append(error);
    });
    link.append(image);
    stage.append(link);
    panel.append(stage);

    appendFacts(panel, [
      ["Размер", source.width + "×" + source.height],
      ["Роль", source.role],
      ["Файл", basename(source.path)],
      ["SHA-256", shortHash(source.sha256)],
    ]);
    panel.append(
      createDetails("Источник и контрольная сумма", [
        ["Путь в репозитории", source.path],
        ["SHA-256", source.sha256],
      ]),
    );
    return panel;
  };

  const createMissingStage = (output) => {
    const stage = createElement("div", "mediaStage");
    const tone = statusTone(output.status, output.video_path);
    const empty = createElement(
      "p",
      "emptyState",
      tone === "pending"
        ? "Видео ещё не готово. Статус обновится в манифесте."
        : "Видео отсутствует. Смотрите статус и проверку ниже.",
    );
    empty.dataset.tone = tone === "failed" || tone === "missing" ? "failed" : "neutral";
    stage.append(empty);
    return stage;
  };

  const createVideoStage = (article, modelId, output) => {
    const stage = createElement("div", "mediaStage");
    const video = createElement("video");
    video.src = resolveRepoAssetUrl(output.video_path);
    video.preload = "metadata";
    video.playsInline = true;
    video.muted = state.muted;
    video.dataset.syncedVideo = modelId;
    video.tabIndex = 0;
    video.setAttribute(
      "aria-label",
      MODEL_PRESENTATION[modelId].name + ": видео для статьи " + article.title,
    );

    const error = createElement("p", "mediaError", "MP4 не загрузился.");
    error.hidden = true;
    video.addEventListener("error", () => {
      error.hidden = false;
      elements.navigatorStatus.textContent =
        MODEL_PRESENTATION[modelId].name + ": файл MP4 недоступен.";
      updateTransportControls();
    });
    ["play", "pause", "ended", "loadedmetadata"].forEach((eventName) => {
      video.addEventListener(eventName, updateTransportControls);
    });
    stage.append(video, error);
    return stage;
  };

  const mediaFactsForOutput = (output) => {
    const media = output.media;
    if (!isObject(media)) {
      return [
        ["Медиа", "Нет метаданных"],
        ["Проверка", verificationLabel(output.verification)],
      ];
    }
    const dimensions =
      Number.isFinite(media.width) && Number.isFinite(media.height)
        ? media.width + "×" + media.height
        : "—";
    const fps = Number.isFinite(media.fps)
      ? numberFormatter.format(media.fps) + " fps"
      : "—";
    const audio =
      typeof media.has_audio === "boolean"
        ? media.has_audio
          ? "есть"
          : "нет"
        : "—";
    return [
      ["Размер", dimensions],
      ["Длительность", formatDuration(media.duration_seconds)],
      ["Частота", fps],
      ["Аудио", audio],
      ["Вес", formatBytes(media.bytes)],
      ["Кодек", media.codec || media.container || "—"],
      ["Кадры", Number.isFinite(media.frames) ? media.frames : "—"],
      ["Проверка", verificationLabel(output.verification)],
    ];
  };

  const createModelPanel = (article, modelId, output) => {
    const presentation = MODEL_PRESENTATION[modelId];
    const panel = createElement("article", "mediaPanel modelPanel");
    panel.dataset.modelId = modelId;
    panel.dataset.status = output.status;
    panel.setAttribute("aria-label", presentation.name);
    const tone = statusTone(output.status, output.video_path);
    panel.append(
      createIdentity(
        presentation.eyebrow,
        presentation.name,
        modelId,
        statusLabel(output.status, output.video_path),
        tone,
      ),
    );
    panel.append(
      output.video_path
        ? createVideoStage(article, modelId, output)
        : createMissingStage(output),
    );
    appendFacts(panel, mediaFactsForOutput(output));

    const review = createElement(
      "p",
      "reviewNote",
      visualReviewSummary(output.visual_review),
    );
    review.dataset.tone = visualReviewTone(output.visual_review);
    panel.append(review);
    panel.append(
      createDetails("Промпт и сцена", [
        ["Позитивный промпт", output.prompt.positive, "Не задан."],
        ["Негативный промпт", output.prompt.negative, "Не задан."],
        ["План сцены", output.scene_plan, "Не задан."],
      ]),
      createDetails("Проверка и визуальный ревью", [
        ["Verification", output.verification, "Не проводилась."],
        ["Visual review", output.visual_review, "Не проводился."],
      ]),
    );
    return panel;
  };

  const articleAvailability = (article) =>
    EXPECTED_MODEL_ORDER.filter((modelId) => article.outputs[modelId].video_path)
      .length;

  const updateUrl = (article) => {
    if (!window.history || typeof window.history.replaceState !== "function") return;
    const url = new URL(window.location.href);
    url.searchParams.set("case", normalizeArticleNumber(article.number));
    window.history.replaceState({}, "", url);
  };

  const renderArticle = () => {
    pauseVideos();
    const article = state.articles[state.index];
    if (!article) return;

    const articleNumber = normalizeArticleNumber(article.number);
    elements.currentNumber.textContent = articleNumber;
    elements.totalNumber.textContent = state.articles.length;
    elements.caseTitle.textContent = article.title;
    elements.caseMeta.textContent =
      article.slug +
      " · " +
      article.source_image.role +
      " · " +
      article.source_image.width +
      "×" +
      article.source_image.height;
    elements.caseSelect.value = String(state.index);
    elements.previousCase.disabled = state.index === 0;
    elements.nextCase.disabled = state.index === state.articles.length - 1;

    elements.comparisonGrid.replaceChildren();
    elements.comparisonGrid.append(createSourcePanel(article));
    EXPECTED_MODEL_ORDER.forEach((modelId) => {
      elements.comparisonGrid.append(
        createModelPanel(article, modelId, article.outputs[modelId]),
      );
    });
    elements.comparisonViewport.setAttribute("aria-busy", "false");
    elements.comparisonViewport.scrollLeft = 0;

    const available = articleAvailability(article);
    const warnings = EXPECTED_MODEL_ORDER.filter(
      (modelId) =>
        statusTone(
          article.outputs[modelId].status,
          article.outputs[modelId].video_path,
        ) === "warning",
    ).length;
    const failures = EXPECTED_MODEL_ORDER.length - available;
    elements.navigatorStatus.textContent =
      "Кейс " +
      articleNumber +
      " из " +
      state.articles.length +
      " · MP4 " +
      available +
      " из 3" +
      (warnings ? " · с отклонениями " + warnings : "") +
      (failures ? " · отсутствуют " + failures : "");
    activeVideos().forEach((video) => {
      video.muted = state.muted;
    });
    updateTransportControls();
    updateUrl(article);
  };

  const setIndex = (nextIndex, focusTitle) => {
    const boundedIndex = Math.max(0, Math.min(state.articles.length - 1, nextIndex));
    if (boundedIndex === state.index && state.articles.length) return;
    state.index = boundedIndex;
    renderArticle();
    if (focusTitle) elements.caseTitle.focus({ preventScroll: true });
  };

  const populateSelector = () => {
    elements.caseSelect.replaceChildren();
    state.articles.forEach((article, index) => {
      const option = createElement(
        "option",
        "",
        normalizeArticleNumber(article.number) + " · " + article.title,
      );
      option.value = String(index);
      elements.caseSelect.append(option);
    });
    elements.caseSelect.disabled = false;
  };

  const selectInitialIndex = () => {
    const requested = new URL(window.location.href).searchParams.get("case");
    if (!requested) return 0;
    const normalized = normalizeArticleNumber(requested);
    const index = state.articles.findIndex(
      (article) => normalizeArticleNumber(article.number) === normalized,
    );
    return index >= 0 ? index : 0;
  };

  const renderManifestSummary = () => {
    const totalOutputs = state.articles.length * EXPECTED_MODEL_ORDER.length;
    const availableOutputs = state.articles.reduce(
      (count, article) => count + articleAvailability(article),
      0,
    );
    const wan30Available = state.articles.filter(
      (article) => article.outputs["alibaba/wan-3.0"].video_path,
    ).length;
    elements.articleCountSummary.textContent = state.articles.length;
    elements.availableCountSummary.textContent =
      availableOutputs + "/" + totalOutputs;
    elements.wan30CountSummary.textContent =
      wan30Available + "/" + state.articles.length;
    elements.manifestSummary.textContent = JSON.stringify(
      state.manifest.summary,
      null,
      2,
    );
    elements.datasetSourceStatus.textContent =
      "Схема " +
      state.manifest.schema_version +
      " · сформировано " +
      safeDateLabel(state.manifest.generated_at);
  };

  const showFatalError = (error) => {
    pauseVideos();
    elements.datasetError.hidden = false;
    elements.datasetErrorText.textContent =
      error instanceof Error ? error.message : String(error);
    elements.comparisonViewport.hidden = true;
    elements.comparisonViewport.setAttribute("aria-busy", "false");
    elements.datasetSourceStatus.textContent = "Манифест не прошёл проверку.";
    elements.navigatorStatus.textContent = "Сравнение недоступно.";
  };

  const loadManifest = async () => {
    try {
      const response = await fetch(MANIFEST_PATH, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(
          "Не удалось загрузить " +
            MANIFEST_PATH +
            ": HTTP " +
            response.status +
            ".",
        );
      }
      const manifest = validateManifest(await response.json());
      state.manifest = manifest;
      state.articles = manifest.articles;
      state.index = selectInitialIndex();
      populateSelector();
      renderManifestSummary();
      renderArticle();
    } catch (error) {
      showFatalError(error);
    }
  };

  elements.previousCase.addEventListener("click", () => setIndex(state.index - 1));
  elements.nextCase.addEventListener("click", () => setIndex(state.index + 1));
  elements.caseSelect.addEventListener("change", () => {
    setIndex(Number(elements.caseSelect.value));
  });
  elements.playPause.addEventListener("click", togglePlayback);
  elements.restartVideos.addEventListener("click", restartVideos);
  elements.muteVideos.addEventListener("click", toggleMute);

  document.addEventListener("keydown", (event) => {
    const action = keyboardAction(event);
    if (!action) return;
    event.preventDefault();
    if (action === "previous") setIndex(state.index - 1, true);
    if (action === "next") setIndex(state.index + 1, true);
    if (action === "play-pause") togglePlayback();
    if (action === "restart") restartVideos();
    if (action === "mute") toggleMute();
  });

  loadManifest();
})();
