(() => {
  "use strict";

  const BATCH_ID = "promopages-live-images-20260813-v1";
  const MANIFEST_URL =
    "../clipmaker-lite-test/reviews/promopages-live-images-20260813-v1.json";
  const MODELS = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
  ];
  const MODEL_LABELS = {
    "alibaba/wan-2.2": "Wan 2.2",
    "alibaba/wan-2.7": "Wan 2.7",
    "google/veo-3.1-lite": "Veo 3.1 Lite",
  };
  const MODEL_FOLDERS = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
  };
  const PUBLIC_BASE_URL =
    "https://yastatic.net/s3/promopages-front-bundles/";
  const ARTICLE_CONTRACTS = {
    "6a4f5fe924801975680d9be5": {
      brand: "Банки.ру",
      title: "В каких банках можно выгодно купить доллар?",
      imageId: "01",
      mediaId: "6a4f718952e3ce75a3110deb",
      width: 2000,
      height: 1125,
      sourceUrl:
        "https://avatars.mds.yandex.net/get-promoarticles/5126709/pub_6a4f5fe924801975680d9be5_6a4f718952e3ce75a3110deb/orig",
      cabinetPath: "banki-ru__5b0fb7c448c85e2421e049ab",
    },
    "6a048ddca495b52c9d873940": {
      brand: "Level Group",
      title: "Брать ипотеку в II половине 2026 года? Отвечают эксперты",
      imageId: "04",
      mediaId: "6a049156a495b52c9d87cb75",
      width: 1920,
      height: 1023,
      sourceUrl:
        "https://avatars.mds.yandex.net/get-promoarticles/6165752/pub_6a048ddca495b52c9d873940_6a049156a495b52c9d87cb75/orig",
      cabinetPath: "level-group__69ee06293ba10e0ae4b765d1",
    },
  };

  const isObject = (value) =>
    value !== null && typeof value === "object" && !Array.isArray(value);
  const isNonEmptyString = (value) =>
    typeof value === "string" && value.trim().length > 0;
  const isSha256 = (value) =>
    typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  const arraysEqual = (left, right) =>
    Array.isArray(left) &&
    Array.isArray(right) &&
    left.length === right.length &&
    left.every((value, index) => value === right[index]);

  const assert = (condition, message) => {
    if (!condition) {
      throw new Error(message);
    }
  };

  const validatePrompt = (prompt, label) => {
    assert(isObject(prompt), `${label}: промпт отсутствует`);
    assert(isNonEmptyString(prompt.positive), `${label}: positive prompt пуст`);
    assert(typeof prompt.negative === "string", `${label}: negative prompt не строка`);
  };

  const validateAttempt = (attempt, label) => {
    assert(isObject(attempt), `${label}: попытка должна быть объектом`);
    assert(isNonEmptyString(attempt.attempt_id), `${label}: attempt_id пуст`);
    assert(isNonEmptyString(attempt.status), `${label}: status попытки пуст`);
    validatePrompt(attempt.prompt, `${label}/${attempt.attempt_id}`);
    assert(
      attempt.provider_run_id === null || isNonEmptyString(attempt.provider_run_id),
      `${label}: provider_run_id некорректен`,
    );
    assert(
      attempt.error === null || isNonEmptyString(attempt.error),
      `${label}: error попытки некорректен`,
    );
  };

  const expectedVideoUrl = (article, contract, output) => {
    const prefix =
      `${PUBLIC_BASE_URL}front-images/exp_video/${contract.cabinetPath}/` +
      `${article.publication_id}/${MODEL_FOLDERS[output.model_id]}/`;
    const suffix =
      `image_${contract.imageId}--sha256-${output.media.sha256.slice(0, 12)}.mp4`;
    return prefix + suffix;
  };

  const validateOutput = (article, contract, output, index) => {
    const label = `${article.publication_id}/${contract.imageId}/${MODELS[index]}`;
    assert(isObject(output), `${label}: output должен быть объектом`);
    assert(output.model_id === MODELS[index], `${label}: нарушен порядок моделей`);
    assert(
      output.status === "succeeded" || output.status === "unavailable",
      `${label}: неизвестный статус`,
    );
    assert(
      Number.isInteger(output.attempt_count) && output.attempt_count > 0,
      `${label}: attempt_count должен быть положительным`,
    );
    assert(
      Array.isArray(output.attempts) &&
        output.attempts.length === output.attempt_count,
      `${label}: история попыток неполна`,
    );
    output.attempts.forEach((attempt) => validateAttempt(attempt, label));
    const attemptIds = output.attempts.map((attempt) => attempt.attempt_id);
    assert(new Set(attemptIds).size === attemptIds.length, `${label}: attempt_id повторяется`);

    if (output.status === "unavailable") {
      assert(output.selected_attempt_id === null, `${label}: выбранная попытка недопустима`);
      assert(output.selected_prompt === null, `${label}: выбранный промпт недопустим`);
      assert(output.video_url === null, `${label}: unavailable содержит video_url`);
      assert(output.media === null, `${label}: unavailable содержит media`);
      assert(output.contract_check === null, `${label}: unavailable содержит contract_check`);
      assert(isNonEmptyString(output.error), `${label}: причина недоступности пуста`);
      return;
    }

    assert(isNonEmptyString(output.selected_attempt_id), `${label}: нет выбранной попытки`);
    const selectedAttempt = output.attempts.find(
      (attempt) => attempt.attempt_id === output.selected_attempt_id,
    );
    assert(selectedAttempt, `${label}: выбранная попытка отсутствует в истории`);
    assert(selectedAttempt.status === "succeeded", `${label}: выбрана неуспешная попытка`);
    validatePrompt(output.selected_prompt, `${label}/selected_prompt`);
    assert(
      output.selected_prompt.positive === selectedAttempt.prompt.positive &&
        output.selected_prompt.negative === selectedAttempt.prompt.negative,
      `${label}: выбранный промпт расходится с попыткой`,
    );
    assert(isObject(output.media), `${label}: media отсутствует`);
    assert(isSha256(output.media.sha256), `${label}: sha256 некорректен`);
    for (const field of ["bytes", "width", "height", "duration_seconds"]) {
      assert(
        typeof output.media[field] === "number" && output.media[field] > 0,
        `${label}: media.${field} некорректен`,
      );
    }
    assert(isObject(output.contract_check), `${label}: contract_check отсутствует`);
    assert(output.contract_check.conforms === true, `${label}: MP4 не прошёл контракт`);
    assert(
      Array.isArray(output.contract_check.warnings),
      `${label}: contract warnings отсутствуют`,
    );
    assert(output.error === null, `${label}: успешный output содержит error`);
    assert(
      output.video_url === expectedVideoUrl(article, contract, output),
      `${label}: yastatic URL не соответствует S3-маршруту и хешу`,
    );
  };

  const validateManifest = (manifest) => {
    assert(isObject(manifest), "Манифест должен быть объектом");
    assert(manifest.schema_version === 1, "Неподдерживаемая версия манифеста");
    assert(
      manifest.manifest_role === "clipmaker-lite-public-review",
      "Неверная роль манифеста",
    );
    assert(manifest.batch_id === BATCH_ID, "Неверный batch_id");
    assert(isObject(manifest.producer), "Producer отсутствует");
    assert(manifest.producer.agent_id === "clipmaker-lite", "Неверный producer agent");
    assert(
      manifest.producer.contract_version === "2.1.4" &&
        manifest.producer.runner_version === 8,
      "Неверная версия Clipmaker Lite",
    );
    assert(arraysEqual(manifest.models, MODELS), "Список моделей неканоничен");
    assert(
      manifest.article_count === 2 &&
        manifest.image_count === 2 &&
        manifest.expected_outputs === 6,
      "Объявленные счётчики неверны",
    );
    assert(Array.isArray(manifest.articles) && manifest.articles.length === 2, "Нужны две статьи");

    const seenArticles = new Set();
    let outputCount = 0;
    manifest.articles.forEach((article) => {
      assert(isObject(article), "Статья должна быть объектом");
      const contract = ARTICLE_CONTRACTS[article.publication_id];
      assert(contract, `Неизвестная публикация: ${article.publication_id}`);
      assert(!seenArticles.has(article.publication_id), "Публикация повторяется");
      seenArticles.add(article.publication_id);
      assert(article.brand === contract.brand, `${article.publication_id}: неверный бренд`);
      assert(article.title === contract.title, `${article.publication_id}: неверный заголовок`);
      assert(
        isNonEmptyString(article.article_url) &&
          article.article_url.startsWith("https://") &&
          article.article_url.includes(article.publication_id),
        `${article.publication_id}: article_url не привязан к публикации`,
      );
      assert(isObject(article.image), `${article.publication_id}: image отсутствует`);
      const image = article.image;
      assert(
        image.image_id === contract.imageId &&
          image.media_id === contract.mediaId &&
          image.width === contract.width &&
          image.height === contract.height &&
          image.source_url === contract.sourceUrl &&
          typeof image.caption === "string",
        `${article.publication_id}: источник не соответствует контракту`,
      );
      assert(isObject(image.provenance), `${article.publication_id}: provenance отсутствует`);
      assert(
        image.provenance.verified === true &&
          image.provenance.agent_id === "clipmaker-lite" &&
          image.provenance.contract_version === "2.1.4" &&
          image.provenance.runner_version === 8,
        `${article.publication_id}: provenance не подтверждён`,
      );
      assert(
        Array.isArray(image.outputs) && image.outputs.length === MODELS.length,
        `${article.publication_id}: нужны три модели`,
      );
      image.outputs.forEach((output, index) =>
        validateOutput(article, contract, output, index),
      );
      outputCount += image.outputs.length;
    });
    assert(
      seenArticles.size === Object.keys(ARTICLE_CONTRACTS).length,
      "Набор публикаций неполон",
    );
    assert(outputCount === manifest.expected_outputs, "Число outputs не совпадает");
    return manifest;
  };

  const escapeHtml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const formatBytes = (value) => {
    if (!Number.isFinite(value) || value <= 0) return "—";
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} КБ`;
    return `${(value / (1024 * 1024)).toFixed(1)} МБ`;
  };

  const formatAttemptHistory = (attempts) =>
    attempts
      .map((attempt, index) => {
        const provider = attempt.provider_run_id
          ? ` · run ${attempt.provider_run_id}`
          : "";
        const error = attempt.error ? ` · ${attempt.error}` : "";
        return [
          `${index + 1}. ${attempt.attempt_id} · ${attempt.status}${provider}${error}`,
          `Positive: ${attempt.prompt.positive}`,
          `Negative: ${attempt.prompt.negative || "—"}`,
        ].join("\n");
      })
      .join("\n\n");

  const renderFacts = (facts) =>
    `<dl class="mediaFacts">${facts
      .map(
        ([term, value]) =>
          `<div><dt>${escapeHtml(term)}</dt><dd>${escapeHtml(value)}</dd></div>`,
      )
      .join("")}</dl>`;

  const renderPromptDetails = (output) => {
    if (!output.selected_prompt) {
      return `
        <details class="promptDetails">
          <summary>История попыток</summary>
          <p class="promptText">${escapeHtml(formatAttemptHistory(output.attempts))}</p>
        </details>`;
    }
    return `
      <details class="promptDetails">
        <summary>Выбранный промпт</summary>
        <p class="promptText">${escapeHtml(
          `Positive: ${output.selected_prompt.positive}\n\n` +
            `Negative: ${output.selected_prompt.negative || "—"}`,
        )}</p>
      </details>
      <details class="promptDetails">
        <summary>Все попытки · ${output.attempt_count}</summary>
        <p class="promptText">${escapeHtml(formatAttemptHistory(output.attempts))}</p>
      </details>`;
  };

  const renderOutput = (output, sourceUrl) => {
    const label = MODEL_LABELS[output.model_id];
    if (output.status === "unavailable") {
      return `
        <article class="mediaPanel modelPanel providerFilteredPanel" data-output-kind="provider-filtered">
          <div class="mediaStage providerFilteredStage">
            <div class="providerFilteredMessage">
              <p class="providerFilteredKicker">Недоступно</p>
              <strong>Подходящего MP4 нет</strong>
              <p>${escapeHtml(output.error)}</p>
            </div>
          </div>
          <header class="panelIdentity">
            <div>
              <span class="panelKicker">Модель · недоступно</span>
              <h3>${escapeHtml(label)}</h3>
              <span class="modelId">${escapeHtml(output.model_id)}</span>
            </div>
          </header>
          ${renderFacts([
            ["Попытки", String(output.attempt_count)],
            ["Статус", "Недоступно"],
          ])}
          ${renderPromptDetails(output)}
        </article>`;
    }

    const media = output.media;
    return `
      <article class="mediaPanel modelPanel" data-output-kind="comparison">
        <div class="mediaStage" style="--media-aspect: ${media.width} / ${media.height}">
          <video
            controls
            playsinline
            preload="metadata"
            poster="${escapeHtml(sourceUrl)}"
            src="${escapeHtml(output.video_url)}"
            aria-label="${escapeHtml(`Видео ${label}`)}"
          ></video>
        </div>
        <header class="panelIdentity">
          <div>
            <span class="panelKicker">Модель · готово</span>
            <h3>${escapeHtml(label)}</h3>
            <span class="modelId">${escapeHtml(output.model_id)}</span>
          </div>
        </header>
        <p class="publicVideoLink">
          <a class="publicVideoOpen" href="${escapeHtml(output.video_url)}" target="_blank" rel="noopener noreferrer">
            Открыть MP4 ↗
          </a>
        </p>
        ${renderFacts([
          ["Попытки", String(output.attempt_count)],
          ["Размер", `${media.width}×${media.height}`],
          ["Длительность", `${media.duration_seconds.toFixed(2)} с`],
          ["Файл", formatBytes(media.bytes)],
          ["SHA-256", media.sha256.slice(0, 12)],
          ["Контракт", "Пройден"],
        ])}
        ${renderPromptDetails(output)}
      </article>`;
  };

  const renderArticle = (article) => {
    const image = article.image;
    return `
      <div class="comparisonWorkspace">
        <article class="mediaPanel sourcePanel">
          <a class="mediaStage mediaStageLink" href="${escapeHtml(
            image.source_url,
          )}" target="_blank" rel="noopener noreferrer" style="--media-aspect: ${
            image.width
          } / ${image.height}">
            <img src="${escapeHtml(image.source_url)}" alt="${escapeHtml(
              image.caption || `Исходное изображение ${article.brand}`,
            )}" />
          </a>
          <header class="panelIdentity">
            <div>
              <span class="panelKicker">Исходник · изображение ${escapeHtml(
                image.image_id,
              )}</span>
              <h3>${escapeHtml(article.brand)}</h3>
              <span class="modelId">media ${escapeHtml(image.media_id)}</span>
            </div>
          </header>
          ${renderFacts([
            ["Размер", `${image.width}×${image.height}`],
            ["Provenance", "verified"],
            ["Contract", image.provenance.contract_version],
            ["Runner", String(image.provenance.runner_version)],
          ])}
        </article>
        <div class="modelGrid">
          ${image.outputs.map((output) => renderOutput(output, image.source_url)).join("")}
        </div>
      </div>`;
  };

  const parseSelection = (manifest, search) => {
    const parameters = new URLSearchParams(search);
    const requestedBatch = parameters.get("batch");
    if (requestedBatch && requestedBatch !== BATCH_ID) {
      throw new Error(`Неизвестный batch: ${requestedBatch}`);
    }
    const requestedCase = parameters.get("case");
    const index = requestedCase
      ? manifest.articles.findIndex(
          (article) => article.publication_id === requestedCase,
        )
      : 0;
    if (requestedCase && index < 0) {
      throw new Error(`Публикация ${requestedCase} отсутствует в batch`);
    }
    const article = manifest.articles[Math.max(index, 0)];
    const requestedImage = parameters.get("image");
    if (requestedImage && requestedImage !== article.image.image_id) {
      throw new Error(
        `Изображение ${requestedImage} отсутствует в публикации ${article.publication_id}`,
      );
    }
    return Math.max(index, 0);
  };

  const testHooks = Object.freeze({
    validateManifest,
    parseSelection,
    expectedVideoUrl,
    escapeHtml,
    constants: Object.freeze({ BATCH_ID, MANIFEST_URL, MODELS }),
  });
  globalThis.__generationReviewTestHooks = testHooks;

  const start = async () => {
    const elements = {
      sourceStatus: document.querySelector("#datasetSourceStatus"),
      articleCount: document.querySelector("#articleCountSummary"),
      imageCount: document.querySelector("#imageCountSummary"),
      modelCount: document.querySelector("#modelCountSummary"),
      currentNumber: document.querySelector("#currentNumber"),
      totalNumber: document.querySelector("#totalNumber"),
      caseTitle: document.querySelector("#caseTitle"),
      caseMeta: document.querySelector("#caseDatasetMeta"),
      previous: document.querySelector("#previousCase"),
      next: document.querySelector("#nextCase"),
      select: document.querySelector("#caseSelect"),
      status: document.querySelector("#navigatorStatus"),
      error: document.querySelector("#datasetError"),
      errorText: document.querySelector("#datasetErrorText"),
      viewport: document.querySelector("#caseViewport"),
    };

    try {
      const response = await fetch(MANIFEST_URL, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} при загрузке манифеста`);
      }
      const manifest = validateManifest(await response.json());
      let currentIndex = parseSelection(manifest, window.location.search);

      elements.articleCount.textContent = String(manifest.article_count);
      elements.imageCount.textContent = String(manifest.image_count);
      elements.modelCount.textContent = String(manifest.models.length);
      elements.totalNumber.textContent = String(manifest.articles.length);
      elements.sourceStatus.textContent =
        `Batch ${manifest.batch_id} · contract ${manifest.producer.contract_version} · ` +
        `runner ${manifest.producer.runner_version}`;
      elements.select.innerHTML = manifest.articles
        .map(
          (article, index) =>
            `<option value="${index}">${escapeHtml(article.brand)} — ${escapeHtml(
              article.title,
            )}</option>`,
        )
        .join("");
      elements.select.disabled = false;

      const show = (nextIndex, { focusTitle = false } = {}) => {
        currentIndex = nextIndex;
        const article = manifest.articles[currentIndex];
        elements.currentNumber.textContent = String(currentIndex + 1);
        elements.caseTitle.textContent = article.title;
        elements.caseMeta.textContent =
          `${article.brand} · публикация ${article.publication_id} · изображение ${article.image.image_id}`;
        elements.select.value = String(currentIndex);
        elements.previous.disabled = currentIndex === 0;
        elements.next.disabled = currentIndex === manifest.articles.length - 1;
        elements.status.textContent =
          `${article.image.outputs.filter((output) => output.status === "succeeded").length} из 3 моделей доступны`;
        elements.viewport.innerHTML = renderArticle(article);
        elements.viewport.setAttribute("aria-busy", "false");

        const url = new URL(window.location.href);
        url.searchParams.set("batch", BATCH_ID);
        url.searchParams.set("case", article.publication_id);
        url.searchParams.set("image", article.image.image_id);
        window.history.replaceState(null, "", url);
        if (focusTitle) elements.caseTitle.focus({ preventScroll: true });
      };

      elements.previous.addEventListener("click", () => {
        if (currentIndex > 0) show(currentIndex - 1, { focusTitle: true });
      });
      elements.next.addEventListener("click", () => {
        if (currentIndex < manifest.articles.length - 1) {
          show(currentIndex + 1, { focusTitle: true });
        }
      });
      elements.select.addEventListener("change", () => {
        show(Number(elements.select.value), { focusTitle: true });
      });
      show(currentIndex);
    } catch (error) {
      elements.sourceStatus.textContent = "Манифест не прошёл проверку";
      elements.error.hidden = false;
      elements.errorText.textContent = error instanceof Error ? error.message : String(error);
      elements.viewport.setAttribute("aria-busy", "false");
      elements.viewport.innerHTML = "";
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
