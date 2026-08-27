(function () {
  "use strict";

  const MODELS = Object.freeze([
    {
      key: "h3",
      name: "MiniMax H3",
      id: "minimax/hailuo-3",
      src: "media/minimax-h3.mp4",
      duration: "5,167 с",
      resolution: "2560 × 1440",
      fps: "24 fps",
      size: "5,2 МБ",
      attempt: "Исторический canary · job 9S1CpP1RjyGy4hZTD9yq",
      providerAudio: true,
      summary: "Самое сдержанное движение в пятёрке. Пара и рожки остаются стабильными, декоративные диски сохраняются заметнее, чем в Wan 3.0.",
      prompt: "The couple walks forward together with relaxed, synchronized steps, keeping both ice-cream cones upright as their hair and loose clothing move gently in the breeze. The camera tracks backward smoothly on the couple, ending after they have advanced several steps while still sharing the same warm gaze.",
    },
    {
      key: "wan30",
      name: "Wan 3.0",
      id: "alibaba/wan-3.0",
      src: "media/wan-3.0.mp4",
      duration: "4,0 с",
      resolution: "1920 × 1080",
      fps: "30 fps",
      size: "23,7 МБ",
      attempt: "Новый запуск · job yUNNtxJsn8yUIrULQkaD",
      providerAudio: true,
      summary: "Движение пары читается выразительнее, лица и рожки удерживаются уверенно. Декоративные диски постепенно почти исчезают.",
      prompt: "The couple strolls forward together at a relaxed, even pace while keeping their warm mutual gaze, each ice-cream cone upright in its gripping hand. A smooth backward tracking camera holds them centered as their steps and hair movement settle naturally by the final frame.",
    },
    {
      key: "veo31",
      name: "Veo 3.1 Lite",
      id: "google/veo-3.1-lite",
      src: "media/veo-3.1-lite.mp4",
      duration: "4,0 с",
      resolution: "1920 × 1080",
      fps: "24 fps",
      size: "10,3 МБ",
      attempt: "Выбран retry-04 · контроль трёх колец",
      providerAudio: false,
      summary: "Специальный retry с явным требованием сохранить три кольца в исходной глубине и не допустить их пересечения с людьми.",
      prompt: "The camera tracks backward smoothly at normal real-time speed as the couple walks forward together, ending clearly mid-stride with both upright cones and the same warm mutual gaze. Keep exactly three rigid decorative rings fixed to the background at their original size, position, depth, orientation, and occlusion order, never intersecting either person or creating fragments.",
    },
    {
      key: "wan27",
      name: "Wan 2.7",
      id: "alibaba/wan-2.7",
      src: "media/wan-2.7.mp4",
      duration: "5,0 с",
      resolution: "1920 × 1080",
      fps: "30 fps",
      size: "9,1 МБ",
      attempt: "Выбран retry-02 · provider output accepted",
      providerAudio: true,
      summary: "Пятисекундный выбранный вариант с плавной совместной прогулкой. Неожиданная аудиодорожка удалена stream-copy операцией.",
      prompt: "The couple continue strolling forward side by side in a smooth natural rhythm, keeping their smiles and eye contact while the cones remain upright in their hands. They finish several steps farther along, still walking together with the same relaxed mood.",
    },
    {
      key: "wan22",
      name: "Wan 2.2",
      id: "alibaba/wan-2.2",
      src: "media/wan-2.2.mp4",
      duration: "5,0 с",
      resolution: "1280 × 720",
      fps: "30 fps",
      size: "11,3 МБ",
      attempt: "Одобрен retry-07 · Segmind",
      providerAudio: false,
      summary: "Финальный одобренный 720p-вариант. Сохраняет спокойный темп, взаимный взгляд и вертикальное положение обоих рожков.",
      prompt: "The couple continues strolling forward together at a relaxed, even pace, with gentle body sway and hair moving in the breeze while their ice-cream cones remain upright in their hands. By the final frames they have advanced visibly and still share the same warm smile.",
    },
  ]);

  const elements = {
    tabs: document.getElementById("modelTabs"),
    video: document.getElementById("modelVideo"),
    playPause: document.getElementById("playPause"),
    restart: document.getElementById("restart"),
    panel: document.getElementById("modelPanel"),
    count: document.getElementById("modelCount"),
    name: document.getElementById("modelName"),
    id: document.getElementById("modelId"),
    summary: document.getElementById("modelSummary"),
    duration: document.getElementById("duration"),
    resolution: document.getElementById("resolution"),
    fps: document.getElementById("fps"),
    fileSize: document.getElementById("fileSize"),
    audioNote: document.getElementById("audioNote"),
    prompt: document.getElementById("prompt"),
    attempt: document.getElementById("attemptLine"),
    body: document.getElementById("comparisonBody"),
  };

  let currentIndex = Math.max(0, MODELS.findIndex((model) => model.key === location.hash.slice(1)));

  const renderTabs = () => {
    elements.tabs.replaceChildren(
      ...MODELS.map((model, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "modelTab";
        button.id = "tab-" + model.key;
        button.role = "tab";
        button.textContent = model.name;
        button.setAttribute("aria-controls", "modelPanel");
        button.setAttribute("aria-selected", String(index === currentIndex));
        button.tabIndex = index === currentIndex ? 0 : -1;
        button.addEventListener("click", () => selectModel(index, true));
        return button;
      }),
    );
  };

  const renderTable = () => {
    elements.body.replaceChildren(
      ...MODELS.map((model) => {
        const row = document.createElement("tr");
        const values = [
          model.name,
          model.duration,
          model.resolution,
          model.fps,
          model.attempt.split(" · ")[0],
          model.providerAudio ? "Было — удалено в playback" : "Не было",
        ];
        values.forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.appendChild(cell);
        });
        return row;
      }),
    );
  };

  const updatePlayLabel = () => {
    elements.playPause.textContent = elements.video.paused ? "Воспроизвести" : "Пауза";
  };

  function selectModel(index, updateHash) {
    currentIndex = (index + MODELS.length) % MODELS.length;
    const model = MODELS[currentIndex];
    elements.video.pause();
    elements.video.src = model.src;
    elements.video.load();
    elements.count.textContent = String(currentIndex + 1).padStart(2, "0") + " / " + String(MODELS.length).padStart(2, "0");
    elements.name.textContent = model.name;
    elements.id.textContent = model.id;
    elements.summary.textContent = model.summary;
    elements.duration.textContent = model.duration;
    elements.resolution.textContent = model.resolution;
    elements.fps.textContent = model.fps;
    elements.fileSize.textContent = model.size;
    elements.audioNote.textContent = model.providerAudio
      ? "Провайдер вернул аудио вопреки generate_audio=false. Здесь воспроизводится бесшумная копия без перекодирования видеопотока."
      : "Провайдер выполнил generate_audio=false: в исходном результате аудиодорожки нет.";
    elements.prompt.textContent = model.prompt;
    elements.attempt.textContent = model.attempt;
    elements.panel.setAttribute("aria-labelledby", "tab-" + model.key);

    Array.from(elements.tabs.children).forEach((tab, tabIndex) => {
      tab.setAttribute("aria-selected", String(tabIndex === currentIndex));
      tab.tabIndex = tabIndex === currentIndex ? 0 : -1;
    });
    if (updateHash) history.replaceState(null, "", "#" + model.key);
    updatePlayLabel();
  }

  elements.playPause.addEventListener("click", () => {
    if (elements.video.paused) elements.video.play();
    else elements.video.pause();
  });

  elements.restart.addEventListener("click", () => {
    elements.video.currentTime = 0;
    elements.video.play();
  });

  elements.video.addEventListener("play", updatePlayLabel);
  elements.video.addEventListener("pause", updatePlayLabel);
  elements.video.addEventListener("ended", updatePlayLabel);

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("summary, button, video")) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      selectModel(currentIndex + (event.key === "ArrowRight" ? 1 : -1), true);
      elements.tabs.children[currentIndex].focus();
    }
    if (event.code === "Space") {
      event.preventDefault();
      elements.playPause.click();
    }
  });

  window.addEventListener("hashchange", () => {
    const index = MODELS.findIndex((model) => model.key === location.hash.slice(1));
    if (index >= 0) selectModel(index, false);
  });

  renderTabs();
  renderTable();
  selectModel(currentIndex, false);
})();
