(() => {
  "use strict";

  const BASE_MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";
  const ADDITIONAL_MANIFEST_PATH =
    "../clipmaker-lite-test/promopages-9930-manifest.json";
  const CASE_21_MANIFEST_PATH = "../clipmaker-lite-test/case-21-manifest.json";
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
  const LOOP_MODEL_ID = "alibaba/wan-2.7";
  const LOOP_REQUEST_CLASSIFICATION = "api-loop-closure-experiment";
  const LOOP_REQUEST_MECHANISM = "same-source-first-and-last-frame";
  const LOOP_FRAME_TYPES = ["first_frame", "last_frame"];
  const LOOP_SEAM_PRESENTATION = {
    "seam-passed": "Шов · проверен",
    "seam-failed": "Шов · не прошёл проверку",
    "seam-not-reviewed": "Шов · не проверен",
  };
  const EXPECTED_TOTAL_ARTICLE_COUNT = 21;
  const EXPECTED_UNIQUE_IMAGE_COUNT = 41;
  const EXPECTED_CANONICAL_OUTPUT_COUNT = 123;
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
    videoCountSummary: document.querySelector("#videoCountSummary"),
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

    return [
      {
        ...article,
        images: [
          {
            ...record,
            image,
            outputs,
            research_outputs: researchOutputs,
            displayOutputs,
            loopExperiment,
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
        images: [firstImage, ...additional.images],
      };
    });
    merged.push(...case21Articles);
    assert(
      merged.length === EXPECTED_TOTAL_ARTICLE_COUNT,
      `После объединения найдено кейсов: ${merged.length}, ожидалось 21.`,
    );
    const totalImages = merged.reduce((sum, article) => sum + article.images.length, 0);
    assert(
      totalImages === EXPECTED_UNIQUE_IMAGE_COUNT,
      `После объединения найдено уникальных изображений: ${totalImages}, ожидалось 41.`,
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
      `После объединения найдено canonical роликов: ${canonicalOutputCount}, ожидалось 123.`,
    );
    const canonicalVideoPaths = new Set(
      merged.flatMap((article) =>
        article.images.flatMap((imageRecord) =>
          imageRecord.outputs.map((output) => output.video_path),
        ),
      ),
    );
    assert(
      canonicalVideoPaths.size === EXPECTED_CANONICAL_OUTPUT_COUNT,
      "После объединения canonical MP4 должны быть уникальны.",
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

  const renderModel = (
    article,
    imageRecord,
    output,
    modelIndex,
    { idPrefix = "model", loopPlayback = false, headingLevel = 3 } = {},
  ) => {
    const presentation = MODEL_PRESENTATION[output.model_id];
    assert(presentation, `Нет presentation для ${output.model_id}.`);
    const titleId = `${idPrefix}-${article.article_number}-${imageRecord.image.image_id}-${modelIndex + 1}`;
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
    const panelKind = loopPlayback
      ? "Loop-вариант"
      : output.showcaseLabel
        ? "Вариант"
        : "Модель";
    const headingTag = headingLevel === 4 ? "h4" : "h3";
    const loopAttributes = loopPlayback
      ? `${prefersReducedMotion ? "" : " loop"} muted data-loop-output`
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
            ${loopAttributes}
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
        ])}

        <details class="promptDetails">
          <summary>Дословный positive prompt</summary>
          <p class="promptText" lang="en">${escapeHtml(output.positive_prompt)}</p>
        </details>
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
          <p class="loopExperimentKicker">Wan 2.7 · отдельная исследовательская серия</p>
          <h3 id="loopExperimentTitle">API loop-closure: одинаковый first и last frame</h3>
          <p>
            Это endpoint-conditioning, а не native loop-параметр и не canonical Lite runtime.
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
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${group.name} на паузе.`;
        return;
      }

      pauseAll();
      button.disabled = true;
      elements.navigatorStatus.textContent =
        `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: запускаем ${videoCount} видео — ${group.name}…`;
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
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: браузер не разрешил воспроизвести группу «${group.name}».`;
        return;
      }

      setPlaybackState();
      elements.navigatorStatus.textContent =
        `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${videoCount} видео группы «${group.name}» запущены одновременно без звука.`;
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
        elements.navigatorStatus.textContent = `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: загружено ${ready.size} из ${allVideos.length}, ошибок — ${failed.size}.`;
      } else if (ready.size === allVideos.length) {
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: ${allVideos.length} видео подключены. Серии запускаются отдельно.`;
      } else {
        elements.navigatorStatus.textContent =
          `Кейс ${article.article_number}, изображение ${imageRecord.image.image_id}: загружаем метаданные · ${ready.size} из ${allVideos.length}.`;
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
    const gridClass = displayOutputs.length > MODEL_ORDER.length ? " hasExperiment" : "";
    const multiRowClass = displayOutputs.length >= 6 ? " multiRow" : "";
    const modelCountClass = displayOutputs.length === 2 ? " twoModels" : "";
    const researchSummary = imageRecord.attemptSummary
      ? `<p class="researchSummary"><strong>Полный журнал кейса 21.</strong> Получено ${imageRecord.attemptSummary.available} MP4 из ${imageRecord.attemptSummary.total} запусков; ${imageRecord.attemptSummary.unavailable} запуска завершились без видео. Все семь результатов имеют статус fidelity failed.</p>`
      : "";
    const loopSection = renderLoopSection(article, imageRecord);

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
            data-video-group-control="primary"
            data-play-label="Воспроизвести ${displayOutputs.length} основных"
            data-pause-label="Пауза основных"
            aria-pressed="false"
            aria-describedby="navigatorStatus"
            disabled
          >
            Воспроизвести ${displayOutputs.length} основных
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
      const [baseResponse, additionalResponse, case21Response] = await Promise.all([
        fetch(BASE_MANIFEST_PATH, { cache: "no-store" }),
        fetch(ADDITIONAL_MANIFEST_PATH, { cache: "no-store" }),
        fetch(CASE_21_MANIFEST_PATH, { cache: "no-store" }),
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

      const [baseManifest, additionalManifest, case21Manifest] = await Promise.all([
        baseResponse.json(),
        additionalResponse.json(),
        case21Response.json(),
      ]);
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
      const loopOutputCount =
        case21Articles[0]?.images[0]?.loopExperiment?.outputs.length || 0;
      elements.videoCountSummary.textContent =
        `123 + ${EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT + loopOutputCount}`;
      articles = mergeArticleImages(baseArticles, additionalArticles, case21Articles);
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
