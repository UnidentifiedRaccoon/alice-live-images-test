const data = Array.isArray(window.generatedGalleryData) ? window.generatedGalleryData : [];

const galleryList = document.querySelector("#galleryList");
const librarySummary = document.querySelector("#librarySummary");
const groupTabs = document.querySelector("#groupTabs");
const togglePromptsButton = document.querySelector("#togglePrompts");

const groupDefinitions = [
  { id: "dobrograd", dataGroup: "orig 1", label: "ДоброГрад" },
  { id: "menswear", dataGroup: "orig 2", label: "Мужская мода" },
  { id: "cars", dataGroup: "orig 3", label: "Автомобили" },
  { id: "food", dataGroup: "orig 4", label: "Еда" },
];

const titleOverrides = {
  "example-01": "Лебеди на озере",
  "example-02": "Гольфист после удара",
  "example-03": "Вейкбордер на трассе",
  "example-04": "Портрет у моря",
  "example-05": "Манжета на фоне гор",
  "example-06": "Портрет у фасада",
  "example-07": "Портрет в дверном проёме",
  "example-08": "Сложенные рубашки",
  "example-09": "Автомобиль на парковке",
  "example-10": "Отражение на консоли",
  "example-11": "Подсветка салона",
  "example-12": "Changan CS55 Plus",
  "example-13": "Хлеб и сливки",
  "example-14": "Холодный суп крупным планом",
  "example-15": "Сметана над зелёным супом",
  "example-16": "Подача супа на деревянном столе",
  "example-17": "Обед с холодным супом",
};

const isComplete = (item) => Boolean(item.sourceImage && item.positivePrompt);
const completeItems = data.filter(isComplete);
const incompleteItems = data.filter((item) => !isComplete(item));
const completeGroups = groupDefinitions.filter((group) =>
  completeItems.some((item) => item.group === group.dataGroup),
);

const views = [
  ...completeGroups.map((group) => ({
    ...group,
    count: completeItems.filter((item) => item.group === group.dataGroup).length,
  })),
  ...(completeItems.length
    ? [{ id: "all", dataGroup: null, label: "Все", count: completeItems.length }]
    : []),
  ...(incompleteItems.length
    ? [
        {
          id: "incomplete",
          dataGroup: null,
          label: "Без метаданных",
          count: incompleteItems.length,
        },
      ]
    : []),
];

if (!views.length) {
  views.push({ id: "empty", dataGroup: null, label: "Все", count: 0 });
}

const integerFormatter = new Intl.NumberFormat("ru-RU");
const decimalFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
const durationFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const ratioFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const examplePluralRules = new Intl.PluralRules("ru-RU");
const exampleLabels = {
  one: "пример",
  few: "примера",
  many: "примеров",
  other: "примера",
};
const reducedMotionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || {
  matches: false,
};

const escapeHtml = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const formatMiB = (bytes) => `${decimalFormatter.format(bytes / 1024 / 1024)} МиБ`;
const formatExampleCount = (count) =>
  `${integerFormatter.format(count)} ${exampleLabels[examplePluralRules.select(count)]}`;

const formatFps = (value) => {
  const [numerator, denominator = 1] = String(value).split("/").map(Number);
  const fps = denominator ? numerator / denominator : numerator;
  return Number.isFinite(fps) ? decimalFormatter.format(fps) : String(value);
};

const mediaRatio = ({ width, height }) => `${width} / ${height}`;

const sourceDimensions = (item) => {
  const [width, height] = String(item.sourceRatio || "")
    .split("/")
    .map((value) => Number(value.trim()));

  return {
    width: Number.isFinite(width) && width > 0 ? width : item.width,
    height: Number.isFinite(height) && height > 0 ? height : item.height,
  };
};

const groupLabel = (dataGroup) =>
  groupDefinitions.find((group) => group.dataGroup === dataGroup)?.label || dataGroup;

const itemsForView = (viewId) => {
  if (viewId === "all") return completeItems;
  if (viewId === "incomplete") return incompleteItems;
  const view = views.find((item) => item.id === viewId);
  return view?.dataGroup
    ? completeItems.filter((item) => item.group === view.dataGroup)
    : [];
};

const requestedView = new URL(window.location.href).searchParams.get("group");
const defaultView = completeGroups[0]?.id || views[0].id;
let activeView = views.some((view) => view.id === requestedView) ? requestedView : defaultView;
let promptsOpen = false;

const syncUrl = () => {
  const url = new URL(window.location.href);
  url.searchParams.set("group", activeView);
  try {
    window.history.replaceState({ group: activeView }, "", url);
  } catch {
    // Direct file previews may disallow History API updates; the demo still works.
  }
};

const renderSummary = () => {
  const groupCount = new Set(completeItems.map((item) => item.group)).size;
  librarySummary.textContent = `${integerFormatter.format(completeItems.length)} готовых примеров · ${integerFormatter.format(groupCount)} коллекции · ${integerFormatter.format(incompleteItems.length)} без метаданных`;
};

const renderTabs = () => {
  groupTabs.innerHTML = views
    .map(
      (view) => `
        <button
          class="tabButton ${view.id === activeView ? "active" : ""}"
          id="tab-${view.id}"
          type="button"
          role="tab"
          aria-selected="${view.id === activeView}"
          aria-controls="galleryList"
          tabindex="${view.id === activeView ? "0" : "-1"}"
          data-view="${view.id}"
        >
          <span>${view.label}</span>
          <span class="tabCount" aria-label="${formatExampleCount(view.count)}">${integerFormatter.format(view.count)}</span>
        </button>
      `,
    )
    .join("");
};

const renderSourceMedia = (item) => {
  if (!item.sourceImage) {
    return `
      <section class="mediaBlock" aria-label="Исходное изображение не найдено">
        <div class="mediaLabel">
          <h3>Исходник</h3>
          <span>не привязан</span>
        </div>
        <div class="mediaFrame mediaFrame--empty" style="--media-ratio: ${mediaRatio(item)}">
          <div class="emptyFrame">Исходное изображение не найдено</div>
        </div>
      </section>
    `;
  }

  const dimensions = sourceDimensions(item);
  return `
    <section class="mediaBlock" aria-label="Исходное изображение">
      <div class="mediaLabel">
        <h3>Исходник</h3>
        <span>${escapeHtml(item.sourceName)}</span>
      </div>
      <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
        <img
          src="${escapeHtml(item.sourceImage)}"
          alt="Исходное изображение для «${escapeHtml(titleOverrides[item.id] || item.title)}»"
          width="${dimensions.width}"
          height="${dimensions.height}"
          loading="lazy"
          decoding="async"
        />
      </div>
    </section>
  `;
};

const renderWebpMedia = (item) => {
  const title = titleOverrides[item.id] || item.title;
  const media = reducedMotionQuery.matches
    ? `
        <button
          class="revealAnimation"
          type="button"
          data-reveal-webp
          data-src="${escapeHtml(item.webp)}"
          data-alt="Анимированный WebP для «${escapeHtml(title)}»"
          data-width="${item.width}"
          data-height="${item.height}"
        >
          <strong>Показать анимацию</strong>
          <span>Движение начнётся после клика</span>
        </button>
      `
    : `
        <img
          src="${escapeHtml(item.webp)}"
          alt="Анимированный WebP для «${escapeHtml(title)}»"
          width="${item.width}"
          height="${item.height}"
          loading="lazy"
          decoding="async"
        />
      `;

  return `
    <section class="mediaBlock" aria-label="WebP">
      <div class="mediaLabel">
        <h3>WebP</h3>
        <span>${escapeHtml(item.webpName)}</span>
      </div>
      <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}" data-webp-frame>
        ${media}
      </div>
    </section>
  `;
};

const renderTechnicalDetails = (item) => `
  <details class="compactDetails technicalDetails">
    <summary>
      <span>Технические параметры</span>
      <span class="detailsToggle" aria-hidden="true">+</span>
    </summary>
    <dl class="technicalList">
      <div><dt>Кадр</dt><dd>${item.width}×${item.height}</dd></div>
      <div><dt>Видео</dt><dd>${durationFormatter.format(item.durationMs / 1000)} с · ${formatFps(item.fps)} fps · ${integerFormatter.format(item.frames)} кадров</dd></div>
      <div><dt>WebP</dt><dd>${item.delayMinMs}–${item.delayMaxMs} мс · loop ${item.loop === 0 ? "∞" : item.loop}</dd></div>
      <div><dt>Кодирование</dt><dd>q95 · m6 · sharp_yuv</dd></div>
    </dl>
  </details>
`;

const renderPromptDetails = (item) => {
  if (!item.positivePrompt) {
    return `
      <details class="compactDetails promptDetails promptDetails--missing">
        <summary>
          <span>Промпт не найден</span>
          <span class="detailsToggle" aria-hidden="true">+</span>
        </summary>
        <p class="missingPrompt">
          MP4 и WebP доступны, но исходник и prompt-манифест не привязаны к этому файлу.
        </p>
      </details>
    `;
  }

  return `
    <details class="compactDetails promptDetails" data-prompt-details ${promptsOpen ? "open" : ""}>
      <summary>
        <span>Промпт генерации</span>
        <span class="detailsToggle" aria-hidden="true">+</span>
      </summary>
      <div class="promptBody">
        <section>
          <h3>Позитивный</h3>
          <p>${escapeHtml(item.positivePrompt)}</p>
        </section>
        <section>
          <h3>Негативный</h3>
          <p>${escapeHtml(item.negativePrompt || "Не указан")}</p>
        </section>
      </div>
    </details>
  `;
};

const renderGallery = () => {
  const items = itemsForView(activeView);
  galleryList.setAttribute("aria-labelledby", `tab-${activeView}`);

  if (!items.length) {
    const isIncompleteView = activeView === "incomplete";
    galleryList.innerHTML = `
      <div class="galleryEmpty" role="status">
        <strong>${isIncompleteView ? "Все примеры заполнены" : "В коллекции пока нет примеров"}</strong>
        <span>${isIncompleteView ? "Файлы без исходника и промпта здесь появятся автоматически." : "Выберите другую коллекцию или вернитесь позже."}</span>
      </div>
    `;
    togglePromptsButton.hidden = true;
    return;
  }

  galleryList.innerHTML = items
    .map((item, index) => {
      const title = isComplete(item)
        ? titleOverrides[item.id] || item.title
        : `Рендер без метаданных · ${String(index + 1).padStart(2, "0")}`;
      const ratio = item.webpBytes / item.mp4Bytes;
      const poster = item.sourceImage ? ` poster="${escapeHtml(item.sourceImage)}"` : "";

      return `
        <article class="example" id="${escapeHtml(item.id)}" aria-labelledby="${escapeHtml(item.id)}-title">
          <header class="exampleHeader">
            <div class="exampleHeading">
              <span class="exampleIndex" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
              <div>
                <p class="collectionLabel">${escapeHtml(groupLabel(item.group))}</p>
                <h2 id="${escapeHtml(item.id)}-title">${escapeHtml(title)}</h2>
              </div>
            </div>
            <div class="exampleSummary">
              <p class="exampleMeta">${item.width}×${item.height} · ${durationFormatter.format(item.durationMs / 1000)} с · ${formatFps(item.fps)} fps · ${integerFormatter.format(item.frames)} кадров</p>
              <dl class="fileComparison" aria-label="Размеры файлов">
                <div><dt>MP4</dt><dd>${formatMiB(item.mp4Bytes)}</dd></div>
                <div><dt>WebP</dt><dd>${formatMiB(item.webpBytes)}</dd></div>
                <div class="fileRatio"><dt>Разница</dt><dd>×${ratioFormatter.format(ratio)}</dd></div>
              </dl>
            </div>
          </header>

          <div class="mediaGrid">
            ${renderSourceMedia(item)}
            <section class="mediaBlock" aria-label="MP4">
              <div class="mediaLabel">
                <h3>MP4</h3>
                <span>${escapeHtml(item.videoName)}</span>
              </div>
              <div class="mediaFrame" style="--media-ratio: ${mediaRatio(item)}">
                <video
                  controls
                  muted
                  playsinline
                  preload="none"
                  width="${item.width}"
                  height="${item.height}"
                  aria-label="MP4 для «${escapeHtml(title)}»"
                  ${poster}
                >
                  <source src="${escapeHtml(item.video)}" type="video/mp4" />
                  Ваш браузер не поддерживает MP4-видео.
                </video>
              </div>
            </section>
            ${renderWebpMedia(item)}
          </div>

          <div class="detailsGrid">
            ${renderTechnicalDetails(item)}
            ${renderPromptDetails(item)}
          </div>
        </article>
      `;
    })
    .join("");

  togglePromptsButton.hidden = !items.some((item) => item.positivePrompt);
  updatePromptsButton();
};

const updateTabs = () => {
  groupTabs.querySelectorAll("[data-view]").forEach((button) => {
    const isActive = button.dataset.view === activeView;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
    button.tabIndex = isActive ? 0 : -1;
  });
};

const updatePromptsButton = () => {
  const promptDetails = [...galleryList.querySelectorAll("[data-prompt-details]")];
  promptsOpen = promptDetails.length > 0 && promptDetails.every((details) => details.open);
  togglePromptsButton.classList.toggle("active", promptsOpen);
  togglePromptsButton.setAttribute("aria-pressed", String(promptsOpen));
  togglePromptsButton.textContent = promptsOpen ? "Скрыть все промпты" : "Раскрыть все промпты";
};

const setActiveView = (viewId, shouldFocus = false, updateUrl = true) => {
  if (!views.some((view) => view.id === viewId)) return;
  activeView = viewId;
  updateTabs();
  renderGallery();
  if (updateUrl) syncUrl();
  if (shouldFocus) groupTabs.querySelector(`[data-view="${activeView}"]`)?.focus();
};

groupTabs.addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button) setActiveView(button.dataset.view);
});

groupTabs.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;

  const currentIndex = views.findIndex((view) => view.id === activeView);
  let nextIndex = currentIndex;
  if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + views.length) % views.length;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % views.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = views.length - 1;

  event.preventDefault();
  setActiveView(views[nextIndex].id, true);
});

togglePromptsButton.addEventListener("click", () => {
  const promptDetails = [...galleryList.querySelectorAll("[data-prompt-details]")];
  const shouldOpen = !promptDetails.every((details) => details.open);
  promptDetails.forEach((details) => {
    details.open = shouldOpen;
  });
  updatePromptsButton();
});

galleryList.addEventListener(
  "toggle",
  (event) => {
    if (event.target.matches?.("[data-prompt-details]")) queueMicrotask(updatePromptsButton);
  },
  true,
);

galleryList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-reveal-webp]");
  if (!button) return;

  const image = document.createElement("img");
  image.src = button.dataset.src;
  image.alt = button.dataset.alt;
  image.width = Number(button.dataset.width);
  image.height = Number(button.dataset.height);
  image.loading = "eager";
  image.decoding = "async";
  image.tabIndex = -1;
  button.closest("[data-webp-frame]")?.replaceChildren(image);
  image.focus({ preventScroll: true });
});

window.addEventListener("popstate", () => {
  const viewId = new URL(window.location.href).searchParams.get("group");
  setActiveView(views.some((view) => view.id === viewId) ? viewId : defaultView, false, false);
});

reducedMotionQuery.addEventListener?.("change", renderGallery);

renderSummary();
renderTabs();
renderGallery();
syncUrl();
