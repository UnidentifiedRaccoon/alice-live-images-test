const assets = [
  {
    id: "480p-3375-24",
    name: "480p · короткий · 24fps",
    quality: "480p",
    resolution: "720x544",
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
    name: "480p · длинный · 24fps",
    quality: "480p",
    resolution: "720x544",
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
    name: "720p · короткий · 30fps",
    quality: "720p",
    resolution: "1088x816",
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
    name: "720p · короткий · 30fps",
    quality: "720p",
    resolution: "1088x816",
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
    quality: "720p",
    resolution: "1088x816",
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
    quality: "720p",
    resolution: "1088x816",
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
    name: "720p · длинный · 24fps",
    quality: "720p",
    resolution: "1088x816",
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
const toolbarEl = document.querySelector(".toolbar");

const formatBytes = (bytes) => {
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(mb >= 10 ? 1 : 2)} MB`;
};

const formatRatio = (webpBytes, videoBytes) => {
  const ratio = webpBytes / videoBytes;
  return `×${ratio.toFixed(1)}`;
};

const cssRatio = ({ width, height }) => `${width} / ${height}`;

const totalVideoBytes = assets.reduce((sum, item) => sum + item.videoBytes, 0);
const totalWebpBytes = assets.reduce((sum, item) => sum + item.webpBytes, 0);
const totalFrames = assets.reduce((sum, item) => sum + item.frames, 0);

summaryEl.innerHTML = [
  ["Пар в выборке", `${assets.length}`],
  ["Исходные MP4", formatBytes(totalVideoBytes)],
  ["Animated WebP", formatBytes(totalWebpBytes)],
  ["Кадров сохранено", `${totalFrames}`],
]
  .map(
    ([label, value], index) => `
      <article class="summaryMetric" style="--i: ${index}">
        <span>${label}</span>
        <strong>${value}</strong>
      </article>
    `,
  )
  .join("");

listEl.innerHTML = assets
  .map((item, index) => {
    const ratio = formatRatio(item.webpBytes, item.videoBytes);
    const ratioClass = item.webpBytes / item.videoBytes > 20 ? "deltaHigh" : "deltaNeutral";
    const loopPill = item.looped ? '<span class="pill looped">Зациклено</span>' : "";

    return `
      <article class="pairCard" id="${item.id}" style="--ratio: ${cssRatio(item)}">
        <header class="pairHeader">
          <div>
            <h2 class="pairTitle"><span class="pairIndex">${String(index + 1).padStart(2, "0")}</span>${item.name}</h2>
            <div class="metaRow" aria-label="Параметры медиа">
              <span class="pill quality">${item.quality}</span>
              <span class="pill">${item.resolution}</span>
              <span class="pill">${item.duration.toFixed(3)}s</span>
              <span class="pill">${item.fps}fps</span>
              <span class="pill">${item.frames} кадров</span>
              ${loopPill}
              <span class="pill warning">WebP · ${ratio}</span>
            </div>
          </div>
          <div class="pairActions">
            <button class="controlButton" type="button" data-action="restart-one" data-id="${item.id}">
              Синхронизировать пару
            </button>
          </div>
        </header>

        <div class="mediaPair">
          <section class="mediaPanel" aria-label="Исходный MP4">
            <div class="mediaPanelHeader">
              <h3><span>01</span> Original MP4</h3>
              <span class="fileSize">${formatBytes(item.videoBytes)}</span>
            </div>
            <div class="mediaFrame">
              <video
                controls
                loop
                muted
                playsinline
                preload="metadata"
                data-video-id="${item.id}"
              >
                <source src="${item.video}" type="video/mp4" />
              </video>
            </div>
          </section>

          <section class="mediaPanel" aria-label="Animated WebP">
            <div class="mediaPanelHeader">
              <h3><span>02</span> Animated WebP</h3>
              <span class="fileSize">${formatBytes(item.webpBytes)}</span>
            </div>
            <div class="mediaFrame">
              <img
                src="${item.webp}"
                alt="Конвертация animated WebP для ${item.name}"
                loading="lazy"
                decoding="async"
                data-webp-id="${item.id}"
                data-src="${item.webp}"
              />
            </div>
          </section>
        </div>

        <table class="detailTable" aria-label="Техническое сравнение для ${item.name}">
          <tbody>
            <tr>
              <th scope="row">Параметры</th>
              <td>${item.resolution}, ${item.duration.toFixed(3)} секунды, ${item.fps}fps, ${item.frames} кадров</td>
            </tr>
            <tr>
              <th scope="row">Размер файла</th>
              <td>MP4 ${formatBytes(item.videoBytes)} vs WebP ${formatBytes(item.webpBytes)} <span class="${ratioClass}">(${ratio})</span></td>
            </tr>
          </tbody>
        </table>
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
  video.currentTime = 0;
  const playPromise = video.play();
  if (playPromise) {
    playPromise.catch(() => {
      video.controls = true;
    });
  }
};

const restartPair = (id) => {
  const video = document.querySelector(`video[data-video-id="${id}"]`);
  restartWebp(id);
  if (video) restartVideo(video);
};

const restartAll = () => {
  assets.forEach((item) => restartWebp(item.id));
  getVideos().forEach(restartVideo);
};

toolbarEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;

  const action = button.dataset.action;
  if (action === "play-all") {
    getVideos().forEach((video) => {
      const playPromise = video.play();
      if (playPromise) playPromise.catch(() => {});
    });
  }

  if (action === "pause-all") {
    getVideos().forEach((video) => video.pause());
  }

  if (action === "restart-all") {
    restartAll();
  }
});

listEl.addEventListener("click", (event) => {
  const button = event.target.closest('button[data-action="restart-one"]');
  if (!button) return;
  restartPair(button.dataset.id);
});

window.addEventListener("load", () => {
  restartAll();
});
