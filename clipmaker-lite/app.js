(() => {
  "use strict";

  const MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";
  const EXPECTED_ARTICLE_COUNT = 20;
  const EXPECTED_OUTPUT_COUNT = 60;
  const MODEL_ORDER = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
  ];
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
  };

  const elements = {
    currentNumber: document.querySelector("#currentNumber"),
    totalNumber: document.querySelector("#totalNumber"),
    caseTitle: document.querySelector("#caseTitle"),
    previousCase: document.querySelector("#previousCase"),
    nextCase: document.querySelector("#nextCase"),
    caseSelect: document.querySelector("#caseSelect"),
    navigatorStatus: document.querySelector("#navigatorStatus"),
    datasetError: document.querySelector("#datasetError"),
    datasetErrorText: document.querySelector("#datasetErrorText"),
    caseViewport: document.querySelector("#caseViewport"),
  };

  const missingElement = Object.values(elements).some((element) => !element);
  if (missingElement) return;

  const numberFormatter = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  });

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

  const asAssetUrl = (repositoryPath) => `../${String(repositoryPath).replace(/^\/+/, "")}`;

  const formatDuration = (seconds) => `${numberFormatter.format(seconds)}\u00a0с`;
  const formatMiB = (bytes) => `${numberFormatter.format(bytes / 1024 / 1024)}\u00a0МиБ`;

  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };

  const validateManifest = (manifest) => {
    assert(manifest && typeof manifest === "object", "Манифест имеет неверный формат.");
    assert(
      manifest.article_count === EXPECTED_ARTICLE_COUNT,
      `В манифесте заявлено статей: ${manifest.article_count ?? "—"}, ожидалось 20.`,
    );
    assert(Array.isArray(manifest.articles), "В манифесте нет списка articles.");
    assert(
      manifest.articles.length === EXPECTED_ARTICLE_COUNT,
      `Найдено статей: ${manifest.articles.length}, ожидалось 20.`,
    );
    assert(Array.isArray(manifest.outputs), "В манифесте нет общего списка outputs.");
    assert(
      manifest.outputs.length === EXPECTED_OUTPUT_COUNT,
      `Найдено роликов: ${manifest.outputs.length}, ожидалось 60.`,
    );

    const expectedNumbers = Array.from({ length: EXPECTED_ARTICLE_COUNT }, (_, index) =>
      String(index + 1).padStart(2, "0"),
    );
    const videoPaths = new Set();
    let promptCount = 0;

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
        assert(output.video_path, `У ${article.article_number} / ${modelId} нет MP4.`);
        assert(
          typeof output.positive_prompt === "string" && output.positive_prompt.trim(),
          `У ${article.article_number} / ${modelId} пустой positive prompt.`,
        );
        assert(
          Number(output.media?.width) > 0 && Number(output.media?.height) > 0,
          `У ${article.article_number} / ${modelId} нет геометрии видео.`,
        );
        assert(
          Number(output.media?.duration_seconds) > 0 && Number(output.media?.bytes) > 0,
          `У ${article.article_number} / ${modelId} нет метаданных видео.`,
        );
        videoPaths.add(output.video_path);
        promptCount += 1;
      });
    });

    assert(videoPaths.size === EXPECTED_OUTPUT_COUNT, "Пути выбранных MP4 повторяются.");
    assert(promptCount === EXPECTED_OUTPUT_COUNT, "Проверены не все 60 positive prompts.");

    return manifest.articles.map((article) => {
      const outputsByModel = new Map(article.outputs.map((output) => [output.model_id, output]));
      return {
        ...article,
        outputs: MODEL_ORDER.map((modelId) => outputsByModel.get(modelId)),
      };
    });
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

  const renderSource = (article) => {
    const image = article.selected_image;
    const imageUrl = asAssetUrl(image.source_path);
    const imageFile = image.file || image.source_path.split("/").pop();
    const panelId = `sourcePanel-${article.article_number}`;
    const titleId = `sourceTitle-${article.article_number}`;

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
          ["Геометрия", `${image.width}×${image.height}`],
        ])}
      </article>
    `;
  };

  const renderModel = (article, output, modelIndex) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    const titleId = `model-${article.article_number}-${modelIndex + 1}`;
    const videoUrl = asAssetUrl(output.video_path);

    return `
      <article class="mediaPanel modelPanel" aria-labelledby="${titleId}">
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
            aria-label="${escapeHtml(presentation.name)}: результат для статьи «${escapeHtml(article.title)}»"
          >
            Ваш браузер не поддерживает MP4-видео.
          </video>
          <p class="mediaError" data-media-error hidden>
            Ролик не загрузился. Проверьте путь к MP4.
          </p>
        </div>

        <div class="panelIdentity">
          <div>
            <p class="panelKicker">Модель ${String(modelIndex + 1).padStart(2, "0")}</p>
            <h3 id="${titleId}">${escapeHtml(presentation.name)}</h3>
            <code class="modelId">${escapeHtml(output.model_id)}</code>
          </div>
          <strong class="modelCost">
            ${escapeHtml(presentation.cost)}
            <span>за ролик</span>
          </strong>
        </div>

        ${renderFacts([
          ["Длительность", formatDuration(output.media.duration_seconds)],
          ["Геометрия", `${output.media.width}×${output.media.height}`],
          ["Размер", formatMiB(output.media.bytes)],
        ])}

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
      </article>
    `;
  };

  let articles = [];
  let activeIndex = 0;
  let renderSequence = 0;

  const detachCurrentVideos = () => {
    elements.caseViewport.querySelectorAll("video").forEach((video) => {
      video.pause();
      video.removeAttribute("src");
      video.load();
    });
  };

  const updateUrl = (articleNumber) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("case", articleNumber);
      window.history.replaceState(null, "", url);
    } catch {
      // The comparison remains usable when history is unavailable (for example file://).
    }
  };

  const monitorSelectedVideos = (article, sequence) => {
    const videos = [...elements.caseViewport.querySelectorAll("video")];
    const playAllButton = elements.caseViewport.querySelector("[data-play-all]");
    const sourceToggle = elements.caseViewport.querySelector("[data-source-toggle]");
    const sourcePanel = elements.caseViewport.querySelector("[data-source-panel]");
    const ready = new Set();
    const failed = new Set();

    const setPlaybackState = () => {
      if (!playAllButton || sequence !== renderSequence) return;
      const anyPlaying = videos.some((video) => !video.paused && !video.ended);
      playAllButton.setAttribute("aria-pressed", String(anyPlaying));
      playAllButton.textContent = anyPlaying ? "Пауза всех" : "Воспроизвести все";
    };

    const pauseAll = () => {
      videos.forEach((video) => video.pause());
      setPlaybackState();
    };

    const playAll = async () => {
      if (!playAllButton || playAllButton.disabled) return;

      if (videos.some((video) => !video.paused && !video.ended)) {
        pauseAll();
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}: три видео на паузе.`;
        return;
      }

      playAllButton.disabled = true;
      elements.navigatorStatus.textContent = `Кейс ${article.article_number}: запускаем три видео…`;
      videos.forEach((video) => {
        video.pause();
        video.currentTime = 0;
      });
      // Keep all play() calls in the original click gesture so media with audio is allowed.
      const results = await Promise.allSettled(videos.map((video) => video.play()));
      if (sequence !== renderSequence) return;

      playAllButton.disabled = false;
      if (results.some((result) => result.status === "rejected")) {
        pauseAll();
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}: браузер не разрешил общее воспроизведение.`;
        return;
      }

      setPlaybackState();
      elements.navigatorStatus.textContent =
        `Кейс ${article.article_number}: три видео запущены одновременно.`;
    };

    const announce = () => {
      if (sequence !== renderSequence) return;

      const complete = ready.size + failed.size === videos.length;
      elements.caseViewport.setAttribute("aria-busy", String(!complete));
      if (playAllButton) {
        playAllButton.disabled = !complete || failed.size > 0;
      }

      if (failed.size > 0) {
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}: загружено ${ready.size} из 3, ошибок — ${failed.size}.`;
      } else if (ready.size === videos.length) {
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}: три видео подключены. Остальные 57 не загружаются.`;
      } else {
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}: загружаем метаданные · ${ready.size} из 3.`;
      }
    };

    videos.forEach((video) => {
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

    playAllButton?.addEventListener("click", playAll);
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

  const renderCase = (index) => {
    const nextIndex = Math.min(Math.max(index, 0), articles.length - 1);
    const article = articles[nextIndex];
    const sequence = ++renderSequence;

    detachCurrentVideos();
    activeIndex = nextIndex;
    elements.currentNumber.textContent = article.article_number;
    elements.totalNumber.textContent = String(articles.length);
    elements.caseTitle.textContent = article.title;
    elements.caseSelect.value = article.article_number;
    elements.previousCase.disabled = activeIndex === 0;
    elements.nextCase.disabled = activeIndex === articles.length - 1;
    elements.caseViewport.setAttribute("aria-busy", "true");
    elements.caseViewport.innerHTML = `
      <div class="comparisonWorkspace">
        <div class="comparisonActions" aria-label="Управление сравнением">
          <button
            class="controlButton strong"
            type="button"
            data-play-all
            aria-pressed="false"
            aria-describedby="navigatorStatus"
            disabled
          >
            Воспроизвести все
          </button>
          <button
            class="controlButton"
            type="button"
            data-source-toggle
            aria-expanded="false"
            aria-controls="sourcePanel-${article.article_number}"
          >
            Показать оригинал
          </button>
        </div>
        ${renderSource(article)}
        <div class="modelGrid">
          ${article.outputs
            .map((output, modelIndex) => renderModel(article, output, modelIndex))
            .join("")}
        </div>
      </div>
    `;

    updateUrl(article.article_number);
    monitorSelectedVideos(article, sequence);
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
      const response = await fetch(MANIFEST_PATH, { cache: "no-store" });
      if (!response.ok) throw new Error(`Манифест вернул HTTP ${response.status}.`);

      const manifest = await response.json();
      articles = validateManifest(manifest);
      elements.caseSelect.replaceChildren(
        ...articles.map(
          (article) =>
            new Option(`${article.article_number} · ${article.title}`, article.article_number),
        ),
      );
      elements.caseSelect.disabled = false;
      elements.previousCase.disabled = false;
      elements.nextCase.disabled = false;

      const requestedCase = new URL(window.location.href).searchParams.get("case");
      const requestedIndex = articles.findIndex(
        (article) => article.article_number === requestedCase,
      );
      renderCase(requestedIndex >= 0 ? requestedIndex : 0);
    } catch (error) {
      showError(error instanceof Error ? error : new Error("Неизвестная ошибка данных."));
    }
  };

  elements.previousCase.addEventListener("click", () => renderCase(activeIndex - 1));
  elements.nextCase.addEventListener("click", () => renderCase(activeIndex + 1));
  elements.caseSelect.addEventListener("change", () => {
    const selectedIndex = articles.findIndex(
      (article) => article.article_number === elements.caseSelect.value,
    );
    if (selectedIndex >= 0) renderCase(selectedIndex);
  });

  initialise();
})();
