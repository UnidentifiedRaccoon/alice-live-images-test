(() => {
  "use strict";

  const data = window.comparisonData;
  const list = document.querySelector("#comparison-list");

  if (!data || !Array.isArray(data.cases) || !list) {
    if (list) {
      list.innerHTML = `
        <div class="fatal-error" role="alert">
          <strong>Данные сравнения не загрузились.</strong>
          <span>Откройте страницу через локальный сервер и обновите её.</span>
        </div>
      `;
    }
    return;
  }

  const integerFormatter = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 0,
  });
  const twoDecimalFormatter = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const clockSecondsFormatter = new Intl.NumberFormat("ru-RU", {
    minimumIntegerDigits: 2,
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const currencyFormatter = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
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

  const formatNumber = (value, fractionDigits = 0) =>
    new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value);

  const formatMiB = (bytes) => `${twoDecimalFormatter.format(bytes / 1024 / 1024)}\u00a0МиБ`;
  const formatMbps = (bitsPerSecond) =>
    `${twoDecimalFormatter.format(bitsPerSecond / 1_000_000)}\u00a0Мбит/с`;
  const formatMoney = (value) => currencyFormatter.format(value);

  const formatClock = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds - minutes * 60;
    return `${minutes}:${clockSecondsFormatter.format(remainder)}`;
  };

  const listItems = (items) => items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  const renderModel = (model, item) => {
    const titleId = `${item.id}-${model.key}-title`;
    const findingsId = `${item.id}-${model.key}-findings`;
    const source = item.source;

    return `
      <section class="model-panel model-panel--${escapeHtml(model.key)}" aria-labelledby="${titleId}">
        <header class="model-header">
          <div>
            <p class="model-header__provider">${escapeHtml(model.provider)}</p>
            <h3 id="${titleId}">${escapeHtml(model.name)}</h3>
          </div>
          <div class="model-header__meta">
            <strong class="model-header__cost">${formatMoney(model.costUsd)} за ролик</strong>
            <a class="model-download" href="${escapeHtml(model.video)}" download>Скачать MP4</a>
          </div>
        </header>

        <div class="media-shell" data-media-shell>
          <video
            width="${model.final.width}"
            height="${model.final.height}"
            muted
            playsinline
            preload="metadata"
            poster="${escapeHtml(source.path)}"
            tabindex="-1"
            disablepictureinpicture
            data-pair-video
            aria-label="${escapeHtml(model.name)}: результат для ${escapeHtml(source.filename)}, без аудио"
          >
            <source src="${escapeHtml(model.video)}" type="video/mp4" />
            Ваш браузер не поддерживает MP4-видео.
          </video>
          <p class="media-error" data-media-error role="alert">
            Ролик не загрузился. Проверьте путь к MP4.
          </p>
        </div>

        <dl class="metric-strip">
          <div>
            <dt>API-время</dt>
            <dd>${formatClock(model.generationTimeSeconds)}</dd>
          </div>
          <div>
            <dt>Размер</dt>
            <dd>${formatMiB(model.final.sizeBytes)}</dd>
          </div>
          <div>
            <dt>Геометрия</dt>
            <dd>${model.final.width}×${model.final.height}</dd>
          </div>
        </dl>

        <section class="findings" aria-labelledby="${findingsId}">
          <h4 class="findings__label" id="${findingsId}">Основные отклонения</h4>
          <ul>${listItems(model.deviations)}</ul>
        </section>

        <details class="technical-details">
          <summary>
            <span>Технические параметры</span>
            <span class="technical-details__toggle" aria-hidden="true">+</span>
          </summary>
          <div class="technical-details__body">
            <section>
              <h4>Запрос</h4>
              <dl class="technical-list">
                <div><dt>Модель</dt><dd><code>${escapeHtml(model.modelId)}</code></dd></div>
                <div><dt>Провайдер</dt><dd>${escapeHtml(model.provider)}</dd></div>
                <div><dt>Длительность</dt><dd>${formatNumber(model.requestedDurationSeconds)}\u00a0с</dd></div>
                <div><dt>Разрешение</dt><dd>${escapeHtml(model.requestedResolution)}</dd></div>
                <div><dt>Соотношение сторон</dt><dd>${escapeHtml(model.requestedAspectRatio)}</dd></div>
                <div><dt>Seed</dt><dd>${integerFormatter.format(model.seed)}</dd></div>
                <div><dt>Аудио</dt><dd>выключено</dd></div>
                <div><dt>Негативный промпт</dt><dd>${escapeHtml(model.negativePrompt)}</dd></div>
              </dl>
            </section>
            <section>
              <h4>Проверка ffprobe</h4>
              <dl class="technical-list">
                <div><dt>Видео</dt><dd>${escapeHtml(model.final.codec)} · ${escapeHtml(model.final.pixelFormat)}</dd></div>
                <div><dt>Длительность</dt><dd>${formatNumber(model.final.durationSeconds, 3)}\u00a0с</dd></div>
                <div><dt>Частота</dt><dd>${integerFormatter.format(model.final.fps)}\u00a0fps</dd></div>
                <div><dt>Кадры</dt><dd>${integerFormatter.format(model.final.frames)}</dd></div>
                <div><dt>Битрейт</dt><dd>${formatMbps(model.final.bitRate)}</dd></div>
                <div><dt>Аудиопотоки</dt><dd>${model.final.hasAudio ? "есть" : "0"}</dd></div>
                <div><dt>Постобработка</dt><dd>${escapeHtml(model.processing)}</dd></div>
              </dl>
            </section>
            <section class="technical-details__wide">
              <h4>Идентификаторы генерации</h4>
              <dl class="technical-list technical-list--ids">
                <div><dt>Job ID</dt><dd><code>${escapeHtml(model.jobId)}</code></dd></div>
                <div><dt>Generation ID</dt><dd><code>${escapeHtml(model.generationId)}</code></dd></div>
              </dl>
            </section>
            <section class="technical-details__wide review-notes">
              <h4>Визуальная проверка</h4>
              <ul>${listItems(model.review)}</ul>
            </section>
          </div>
        </details>
      </section>
    `;
  };

  const renderCase = (item) => {
    const timelineId = `${item.id}-timeline`;
    const duration = data.common.finalDuration;
    const sourceLabel = `${item.source.width}×${item.source.height} · ${formatMiB(item.source.sizeBytes)}`;

    return `
      <article class="case-study" id="${escapeHtml(item.id)}" data-case>
        <header class="case-header">
          <p class="case-number" aria-hidden="true">${escapeHtml(item.number)}</p>
          <div class="case-copy">
            <p class="eyebrow">Сценарий ${escapeHtml(item.number)}</p>
            <h2>${escapeHtml(item.title)}</h2>
            <p>${escapeHtml(item.task)}</p>
          </div>
        </header>

        <a
          class="source-figure"
          href="${escapeHtml(item.source.path)}"
          aria-label="Открыть исходный кадр ${escapeHtml(item.source.filename)}"
        >
          <img
            src="${escapeHtml(item.source.path)}"
            width="${item.source.width}"
            height="${item.source.height}"
            alt="Исходный кадр: ${escapeHtml(item.title.toLowerCase())}"
            loading="lazy"
            decoding="async"
          />
          <span class="source-figure__caption">
            <span class="source-figure__label">Исходный кадр</span>
            <strong>${escapeHtml(item.source.filename)}</strong>
            <span>${sourceLabel}</span>
            <span class="source-figure__action">Открыть оригинал</span>
          </span>
        </a>

        <div class="pair-controls" aria-label="Синхронное управление парой">
          <p class="pair-status" aria-live="polite" data-state="loading" data-pair-status>
            <span aria-hidden="true"></span>
            <span data-pair-status-text>Загружаем метаданные · 0 из 2</span>
          </p>
          <div class="pair-actions">
            <button
              class="control-button control-button--primary"
              type="button"
              data-pair-play
              aria-pressed="false"
              disabled
            >
              Воспроизвести
            </button>
            <button class="control-button" type="button" data-pair-reset disabled>
              К первому кадру
            </button>
            <button
              class="control-button"
              type="button"
              data-pair-loop
              aria-pressed="false"
              disabled
            >
              Повтор выключен
            </button>
          </div>
          <label class="timeline" for="${timelineId}">
            <span class="timeline__label">Общий таймкод</span>
            <output for="${timelineId}" data-pair-time>${formatClock(0)} / ${formatClock(duration)}</output>
            <input
              id="${timelineId}"
              type="range"
              min="0"
              max="${duration}"
              step="0.01"
              value="0"
              data-pair-scrubber
              aria-valuetext="${formatClock(0)} из ${formatClock(duration)}"
              disabled
            />
          </label>
        </div>

        <div class="model-comparison">
          <div class="model-grid">
            ${item.models.map((model) => renderModel(model, item)).join("")}
          </div>
        </div>
      </article>
    `;
  };

  list.innerHTML = data.cases.map(renderCase).join("");

  const initialisePair = (pair) => {
    const videos = [...pair.querySelectorAll("[data-pair-video]")];
    const playButton = pair.querySelector("[data-pair-play]");
    const resetButton = pair.querySelector("[data-pair-reset]");
    const loopButton = pair.querySelector("[data-pair-loop]");
    const scrubber = pair.querySelector("[data-pair-scrubber]");
    const timeOutput = pair.querySelector("[data-pair-time]");
    const status = pair.querySelector("[data-pair-status]");
    const statusText = pair.querySelector("[data-pair-status-text]");
    const duration = data.common.finalDuration;
    const controls = [playButton, resetButton, loopButton, scrubber];
    const ready = new Set();
    let locked = false;
    let scrubbing = false;
    let loopEnabled = false;

    const setControlsEnabled = (enabled) => {
      controls.forEach((control) => {
        control.disabled = !enabled;
      });
    };

    const setStatus = (message, state = "ready") => {
      statusText.textContent = message;
      status.dataset.state = state;
    };

    const setPlayState = (playing) => {
      playButton.setAttribute("aria-pressed", String(playing));
      playButton.textContent = playing ? "Пауза" : "Воспроизвести";
    };

    const updateTimeline = (currentTime = videos[0]?.currentTime || 0) => {
      const safeTime = Math.min(Math.max(currentTime, 0), duration);
      if (!scrubbing) scrubber.value = safeTime.toFixed(2);
      scrubber.setAttribute("aria-valuetext", `${formatClock(safeTime)} из ${formatClock(duration)}`);
      timeOutput.value = `${formatClock(safeTime)} / ${formatClock(duration)}`;
    };

    const setCurrentTime = (time) => {
      videos.forEach((video) => {
        video.currentTime = time;
      });
    };

    const pauseAll = (message = "Пауза") => {
      locked = true;
      videos.forEach((video) => video.pause());
      locked = false;
      setPlayState(false);
      setStatus(message, "paused");
    };

    const playAll = async (time) => {
      locked = true;
      if (Number.isFinite(time)) setCurrentTime(time);
      setStatus("Запускаем пару…", "loading");

      try {
        const results = await Promise.allSettled(videos.map((video) => video.play()));
        if (results.some((result) => result.status === "rejected")) {
          videos.forEach((video) => video.pause());
          throw new Error("Pair playback failed");
        }
        setPlayState(true);
        setStatus("Синхронное воспроизведение", "playing");
      } catch {
        setPlayState(false);
        setStatus("Браузер заблокировал воспроизведение", "error");
      } finally {
        locked = false;
      }
    };

    playButton.addEventListener("click", () => {
      if (videos.some((video) => !video.paused && !video.ended)) {
        pauseAll();
        return;
      }

      const master = videos[0];
      const restartAt = master.ended || master.currentTime >= duration - 0.04 ? 0 : master.currentTime;
      playAll(restartAt);
    });

    resetButton.addEventListener("click", () => {
      pauseAll("Первый кадр");
      locked = true;
      setCurrentTime(0);
      locked = false;
      updateTimeline(0);
    });

    loopButton.addEventListener("click", () => {
      loopEnabled = !loopEnabled;
      loopButton.setAttribute("aria-pressed", String(loopEnabled));
      loopButton.textContent = loopEnabled ? "Повтор включён" : "Повтор выключен";
      setStatus(loopEnabled ? "Повтор включён" : "Повтор выключен");
    });

    scrubber.addEventListener("input", () => {
      if (videos.some((video) => !video.paused)) pauseAll("Перемотка");
      scrubbing = true;
      const time = Number(scrubber.value);
      locked = true;
      setCurrentTime(time);
      locked = false;
      updateTimeline(time);
    });

    scrubber.addEventListener("change", () => {
      scrubbing = false;
      const time = Number(scrubber.value);
      updateTimeline(time);
      setStatus(`Кадр ${formatClock(time)}`, "paused");
    });

    videos.forEach((video) => {
      const shell = video.closest("[data-media-shell]");

      const markReady = () => {
        ready.add(video);
        if (ready.size === videos.length) {
          setControlsEnabled(true);
          setStatus("Готово · 2 из 2");
        } else {
          setStatus(`Загружаем метаданные · ${ready.size} из ${videos.length}`, "loading");
        }
      };

      if (video.readyState >= 1) {
        markReady();
      } else {
        video.addEventListener("loadedmetadata", markReady, { once: true });
      }

      video.addEventListener("error", () => {
        shell.dataset.state = "error";
        setControlsEnabled(false);
        setStatus("Один из MP4 не загрузился", "error");
      });
    });

    videos[0].addEventListener("timeupdate", () => {
      if (locked || scrubbing) return;
      const masterTime = videos[0].currentTime;
      const peer = videos[1];

      if (!peer.paused && Math.abs(peer.currentTime - masterTime) > 0.12) {
        locked = true;
        peer.currentTime = masterTime;
        locked = false;
      }
      updateTimeline(masterTime);
    });

    videos[0].addEventListener("ended", () => {
      if (locked) return;
      if (loopEnabled) {
        playAll(0);
      } else {
        pauseAll("Просмотр завершён");
        updateTimeline(duration);
      }
    });

    updateTimeline(0);
  };

  document.querySelectorAll("[data-case]").forEach(initialisePair);
})();
