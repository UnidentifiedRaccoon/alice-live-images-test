const assets = [
  {
    id: "480p-3375-24",
    name: "480p · короткий",
    width: 720,
    height: 544,
    duration: 3.375,
    fps: 24,
    frames: 81,
    looped: false,
    video: "videos/alice-live-480p-720x544-3.375s-24fps.mp4",
    webp: "webp/alice-live-480p-720x544-3.375s-24fps.webp",
    videoBytes: 443139,
    webpBytes: 6612602,
  },
  {
    id: "480p-6208-24",
    name: "480p · длинный",
    width: 720,
    height: 544,
    duration: 6.208,
    fps: 24,
    frames: 149,
    looped: false,
    video: "videos/alice-live-480p-720x544-6.208s-24fps.mp4",
    webp: "webp/alice-live-480p-720x544-6.208s-24fps.webp",
    videoBytes: 854264,
    webpBytes: 13670954,
  },
  {
    id: "720p-3133-30",
    name: "720p · зацикленный",
    width: 1088,
    height: 816,
    duration: 3.133,
    fps: 30,
    frames: 94,
    looped: true,
    video: "videos/alice-live-720p-1088x816-3.133s-30fps-looped.mp4",
    webp: "webp/alice-live-720p-1088x816-3.133s-30fps-looped.webp",
    videoBytes: 403324,
    webpBytes: 9976360,
  },
  {
    id: "720p-3233-30",
    name: "720p · основной",
    width: 1088,
    height: 816,
    duration: 3.233,
    fps: 30,
    frames: 97,
    looped: false,
    video: "videos/alice-live-720p-1088x816-3.233s-30fps.mp4",
    webp: "webp/alice-live-720p-1088x816-3.233s-30fps.webp",
    videoBytes: 447735,
    webpBytes: 12769244,
  },
  {
    id: "720p-3233-30-alt",
    name: "720p · короткий · вариант A",
    width: 1088,
    height: 816,
    duration: 3.233,
    fps: 30,
    frames: 97,
    looped: false,
    video: "videos/alice-live-720p-1088x816-3.233s-30fps-alt.mp4",
    webp: "webp/alice-live-720p-1088x816-3.233s-30fps-alt.webp",
    videoBytes: 430427,
    webpBytes: 14055002,
  },
  {
    id: "720p-3233-30-alt-2",
    name: "720p · короткий · вариант B",
    width: 1088,
    height: 816,
    duration: 3.233,
    fps: 30,
    frames: 97,
    looped: false,
    video: "videos/alice-live-720p-1088x816-3.233s-30fps-alt-2.mp4",
    webp: "webp/alice-live-720p-1088x816-3.233s-30fps-alt-2.webp",
    videoBytes: 394663,
    webpBytes: 13729226,
  },
  {
    id: "720p-3917-24",
    name: "720p · длинный",
    width: 1088,
    height: 816,
    duration: 3.917,
    fps: 24,
    frames: 94,
    looped: true,
    video: "videos/alice-live-720p-1088x816-3.917s-24fps-looped.mp4",
    webp: "webp/alice-live-720p-1088x816-3.917s-24fps-looped.webp",
    videoBytes: 504231,
    webpBytes: 10880292,
  },
];

const summaryEl = document.querySelector("#summary");
const listEl = document.querySelector("#comparisonList");
const restartAllButton = document.querySelector('[data-action="restart-all"]');
const playbackStatusEl = document.querySelector("#playbackStatus");
const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

const integerFormatter = new Intl.NumberFormat("ru-RU");
const durationFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const ratioFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const framePluralRules = new Intl.PluralRules("ru-RU");
const frameLabels = {
  one: "кадр",
  few: "кадра",
  many: "кадров",
  other: "кадра",
};

const formatBytes = (bytes) => {
  const mebibytes = bytes / (1024 * 1024);
  const digits = mebibytes >= 10 ? 1 : 2;
  const formatter = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${formatter.format(mebibytes)} МиБ`;
};

const formatRatio = (webpBytes, videoBytes) => {
  const ratio = webpBytes / videoBytes;
  return `×${ratioFormatter.format(ratio)}`;
};

const cssRatio = ({ width, height }) => `${width} / ${height}`;
const formatResolution = ({ width, height }) =>
  `${integerFormatter.format(width)} × ${integerFormatter.format(height)}`;
const formatFrames = (frames) =>
  `${integerFormatter.format(frames)} ${frameLabels[framePluralRules.select(frames)]}`;

const renderWebpImage = (item, shouldRestart = false) => {
  const source = shouldRestart ? `${item.webp}?restart=${Date.now()}` : item.webp;

  return `
    <img
      src="${source}"
      alt="Анимированный WebP для ${item.name}"
      width="${item.width}"
      height="${item.height}"
      ${shouldRestart ? 'tabindex="-1"' : ""}
      loading="lazy"
      decoding="async"
      data-webp-id="${item.id}"
      data-src="${item.webp}"
    />
  `;
};

const renderWebpContent = (item) => {
  if (!reducedMotionQuery.matches) return renderWebpImage(item);

  return `
    <button
      class="controlButton animationReveal"
      type="button"
      data-action="reveal-webp"
      data-id="${item.id}"
      aria-label="Показать анимированный WebP для ${item.name}"
    >
      Показать анимацию
    </button>
  `;
};

const totalVideoBytes = assets.reduce((sum, item) => sum + item.videoBytes, 0);
const totalWebpBytes = assets.reduce((sum, item) => sum + item.webpBytes, 0);

summaryEl.innerHTML = [
  ["Всего MP4", formatBytes(totalVideoBytes)],
  ["Всего WebP", formatBytes(totalWebpBytes)],
  ["WebP / MP4", formatRatio(totalWebpBytes, totalVideoBytes)],
]
  .map(
    ([label, value]) => `
      <div class="summaryMetric">
        <dt>${label}</dt>
        <dd>${value}</dd>
      </div>
    `,
  )
  .join("");

listEl.innerHTML = assets
  .map((item, index) => {
    const ratio = formatRatio(item.webpBytes, item.videoBytes);
    const loopLabel = item.looped ? " · зациклено" : "";

    return `
      <article class="pairCard" id="${item.id}" style="--ratio: ${cssRatio(item)}">
        <header class="pairHeader">
          <div>
            <h2 class="pairTitle"><span class="pairIndex">${String(index + 1).padStart(2, "0")}</span>${item.name}</h2>
            <p class="metaRow">
              ${formatResolution(item)} · ${durationFormatter.format(item.duration)} с ·
              ${integerFormatter.format(item.fps)} fps · ${formatFrames(item.frames)}${loopLabel} ·
              <strong>WebP ${ratio}</strong>
            </p>
          </div>
          <div class="pairActions">
            <button
              class="controlButton"
              type="button"
              data-action="restart-one"
              data-id="${item.id}"
              aria-label="Перезапустить ${item.name} с первого кадра"
            >
              Перезапустить пару
            </button>
          </div>
        </header>

        <div class="mediaPair">
          <section class="mediaPanel" aria-label="Исходный MP4">
            <div class="mediaPanelHeader">
              <h3>MP4</h3>
              <span class="fileSize">${formatBytes(item.videoBytes)}</span>
            </div>
            <div class="mediaFrame">
              <video
                controls
                loop
                muted
                playsinline
                preload="metadata"
                width="${item.width}"
                height="${item.height}"
                data-video-id="${item.id}"
                aria-label="MP4 для ${item.name}"
              >
                <source src="${item.video}" type="video/mp4" />
                Ваш браузер не поддерживает MP4-видео.
              </video>
            </div>
          </section>

          <section class="mediaPanel" aria-label="Анимированный WebP">
            <div class="mediaPanelHeader">
              <h3>WebP</h3>
              <span class="fileSize">${formatBytes(item.webpBytes)}</span>
            </div>
            <div class="mediaFrame" data-webp-frame="${item.id}">
              ${renderWebpContent(item)}
            </div>
          </section>
        </div>
      </article>
    `;
  })
  .join("");

const getVideos = () => Array.from(document.querySelectorAll("video[data-video-id]"));

const restartWebp = (id) => {
  const image = document.querySelector(`img[data-webp-id="${id}"]`);
  if (!image) return;

  const source = image.dataset.src;
  image.src = `${source}?restart=${Date.now()}`;
};

const restartVideo = (video) => {
  video.pause();
  video.currentTime = 0;
  const playPromise = video.play();
  if (playPromise) {
    return playPromise
      .then(() => true)
      .catch(() => {
        video.controls = true;
        return false;
      });
  }
  return Promise.resolve(true);
};

const restartPair = (id) => {
  const video = document.querySelector(`video[data-video-id="${id}"]`);
  restartWebp(id);
  if (video) void restartVideo(video);
};

const restartAll = async () => {
  assets.forEach((item) => restartWebp(item.id));
  const results = await Promise.all(getVideos().map(restartVideo));
  return results.every(Boolean);
};

restartAllButton.addEventListener("click", async () => {
  playbackStatusEl.textContent = "Перезапускаем MP4 и показанные WebP с первого кадра…";
  const allVideosPlaying = await restartAll();
  playbackStatusEl.textContent = allVideosPlaying
    ? "MP4 и показанные WebP перезапущены с первого кадра."
    : "Медиа сброшены; MP4 можно запустить встроенной кнопкой браузера.";
});

listEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  if (button.dataset.action === "reveal-webp") {
    const item = assets.find(({ id }) => id === button.dataset.id);
    const frame = button.closest("[data-webp-frame]");
    if (item && frame) {
      frame.innerHTML = renderWebpImage(item, true);
      frame.querySelector("img")?.focus({ preventScroll: true });
    }
    return;
  }

  if (button.dataset.action === "restart-one") restartPair(button.dataset.id);
});

reducedMotionQuery.addEventListener?.("change", () => {
  assets.forEach((item) => {
    const frame = document.querySelector(`[data-webp-frame="${item.id}"]`);
    if (frame) frame.innerHTML = renderWebpContent(item);
  });
});
