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

  const formatMiB = (bytes) => `${(bytes / 1024 / 1024).toFixed(2)} MiB`;
  const formatMbps = (bitsPerSecond) => `${(bitsPerSecond / 1_000_000).toFixed(2)} Mbps`;
  const formatMoney = (value) => `$${value.toFixed(2)}`;

  const formatClock = (seconds, precise = true) => {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds - minutes * 60;
    return `${minutes}:${remainder.toFixed(precise ? 1 : 0).padStart(precise ? 4 : 2, "0")}`;
  };

  const listItems = (items) => items.map((item) => `<li>${item}</li>`).join("");

  const renderModel = (model, source) => `
    <section class="model-panel model-panel--${model.key}" aria-labelledby="${source.filename}-${model.key}-title">
      <header class="model-header">
        <div>
          <p class="model-header__provider">${model.provider}</p>
          <h3 id="${source.filename}-${model.key}-title">${model.name}</h3>
        </div>
        <span class="model-header__cost">${formatMoney(model.costUsd)} / ролик</span>
      </header>

      <div class="media-shell" data-media-shell>
        <video
          controls
          muted
          playsinline
          preload="metadata"
          poster="${source.path}"
          data-pair-video
          aria-label="${model.name}: результат для ${source.filename}, без аудиодорожки"
        >
          <source src="${model.video}" type="video/mp4" />
          Ваш браузер не поддерживает MP4-видео.
        </video>
        <div class="media-stamp" aria-hidden="true">
          <span>Final</span>
          <span>5.000 s</span>
          <span>30 fps</span>
          <span>Без аудио</span>
        </div>
        <a class="media-download" href="${model.video}" download>
          Скачать MP4
          <span aria-hidden="true">↓</span>
        </a>
        <p class="media-error" data-media-error role="alert">
          Ролик не загрузился. Проверьте относительный путь к MP4.
        </p>
      </div>

      <dl class="metric-strip">
        <div>
          <dt>API-время</dt>
          <dd>${formatClock(model.generationTimeSeconds)}</dd>
        </div>
        <div>
          <dt>Финал</dt>
          <dd>${formatMiB(model.final.sizeBytes)}</dd>
        </div>
        <div>
          <dt>Геометрия</dt>
          <dd>${model.final.width}×${model.final.height}</dd>
        </div>
        <div>
          <dt>Битрейт</dt>
          <dd>${formatMbps(model.final.bitRate)}</dd>
        </div>
      </dl>

      <div class="findings">
        <p class="findings__label">Основные отклонения</p>
        <ul>${listItems(model.deviations)}</ul>
      </div>

      <details class="technical-details">
        <summary>
          <span>Параметры, проверка и ID</span>
          <span class="technical-details__toggle" aria-hidden="true">+</span>
        </summary>
        <div class="technical-details__body">
          <section>
            <h4>Запрос</h4>
            <dl class="technical-list">
              <div><dt>Модель</dt><dd><code>${model.modelId}</code></dd></div>
              <div><dt>Провайдер</dt><dd>${model.provider}</dd></div>
              <div><dt>Длительность</dt><dd>${model.requestedDurationSeconds} с</dd></div>
              <div><dt>Разрешение</dt><dd>${model.requestedResolution}</dd></div>
              <div><dt>Aspect ratio</dt><dd>${model.requestedAspectRatio}</dd></div>
              <div><dt>Seed</dt><dd>${model.seed}</dd></div>
              <div><dt>Аудио</dt><dd>выключено</dd></div>
              <div><dt>Negative prompt</dt><dd>${model.negativePrompt}</dd></div>
            </dl>
          </section>
          <section>
            <h4>Финальный ffprobe</h4>
            <dl class="technical-list">
              <div><dt>Видео</dt><dd>${model.final.codec} · ${model.final.pixelFormat}</dd></div>
              <div><dt>Длительность</dt><dd>${model.final.durationSeconds.toFixed(3)} с</dd></div>
              <div><dt>Частота</dt><dd>${model.final.fps}/1 fps</dd></div>
              <div><dt>Кадры</dt><dd>${model.final.frames}</dd></div>
              <div><dt>Аудиопотоки</dt><dd>${model.final.hasAudio ? "есть" : "0"}</dd></div>
              <div><dt>Постобработка</dt><dd>${model.processing}</dd></div>
            </dl>
          </section>
          <section class="technical-details__wide">
            <h4>Generation trace</h4>
            <dl class="technical-list technical-list--ids">
              <div><dt>Job ID</dt><dd><code>${model.jobId}</code></dd></div>
              <div><dt>Generation ID</dt><dd><code>${model.generationId}</code></dd></div>
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

  const renderCase = (item) => `
    <article class="case-study" id="${item.id}" data-case>
      <header class="case-header">
        <p class="case-number" aria-hidden="true">${item.number}</p>
        <div class="case-copy">
          <p class="eyebrow">Исходник ${item.source.filename} · ${item.source.width}×${item.source.height}</p>
          <h2>${item.title}</h2>
          <p>${item.task}</p>
        </div>
        <a class="source-figure" href="${item.source.path}" aria-label="Открыть исходник ${item.source.filename}">
          <img src="${item.source.path}" alt="Исходный кадр: ${item.title.toLowerCase()}" />
          <span>
            <strong>First frame</strong>
            ${formatMiB(item.source.sizeBytes)} · открыть
          </span>
        </a>
      </header>

      <div class="pair-controls" aria-label="Синхронное управление парой">
        <p class="pair-status" aria-live="polite" data-pair-status>
          <span aria-hidden="true"></span>
          Загружаем metadata · 0 / 2
        </p>
        <div class="pair-actions">
          <button class="control-button control-button--primary" type="button" data-pair-play aria-pressed="false">
            Запустить пару
          </button>
          <button class="control-button" type="button" data-pair-reset>С первого кадра</button>
          <button class="control-button" type="button" data-pair-loop aria-pressed="false">Повтор: выкл</button>
        </div>
        <label class="timeline">
          <span class="timeline__label">Общий таймкод</span>
          <input
            type="range"
            min="0"
            max="5"
            step="0.01"
            value="0"
            data-pair-scrubber
            aria-label="Общий таймкод пары ${item.number}"
          />
          <output data-pair-time>0:00.0 / 0:05.0</output>
        </label>
      </div>

      <div class="model-comparison">
        <div class="model-grid">
          ${item.models.map((model) => renderModel(model, item.source)).join("")}
        </div>
      </div>
    </article>
  `;

  list.innerHTML = data.cases.map(renderCase).join("");

  const initialisePair = (pair) => {
    const videos = [...pair.querySelectorAll("[data-pair-video]")];
    const playButton = pair.querySelector("[data-pair-play]");
    const resetButton = pair.querySelector("[data-pair-reset]");
    const loopButton = pair.querySelector("[data-pair-loop]");
    const scrubber = pair.querySelector("[data-pair-scrubber]");
    const timeOutput = pair.querySelector("[data-pair-time]");
    const status = pair.querySelector("[data-pair-status]");
    const duration = data.common.finalDuration;
    let locked = false;
    let scrubbing = false;
    let pendingSeek = null;
    let loopEnabled = false;
    const ready = new Set();

    const setStatus = (message, state = "ready") => {
      status.lastChild.textContent = ` ${message}`;
      status.dataset.state = state;
    };

    const setPlayState = (playing) => {
      playButton.setAttribute("aria-pressed", String(playing));
      playButton.textContent = playing ? "Пауза" : "Запустить пару";
    };

    const updateTimeline = (currentTime = videos[0]?.currentTime || 0) => {
      const safeTime = Math.min(Math.max(currentTime, 0), duration);
      if (!scrubbing) scrubber.value = safeTime.toFixed(2);
      timeOutput.value = `${formatClock(safeTime)} / ${formatClock(duration)}`;
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
      if (Number.isFinite(time)) {
        videos.forEach((video) => {
          video.currentTime = time;
        });
      }

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
        setStatus("Воспроизведение заблокировано браузером", "error");
      } finally {
        locked = false;
      }
    };

    playButton.addEventListener("click", () => {
      if (videos.some((video) => !video.paused && !video.ended)) {
        pauseAll();
      } else {
        const restartAt = videos.every((video) => video.ended) ? 0 : videos[0].currentTime;
        playAll(restartAt);
      }
    });

    resetButton.addEventListener("click", () => {
      pauseAll("Первый кадр");
      videos.forEach((video) => {
        video.currentTime = 0;
      });
      updateTimeline(0);
    });

    loopButton.addEventListener("click", () => {
      loopEnabled = !loopEnabled;
      loopButton.setAttribute("aria-pressed", String(loopEnabled));
      loopButton.textContent = `Повтор: ${loopEnabled ? "вкл" : "выкл"}`;
      setStatus(loopEnabled ? "Повтор включён" : "Повтор выключен", "ready");
    });

    scrubber.addEventListener("input", () => {
      scrubbing = true;
      const time = Number(scrubber.value);
      timeOutput.value = `${formatClock(time)} / ${formatClock(duration)}`;
    });

    scrubber.addEventListener("change", () => {
      const time = Number(scrubber.value);
      pendingSeek = time;
      locked = true;
      videos.forEach((video) => {
        video.currentTime = time;
      });
      locked = false;
      scrubbing = false;
      updateTimeline(time);
      setStatus(`Кадр ${formatClock(time)}`, "paused");
    });

    videos.forEach((video) => {
      const shell = video.closest("[data-media-shell]");

      const markReady = () => {
        ready.add(video);
        if (ready.size === videos.length) {
          setStatus("Готово · 2 / 2", "ready");
        } else {
          setStatus(`Загружаем metadata · ${ready.size} / ${videos.length}`, "loading");
        }
      };

      if (video.readyState >= 1) markReady();
      video.addEventListener("loadedmetadata", markReady, { once: true });

      video.addEventListener("error", () => {
        shell.dataset.state = "error";
        setStatus("Один из MP4 не загрузился", "error");
      });

      video.addEventListener("play", () => {
        if (locked) return;
        playAll(video.currentTime);
      });

      video.addEventListener("pause", () => {
        if (locked || video.ended) return;
        pauseAll();
      });

      video.addEventListener("seeking", () => {
        if (locked || scrubbing || pendingSeek !== null) return;
        locked = true;
        videos.forEach((peer) => {
          if (peer !== video && Math.abs(peer.currentTime - video.currentTime) > 0.04) {
            peer.currentTime = video.currentTime;
          }
        });
        locked = false;
        updateTimeline(video.currentTime);
      });

      video.addEventListener("seeked", () => {
        if (pendingSeek === null) return;
        const settled = videos.every((peer) => Math.abs(peer.currentTime - pendingSeek) < 0.08);
        if (!settled) return;
        const target = pendingSeek;
        pendingSeek = null;
        updateTimeline(target);
      });

      video.addEventListener("ended", () => {
        if (locked) return;
        if (loopEnabled) {
          playAll(0);
        } else {
          setPlayState(false);
          setStatus("Просмотр завершён", "paused");
          updateTimeline(duration);
        }
      });
    });

    videos[0].addEventListener("timeupdate", () => {
      if (locked || scrubbing) return;
      const masterTime = videos[0].currentTime;
      if (pendingSeek !== null) {
        if (Math.abs(masterTime - pendingSeek) >= 0.08) return;
        pendingSeek = null;
      }
      const peer = videos[1];
      if (!peer.paused && Math.abs(peer.currentTime - masterTime) > 0.18) {
        peer.currentTime = masterTime;
      }
      updateTimeline(masterTime);
    });

    updateTimeline(0);
  };

  document.querySelectorAll("[data-case]").forEach(initialisePair);

  const navLinks = [...document.querySelectorAll(".section-nav a")];
  const observedSections = navLinks
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if ("IntersectionObserver" in window) {
    const navObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        navLinks.forEach((link) => {
          if (link.getAttribute("href") === `#${visible.target.id}`) {
            link.setAttribute("aria-current", "location");
          } else {
            link.removeAttribute("aria-current");
          }
        });
      },
      { rootMargin: "-25% 0px -55%", threshold: [0, 0.2, 0.5] },
    );
    observedSections.forEach((section) => navObserver.observe(section));
  }
})();
