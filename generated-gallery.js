const data = window.generatedGalleryData || [];

const galleryList = document.querySelector("#galleryList");
const heroStats = document.querySelector("#heroStats");
const groupTabs = document.querySelector("#groupTabs");
const togglePromptsButton = document.querySelector("#togglePrompts");

let activeGroup = "all";
let promptsOpen = false;

const formatBytes = (bytes) => {
  if (!bytes) return "n/a";
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(mb >= 10 ? 1 : 2)} MB`;
};

const escapeHtml = (value = "") =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const mediaRatio = ({ width, height }) => `${width} / ${height}`;

const sourceRatio = (item) => item.sourceRatio || mediaRatio(item);

const promptStatusBadge = (item) =>
  item.positivePrompt
    ? '<span class="badge ok">Prompt linked</span>'
    : '<span class="badge warn">Prompt metadata missing</span>';

const renderStats = () => {
  const groups = new Set(data.map((item) => item.group));
  const totalWebpBytes = data.reduce((sum, item) => sum + item.webpBytes, 0);
  const totalMp4Bytes = data.reduce((sum, item) => sum + item.mp4Bytes, 0);
  const missingPrompts = data.filter((item) => !item.positivePrompt).length;

  heroStats.innerHTML = [
    ["Examples", data.length],
    ["Groups", groups.size],
    ["MP4 total", formatBytes(totalMp4Bytes)],
    ["WebP total", formatBytes(totalWebpBytes)],
    ["Frames checked", data.reduce((sum, item) => sum + item.frames, 0)],
    ["Missing prompts", missingPrompts],
  ]
    .map(
      ([label, value]) => `
        <div>
          <dt>${label}</dt>
          <dd>${value}</dd>
        </div>
      `,
    )
    .join("");
};

const renderTabs = () => {
  const groups = ["all", ...new Set(data.map((item) => item.group))];
  groupTabs.innerHTML = groups
    .map((group) => {
      const label = group === "all" ? "Все" : group;
      const count =
        group === "all" ? data.length : data.filter((item) => item.group === group).length;
      return `
        <button class="tabButton ${group === activeGroup ? "active" : ""}" type="button" data-group="${group}">
          ${label} · ${count}
        </button>
      `;
    })
    .join("");
};

const renderSourceMedia = (item) => {
  if (!item.sourceImage) {
    return `
      <div class="mediaBlock">
        <div class="mediaLabel">
          <strong>Source image</strong>
          <span>not in manifest</span>
        </div>
        <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
          <div class="emptyFrame">Для этого MP4 нет исходной картинки в локальных манифестах.</div>
        </div>
      </div>
    `;
  }

  return `
    <div class="mediaBlock">
      <div class="mediaLabel">
        <strong>Source image</strong>
        <span>${escapeHtml(item.sourceName || "")}</span>
      </div>
      <div class="mediaFrame" style="--media-ratio: ${sourceRatio(item)}">
        <img src="${escapeHtml(item.sourceImage)}" alt="Source image for ${escapeHtml(item.title)}" loading="lazy" decoding="async" />
      </div>
    </div>
  `;
};

const renderPromptPanel = (item) => {
  if (!item.positivePrompt) {
    return `
      <section class="promptPanel">
        <h3>Prompt</h3>
        <p class="missingPrompt">
          В репозитории не найден prompt-манифест для этого примера. Файл включён в галерею,
          потому что MP4 и WebP существуют и прошли video→WebP проверку.
        </p>
      </section>
    `;
  }

  return `
    <section class="promptPanel">
      <h3>Prompt</h3>
      <details class="promptDetails" ${promptsOpen ? "open" : ""}>
        <summary>Positive prompt</summary>
        <p class="promptText">${escapeHtml(item.positivePrompt)}</p>
      </details>
      <details class="promptDetails" ${promptsOpen ? "open" : ""}>
        <summary>Negative prompt</summary>
        <p class="promptText">${escapeHtml(item.negativePrompt)}</p>
      </details>
    </section>
  `;
};

const renderGallery = () => {
  const items = activeGroup === "all" ? data : data.filter((item) => item.group === activeGroup);

  galleryList.innerHTML = items
    .map(
      (item, index) => `
        <article class="example" id="${escapeHtml(item.id)}">
          <header class="exampleHeader">
            <div>
              <div class="exampleTitleRow">
                <span class="exampleIndex">${index + 1}</span>
                <h3>${escapeHtml(item.title)}</h3>
              </div>
              <div class="badgeRow">
                <span class="badge info">${escapeHtml(item.group)}</span>
                <span class="badge">${item.width}x${item.height}</span>
                <span class="badge">${escapeHtml(item.fps)}</span>
                <span class="badge">${item.frames} frames</span>
                <span class="badge">${(item.durationMs / 1000).toFixed(3)}s</span>
                <span class="badge ok">Loop ${item.loop}</span>
                ${promptStatusBadge(item)}
              </div>
            </div>
            <div class="exampleFiles">
              MP4 ${formatBytes(item.mp4Bytes)}<br />
              WebP ${formatBytes(item.webpBytes)}
            </div>
          </header>

          <div class="mediaGrid">
            ${renderSourceMedia(item)}
            <div class="mediaBlock">
              <div class="mediaLabel">
                <strong>Generated MP4</strong>
                <span>${escapeHtml(item.videoName)}</span>
              </div>
              <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
                <video controls muted playsinline preload="metadata">
                  <source src="${escapeHtml(item.video)}" type="video/mp4" />
                </video>
              </div>
            </div>
            <div class="mediaBlock">
              <div class="mediaLabel">
                <strong>Animated WebP</strong>
                <span>${escapeHtml(item.webpName)}</span>
              </div>
              <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
                <img src="${escapeHtml(item.webp)}" alt="Animated WebP for ${escapeHtml(item.title)}" loading="lazy" decoding="async" />
              </div>
            </div>
          </div>

          <div class="detailsGrid">
            <section class="techPanel">
              <h3>Parameters</h3>
              <div class="metaGrid">
                <span class="badge">${item.width}x${item.height} canvas</span>
                <span class="badge">${escapeHtml(item.fps)} avg fps</span>
                <span class="badge">${item.frames} decoded frames</span>
                <span class="badge">${item.durationMs} ms total</span>
                <span class="badge">${item.delayMinMs}-${item.delayMaxMs} ms delays</span>
                <span class="badge">q95 lossy</span>
                <span class="badge">m6</span>
                <span class="badge">sharp_yuv</span>
                <span class="badge ok">webpmux checked</span>
              </div>
            </section>
            ${renderPromptPanel(item)}
          </div>
        </article>
      `,
    )
    .join("");
};

groupTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group]");
  if (!button) return;
  activeGroup = button.dataset.group;
  renderTabs();
  renderGallery();
});

togglePromptsButton.addEventListener("click", () => {
  promptsOpen = !promptsOpen;
  togglePromptsButton.classList.toggle("active", promptsOpen);
  togglePromptsButton.textContent = promptsOpen ? "Скрыть все промпты" : "Раскрыть все промпты";
  renderGallery();
});

renderStats();
renderTabs();
renderGallery();
