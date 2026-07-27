(() => {
  "use strict";

  const BASE_MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";
  const ADDITIONAL_MANIFEST_PATH =
    "../clipmaker-lite-test/promopages-9930-manifest.json";
  const EXPECTED_ARTICLE_COUNT = 20;
  const EXPECTED_BASE_OUTPUT_COUNT = 60;
  const EXPECTED_ADDITIONAL_IMAGE_COUNT = 20;
  const EXPECTED_ADDITIONAL_OUTPUT_COUNT = 60;
  const EXPECTED_UNIQUE_IMAGE_COUNT = 40;
  const EXPECTED_CANONICAL_OUTPUT_COUNT = 120;
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

  const validateBaseManifest = (manifest) => {
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
      manifest.outputs.length === EXPECTED_BASE_OUTPUT_COUNT,
      `Найдено роликов: ${manifest.outputs.length}, ожидалось 60.`,
    );

    const expectedNumbers = Array.from({ length: EXPECTED_ARTICLE_COUNT }, (_, index) =>
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
      if (!hasOwn(article, "comparison_outputs")) {
        return { ...article, outputs: normalizedOutputs, displayOutputs: normalizedOutputs };
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
      manifest.article_count === EXPECTED_ARTICLE_COUNT,
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
      Array.isArray(manifest.articles) && manifest.articles.length === EXPECTED_ARTICLE_COUNT,
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

  const mergeArticleImages = (baseArticles, additionalArticles) => {
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
        images: [firstImage, ...additional.images],
      };
    });
    const totalImages = merged.reduce((sum, article) => sum + article.images.length, 0);
    assert(
      totalImages === EXPECTED_UNIQUE_IMAGE_COUNT,
      `После объединения найдено уникальных изображений: ${totalImages}, ожидалось 40.`,
    );
    const canonicalOutputCount = merged.reduce(
      (articleTotal, article) =>
        articleTotal +
        article.images.reduce(
          (imageTotal, imageRecord) => imageTotal + imageRecord.outputs.length,
          0,
        ),
      0,
    );
    assert(
      canonicalOutputCount === EXPECTED_CANONICAL_OUTPUT_COUNT,
      `После объединения найдено canonical роликов: ${canonicalOutputCount}, ожидалось 120.`,
    );
    return merged;
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
    const panelId = `sourcePanel-${article.article_number}-${image.image_id}`;
    const titleId = `sourceTitle-${article.article_number}-${image.image_id}`;

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
          ["Позиция", image.role || "изображение статьи"],
          ["Геометрия", `${image.width}×${image.height}`],
        ])}
      </article>
    `;
  };

  const renderModel = (article, imageRecord, output, modelIndex) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    assert(presentation, `Нет presentation для ${output.model_id}.`);
    const titleId = `model-${article.article_number}-${imageRecord.image.image_id}-${modelIndex + 1}`;
    const videoUrl = asAssetUrl(output.video_path, output.delivery);
    const promptLabel = output.showcaseLabel
      ? `<p class="promptLabel">${escapeHtml(output.showcaseLabel)}</p>`
      : "";
    const variant = output.showcaseVariant || "canonical";
    const accessibleVariant = output.showcaseLabel ? ` · ${output.showcaseLabel}` : "";
    const contractWarning =
      output.status === "verification-failed"
        ? '<p class="contractWarning">Raw output · media contract warning</p>'
        : "";
    const fidelityWarning =
      output.visual_review?.status === "fidelity-failed"
        ? `<p class="contractWarning fidelityWarning"><strong>Visual review · fidelity failed.</strong> ${escapeHtml(output.visual_review.summary)}</p>`
        : "";

    return `
      <article
        class="mediaPanel modelPanel"
        data-output-kind="${escapeHtml(variant)}"
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
            aria-label="${escapeHtml(presentation.name + accessibleVariant)}: результат для статьи «${escapeHtml(article.title)}»"
          >
            Ваш браузер не поддерживает MP4-видео.
          </video>
          <p class="mediaError" data-media-error hidden>
            Ролик не загрузился. Проверьте путь к MP4.
          </p>
        </div>

        <div class="panelIdentity">
          <div>
            ${promptLabel}
            ${contractWarning}
            ${fidelityWarning}
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
          ...(output.route_label
            ? [["Маршрут", output.route_label]]
            : []),
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

  const updateUrl = (articleNumber, imageId) => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("case", articleNumber);
      url.searchParams.set("image", imageId);
      window.history.replaceState(null, "", url);
    } catch {
      // The comparison remains usable when history is unavailable (for example file://).
    }
  };

  const monitorSelectedVideos = (article, imageRecord, sequence) => {
    const videos = [...elements.caseViewport.querySelectorAll("video")];
    const videoCount = videos.length;
    const playAllButton = elements.caseViewport.querySelector("[data-play-all]");
    const sourceToggle = elements.caseViewport.querySelector("[data-source-toggle]");
    const sourcePanel = elements.caseViewport.querySelector("[data-source-panel]");
    const ready = new Set();
    const failed = new Set();
    const mutedBeforeCoordinatedPlayback = new Map();
    let coordinatedPlaybackActive = false;

    const restoreCoordinatedMuteState = () => {
      if (!coordinatedPlaybackActive) return;
      videos.forEach((video) => {
        if (mutedBeforeCoordinatedPlayback.has(video)) {
          video.muted = mutedBeforeCoordinatedPlayback.get(video);
        }
      });
      mutedBeforeCoordinatedPlayback.clear();
      coordinatedPlaybackActive = false;
    };

    const muteCoordinatedPlayback = () => {
      restoreCoordinatedMuteState();
      videos.forEach((video) => {
        mutedBeforeCoordinatedPlayback.set(video, video.muted);
        video.muted = true;
      });
      coordinatedPlaybackActive = true;
    };

    const setPlaybackState = () => {
      if (!playAllButton || sequence !== renderSequence) return;
      const anyPlaying = videos.some((video) => !video.paused && !video.ended);
      if (!anyPlaying) restoreCoordinatedMuteState();
      playAllButton.setAttribute("aria-pressed", String(anyPlaying));
      playAllButton.textContent = anyPlaying ? "Пауза всех" : "Воспроизвести все";
    };

    const pauseAll = () => {
      videos.forEach((video) => video.pause());
      restoreCoordinatedMuteState();
      setPlaybackState();
    };

    const playAll = async () => {
      if (!playAllButton || playAllButton.disabled) return;

      if (videos.some((video) => !video.paused && !video.ended)) {
        pauseAll();
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${videoCount} видео на паузе.`;
        return;
      }

      playAllButton.disabled = true;
      elements.navigatorStatus.textContent =
        `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: запускаем ${videoCount} видео…`;
      videos.forEach((video) => {
        video.pause();
        video.currentTime = 0;
      });
      // A coordinated comparison is visual: prevent provider audio tracks from overlapping.
      muteCoordinatedPlayback();
      // Keep all play() calls in the original click gesture for consistent browser behavior.
      const results = await Promise.allSettled(videos.map((video) => video.play()));
      if (sequence !== renderSequence) return;

      playAllButton.disabled = false;
      if (results.some((result) => result.status === "rejected")) {
        pauseAll();
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: браузер не разрешил общее воспроизведение.`;
        return;
      }

      setPlaybackState();
      elements.navigatorStatus.textContent =
        `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${videoCount} видео запущены одновременно без звука.`;
    };

    const announce = () => {
      if (sequence !== renderSequence) return;

      const complete = ready.size + failed.size === videos.length;
      elements.caseViewport.setAttribute("aria-busy", String(!complete));
      if (playAllButton) {
        playAllButton.disabled = !complete || failed.size > 0;
      }

      if (failed.size > 0) {
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: загружено ${ready.size} из ${videoCount}, ошибок — ${failed.size}.`;
      } else if (ready.size === videos.length) {
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${videoCount} видео подключены. Другие изображения не загружаются.`;
      } else {
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: загружаем метаданные · ${ready.size} из ${videoCount}.`;
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

  const renderSelection = () => {
    const article = articles[activeIndex];
    const imageRecord = article.images[activeImageIndex];
    const sequence = ++renderSequence;
    const displayOutputs = imageRecord.displayOutputs || imageRecord.outputs;
    const gridClass = displayOutputs.length > MODEL_ORDER.length ? " hasExperiment" : "";
    const sixModelsClass = displayOutputs.length === 6 ? " sixModels" : "";
    const modelCountClass = displayOutputs.length === 2 ? " twoModels" : "";

    detachCurrentVideos();
    elements.currentNumber.textContent = article.article_number;
    elements.totalNumber.textContent = String(articles.length);
    elements.caseTitle.textContent = article.title;
    elements.caseSelect.value = article.article_number;
    elements.previousCase.disabled = activeIndex === 0;
    elements.nextCase.disabled = activeIndex === articles.length - 1;
    elements.currentImageNumber.textContent = String(activeImageIndex + 1);
    elements.totalImageNumber.textContent = String(article.images.length);
    elements.imageSelect.value = imageRecord.image.image_id;
    elements.previousImage.disabled = activeImageIndex === 0;
    elements.nextImage.disabled = activeImageIndex === article.images.length - 1;
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
            aria-controls="sourcePanel-${article.article_number}-${imageRecord.image.image_id}"
          >
            Показать оригинал
          </button>
        </div>
        ${renderSource(article, imageRecord)}
        <div class="modelGrid${modelCountClass}${gridClass}${sixModelsClass}">
          ${displayOutputs
            .map((output, modelIndex) => renderModel(article, imageRecord, output, modelIndex))
            .join("")}
        </div>
      </div>
    `;

    rememberedImageByArticle.set(article.article_number, activeImageIndex);
    updateUrl(article.article_number, imageRecord.image.image_id);
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

    const requestedIndex = requestedImageId
      ? article.images.findIndex((record) => record.image.image_id === requestedImageId)
      : -1;
    const rememberedIndex = rememberedImageByArticle.get(article.article_number) ?? 0;
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
      const [baseResponse, additionalResponse] = await Promise.all([
        fetch(BASE_MANIFEST_PATH, { cache: "no-store" }),
        fetch(ADDITIONAL_MANIFEST_PATH, { cache: "no-store" }),
      ]);
      if (!baseResponse.ok) {
        throw new Error(`Базовый манифест вернул HTTP ${baseResponse.status}.`);
      }
      if (!additionalResponse.ok) {
        throw new Error(
          `Манифест PROMOPAGES-9930 вернул HTTP ${additionalResponse.status}.`,
        );
      }

      const [baseManifest, additionalManifest] = await Promise.all([
        baseResponse.json(),
        additionalResponse.json(),
      ]);
      const baseArticles = validateBaseManifest(baseManifest);
      const additionalArticles = validateAdditionalManifest(
        additionalManifest,
        baseArticles,
      );
      articles = mergeArticleImages(baseArticles, additionalArticles);
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
      const requestedImage = new URL(window.location.href).searchParams.get("image");
      const requestedIndex = articles.findIndex(
        (article) => article.article_number === requestedCase,
      );
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
      (article) => article.article_number === elements.caseSelect.value,
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
