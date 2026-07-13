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

const promptStatusBadge = (item) =>
  item.positivePrompt
    ? '<span class="badge ok">Промпт привязан</span>'
    : '<span class="badge warn">Нет метаданных промпта</span>';

const renderStats = () => {
  const groups = new Set(data.map((item) => item.group));
  const totalWebpBytes = data.reduce((sum, item) => sum + item.webpBytes, 0);
  const totalMp4Bytes = data.reduce((sum, item) => sum + item.mp4Bytes, 0);
  const missingPrompts = data.filter((item) => !item.positivePrompt).length;

  heroStats.innerHTML = [
    ["Примеров", data.length],
    ["Групп", groups.size],
    ["Все MP4", formatBytes(totalMp4Bytes)],
    ["Все WebP", formatBytes(totalWebpBytes)],
    ["Кадров проверено", data.reduce((sum, item) => sum + item.frames, 0)],
    ["Без промпта", missingPrompts],
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
        <button
          class="tabButton ${group === activeGroup ? "active" : ""}"
          type="button"
          role="tab"
          aria-selected="${group === activeGroup}"
          aria-controls="galleryList"
          tabindex="${group === activeGroup ? "0" : "-1"}"
          data-group="${group}"
        >
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
          <strong>Исходное изображение</strong>
          <span>нет в manifest</span>
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
        <strong>Исходное изображение</strong>
        <span>${escapeHtml(item.sourceName || "")}</span>
      </div>
      <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
        <img src="${escapeHtml(item.sourceImage)}" alt="Исходное изображение для ${escapeHtml(item.title)}" loading="lazy" decoding="async" />
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

  if (!items.length) {
    galleryList.innerHTML = `
      <div class="galleryEmpty">
        В этой группе пока нет примеров. Выберите другую группу.
      </div>
    `;
    return;
  }

  galleryList.innerHTML = items
    .map(
      (item, index) => `
        <article class="example" id="${escapeHtml(item.id)}">
          <header class="exampleHeader">
            <div>
              <div class="exampleTitleRow">
                <span class="exampleIndex">${String(index + 1).padStart(2, "0")}</span>
                <h3>${escapeHtml(item.title)}</h3>
              </div>
              <div class="badgeRow">
                <span class="badge info">${escapeHtml(item.group)}</span>
                <span class="badge">${item.width}x${item.height}</span>
                <span class="badge">${escapeHtml(item.fps)}</span>
                <span class="badge">${item.frames} кадров</span>
                <span class="badge">${(item.durationMs / 1000).toFixed(3)}s</span>
                <span class="badge ok">Loop ${item.loop === 0 ? "∞" : item.loop}</span>
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
                <img src="${escapeHtml(item.webp)}" alt="Animated WebP для ${escapeHtml(item.title)}" loading="lazy" decoding="async" />
              </div>
            </div>
          </div>

          <div class="detailsGrid">
            <section class="techPanel">
              <h3>Параметры</h3>
              <div class="metaGrid">
                <span class="badge">${item.width}x${item.height} canvas</span>
                <span class="badge">${escapeHtml(item.fps)} avg fps</span>
                <span class="badge">${item.frames} декодированных кадров</span>
                <span class="badge">${item.durationMs} ms суммарно</span>
                <span class="badge">Задержки ${item.delayMinMs}-${item.delayMaxMs} ms</span>
                <span class="badge">q95 lossy</span>
                <span class="badge">m6</span>
                <span class="badge">sharp_yuv</span>
                <span class="badge ok">webpmux проверен</span>
              </div>
            </section>
            ${renderPromptPanel(item)}
          </div>
        </article>
      `,
    )
    .join("");
};

const setActiveGroup = (group, shouldFocus = false) => {
  activeGroup = group;
  groupTabs.querySelectorAll("[data-group]").forEach((button) => {
    const isActive = button.dataset.group === activeGroup;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
    button.tabIndex = isActive ? 0 : -1;
  });
  renderGallery();

  if (shouldFocus) {
    groupTabs.querySelector(`[data-group="${activeGroup}"]`)?.focus();
  }
};

groupTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group]");
  if (!button) return;
  setActiveGroup(button.dataset.group);
});

groupTabs.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;

  const tabs = Array.from(groupTabs.querySelectorAll("[data-group]"));
  const currentIndex = tabs.findIndex((button) => button.dataset.group === activeGroup);
  let nextIndex = currentIndex;

  if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = tabs.length - 1;

  event.preventDefault();
  setActiveGroup(tabs[nextIndex].dataset.group, true);
});

togglePromptsButton.addEventListener("click", () => {
  promptsOpen = !promptsOpen;
  togglePromptsButton.classList.toggle("active", promptsOpen);
  togglePromptsButton.setAttribute("aria-pressed", String(promptsOpen));
  togglePromptsButton.textContent = promptsOpen ? "Скрыть все промпты" : "Раскрыть все промпты";
  renderGallery();
});

renderStats();
renderTabs();
renderGallery();
