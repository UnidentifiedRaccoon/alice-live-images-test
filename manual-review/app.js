const dataset = window.qualityReviewDataset;
const reviewCore = window.qualityReviewCore;
const reducedMotionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || {
  matches: false,
};
const desktopLayoutQuery = window.matchMedia?.("(min-width: 64rem)") || { matches: false };

const elements = {
  workspace: document.querySelector("#reviewWorkspace"),
  videoColumn: document.querySelector("#videoColumn"),
  navigationStatus: document.querySelector("#navigationStatus"),
  datasetError: document.querySelector("#datasetError"),
  datasetErrorText: document.querySelector("#datasetErrorText"),
  progressLabel: document.querySelector("#progressLabel"),
  draftCount: document.querySelector("#draftCount"),
  progressTrack: document.querySelector(".progressTrack"),
  progressBar: document.querySelector("#progressBar"),
  exportButton: document.querySelector("#exportButton"),
  currentNumber: document.querySelector("#currentNumber"),
  totalNumber: document.querySelector("#totalNumber"),
  clipTitle: document.querySelector("#clipTitle"),
  authorBadge: document.querySelector("#authorBadge"),
  approachBadge: document.querySelector("#approachBadge"),
  modelBadge: document.querySelector("#modelBadge"),
  video: document.querySelector("#reviewVideo"),
  videoStage: document.querySelector("#videoStage"),
  mediaError: document.querySelector("#mediaError"),
  videoFacts: document.querySelector("#videoFacts"),
  technicalNotes: document.querySelector("#technicalNotes"),
  previousButton: document.querySelector("#previousButton"),
  nextButton: document.querySelector("#nextButton"),
  replayButton: document.querySelector("#replayButton"),
  groupFilter: document.querySelector("#groupFilter"),
  itemSelect: document.querySelector("#itemSelect"),
  form: document.querySelector("#reviewForm"),
  panel: document.querySelector("#reviewForm"),
  articleLink: document.querySelector("#articleLink"),
  contextSection: document.querySelector("#contextSection"),
  contextIndex: document.querySelector("#contextIndex"),
  contextScope: document.querySelector("#contextScope"),
  articleIdentity: document.querySelector("#articleIdentity"),
  contextDetails: document.querySelector("#contextDetails"),
  contextFragments: document.querySelector("#contextFragments"),
  contextTitle: document.querySelector("#contextTitle"),
  promptTitle: document.querySelector("#promptTitle"),
  promptIndex: document.querySelector("#promptIndex"),
  agentLabel: document.querySelector("#agentLabel"),
  providerNote: document.querySelector("#providerNote"),
  positivePrompt: document.querySelector("#positivePrompt"),
  negativePromptBlock: document.querySelector("#negativePromptBlock"),
  negativePrompt: document.querySelector("#negativePrompt"),
  negativePromptStatus: document.querySelector("#negativePromptStatus"),
  ratingFieldset: document.querySelector("#ratingFieldset"),
  ratingIndex: document.querySelector("#ratingIndex"),
  ratingQuestion: document.querySelector("#ratingQuestion"),
  ratingInputs: Array.from(document.querySelectorAll('input[name="rating"]')),
  ratingError: document.querySelector("#ratingError"),
  feedback: document.querySelector("#feedback"),
  guideIndex: document.querySelector("#guideIndex"),
  intentionGuide: document.querySelector("#intentionGuide"),
  promptGuide: document.querySelector("#promptGuide"),
  feedbackIndex: document.querySelector("#feedbackIndex"),
  feedbackRequirement: document.querySelector("#feedbackRequirement"),
  feedbackError: document.querySelector("#feedbackError"),
  autosaveStatus: document.querySelector("#autosaveStatus"),
  storageNotice: document.querySelector("#storageNotice"),
  submitStatus: document.querySelector("#submitStatus"),
  submitButton: document.querySelector("#submitButton"),
  toast: document.querySelector("#toast"),
};

const pluralRules = new Intl.PluralRules("ru-RU");
const draftLabels = { one: "черновик", few: "черновика", many: "черновиков", other: "черновика" };
const decimalFormatter = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 3 });
const timeFormatter = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const warningLabels = {
  audio: "провайдер добавил аудио, хотя оно было отключено",
  resolution: "фактическое разрешение отличается от запроса",
  aspect_ratio: "фактическое соотношение сторон отличается от запроса",
  duration: "фактическая длительность отличается от запроса",
};
const modelLabelFor = (modelId) =>
  items.find((item) => item.model.id === modelId)?.model.label || modelId || "неизвестная модель";

const isDatasetValid =
  reviewCore &&
  dataset &&
  dataset.schema_version === 2 &&
  typeof dataset.dataset_id === "string" &&
  Array.isArray(dataset.items) &&
  dataset.items.length > 0;

let items = isDatasetValid ? dataset.items : [];
let storageKey = isDatasetValid
  ? `alice-live:quality-review:v2:${dataset.review_ticket}`
  : "";
let state;
let activeIndex = 0;
let activeGroupFilter = "all";
let saveTimer = 0;
let toastTimer = 0;
let hasMediaError = false;
let storageAvailable = true;

const nowIso = () => new Date().toISOString();

const freshState = () => reviewCore.freshState(dataset, nowIso());
const isValidRating = reviewCore?.isValidRating || (() => false);
const normalizeState = (value) =>
  (reviewCore.migrateState || reviewCore.normalizeState)(value, dataset, nowIso());

const loadState = () => {
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored) return normalizeState(JSON.parse(stored));

    for (const datasetId of dataset.supersedes_dataset_ids || []) {
      const legacyKey = `alice-live:quality-review:v1:${datasetId}`;
      const legacyState = window.localStorage.getItem(legacyKey);
      if (!legacyState) continue;
      const migrated = normalizeState(JSON.parse(legacyState));
      window.localStorage.setItem(storageKey, JSON.stringify(migrated));
      return migrated;
    }

    return freshState();
  } catch {
    storageAvailable = false;
    return freshState();
  }
};

const showStorageWarning = () => {
  elements.storageNotice.hidden = storageAvailable;
  elements.storageNotice.textContent = storageAvailable
    ? ""
    : "Автосохранение в этом браузере недоступно. Экспортируйте JSON до закрытия страницы.";
};

const persistState = () => {
  if (!state || !storageKey) return;
  window.clearTimeout(saveTimer);
  saveTimer = 0;
  state.savedAt = nowIso();

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
    storageAvailable = true;
    elements.autosaveStatus.textContent = `Черновик сохранён локально · ${timeFormatter.format(
      new Date(state.savedAt),
    )}`;
  } catch {
    storageAvailable = false;
    elements.autosaveStatus.textContent = "Черновик хранится только до закрытия страницы.";
  }
  showStorageWarning();
};

const scheduleSave = () => {
  elements.autosaveStatus.textContent = "Сохраняем черновик…";
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(persistState, 180);
};

const entryFor = (itemId) => state.entries[itemId] || null;

const ensureEntry = (itemId) => {
  if (!state.entries[itemId]) {
    const item = items.find((candidate) => candidate.id === itemId);
    state.entries[itemId] = {
      rating: null,
      feedback: "",
      status: "draft",
      completedAt: null,
      updatedAt: nowIso(),
      reviewBasisSha256: item?.review_basis_sha256 || null,
    };
  }
  return state.entries[itemId];
};

const markCurrentDraft = (changes) => {
  const item = items[activeIndex];
  const entry = ensureEntry(item.id);
  Object.assign(entry, changes, {
    status: "draft",
    completedAt: null,
    updatedAt: nowIso(),
  });
  state.activeItemId = item.id;
  state.savedAt = null;
  scheduleSave();
  renderProgress();
  renderNavigatorOptions();
  elements.submitStatus.textContent = "";
  elements.submitButton.textContent = "Сохранить оценку и перейти дальше";
};

const formatBytes = (bytes) => {
  const mebibytes = Number(bytes) / 1024 / 1024;
  return Number.isFinite(mebibytes) ? `${decimalFormatter.format(mebibytes)} МиБ` : "—";
};

const formatDuration = (seconds) =>
  Number.isFinite(Number(seconds)) ? `${decimalFormatter.format(Number(seconds))} с` : "—";

const showToast = (message) => {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  toastTimer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 3600);
};

const clearValidation = () => {
  elements.ratingFieldset.classList.remove("hasError");
  elements.ratingError.hidden = true;
  elements.feedbackError.hidden = true;
  elements.feedback.removeAttribute("aria-invalid");
};

const renderProgress = () => {
  const entries = Object.values(state.entries);
  const completed = entries.filter((entry) => entry.status === "completed").length;
  const drafts = entries.filter(
    (entry) => entry.status !== "completed" && (entry.rating || entry.feedback.trim()),
  ).length;
  const total = items.length;

  elements.progressLabel.textContent = `${completed} из ${total} оценено`;
  elements.draftCount.textContent = drafts
    ? `${drafts} ${draftLabels[pluralRules.select(drafts)]}`
    : "Черновиков пока нет";
  elements.progressTrack.setAttribute("aria-valuemax", String(total));
  elements.progressTrack.setAttribute("aria-valuenow", String(completed));
  elements.progressBar.style.width = `${total ? (completed / total) * 100 : 0}%`;
};

const itemStatus = (itemId) => {
  const entry = entryFor(itemId);
  if (entry?.status === "completed") return "готово";
  if (entry && (entry.rating || entry.feedback.trim())) return "черновик";
  return "не оценено";
};

const itemGroupId = (item) => item.review_group?.id || "ungrouped";
const contextAvailability = (item) =>
  typeof item.context_status === "string"
    ? item.context_status
    : item.context_status?.availability || (item.context ? "shown" : "not_available_in_artifacts");

const reviewGroups = () => {
  const groups = new Map();
  items.forEach((item) => {
    const id = itemGroupId(item);
    if (!groups.has(id)) {
      const rawOrder = Number(item.review_group?.order);
      groups.set(id, {
        id,
        label: item.review_group?.label || "Без группы",
        shortLabel: item.review_group?.short_label || item.review_group?.label || "Без группы",
        order: Number.isFinite(rawOrder) ? rawOrder : Number.MAX_SAFE_INTEGER,
        count: 0,
      });
    }
    groups.get(id).count += 1;
  });
  return Array.from(groups.values()).sort(
    (left, right) => left.order - right.order || left.label.localeCompare(right.label, "ru"),
  );
};

const visibleItemIndexes = () =>
  items.reduce((indexes, item, index) => {
    if (activeGroupFilter === "all" || itemGroupId(item) === activeGroupFilter) {
      indexes.push(index);
    }
    return indexes;
  }, []);

const renderGroupFilter = () => {
  const options = [];
  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = `Все подходы · ${items.length}`;
  allOption.selected = activeGroupFilter === "all";
  options.push(allOption);

  reviewGroups().forEach((group) => {
    const option = document.createElement("option");
    option.value = group.id;
    option.textContent = `${group.label} · ${group.count}`;
    option.selected = activeGroupFilter === group.id;
    options.push(option);
  });
  elements.groupFilter.replaceChildren(...options);
};

const renderNavigatorOptions = () => {
  const selectedId = items[activeIndex]?.id;
  const indexes = visibleItemIndexes();
  const groups = reviewGroups().filter(
    (group) => activeGroupFilter === "all" || group.id === activeGroupFilter,
  );
  const children = groups.map((group) => {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.label;
    indexes
      .filter((index) => itemGroupId(items[index]) === group.id)
      .forEach((index) => {
        const item = items[index];
      const option = document.createElement("option");
      option.value = item.id;
        option.textContent = `${String(index + 1).padStart(2, "0")} · ${item.prompt_author?.id || item.agent?.id || "—"} · ${item.model.label} · ${
        item.article.label || item.sample_id
      } · ${itemStatus(item.id)}`;
      option.selected = item.id === selectedId;
        optgroup.append(option);
      });
    return optgroup;
  });
  elements.itemSelect.replaceChildren(...children);
  renderGroupFilter();
};

const renderVideoFacts = (item) => {
  const facts = [
    ["Длительность", formatDuration(item.video.duration_seconds)],
    ["Геометрия", `${item.video.width} × ${item.video.height}`],
    ["Частота", `${decimalFormatter.format(item.video.fps)} fps`],
    ["Размер", formatBytes(item.video.bytes)],
  ];
  elements.videoFacts.replaceChildren(
    ...facts.map(([label, value]) => {
      const wrapper = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = value;
      wrapper.append(term, description);
      return wrapper;
    }),
  );
};

const technicalNote = (label, text, warning = false) => {
  const paragraph = document.createElement("p");
  paragraph.className = `technicalNote${warning ? " technicalNoteWarning" : ""}`;
  const heading = document.createElement("strong");
  const body = document.createElement("span");
  heading.textContent = label;
  body.textContent = text;
  paragraph.append(heading, body);
  return paragraph;
};

const renderTechnicalNotes = (item) => {
  const notes = [];
  const expansion = item.prompt.prompt_expansion || { mode: "not_recorded" };

  const availability = contextAvailability(item);
  if (availability === "omitted_by_review_policy" || availability === "not_shown_by_review_policy") {
    notes.push(
      technicalNote(
        "Контекст",
        "Контекст статьи не показывается для этой исторической итерации. Оценивайте видео относительно промпта.",
      ),
    );
  } else if (availability === "not_available_in_artifacts" || availability === "not_provided") {
    notes.push(
      technicalNote(
        "Контекст",
        "В исторических артефактах этой итерации нет контекста статьи. Оценивайте видео относительно промпта.",
      ),
    );
  }

  if (item.prompt.native_for_generation_model === false && item.prompt.source_model_id) {
    notes.push(
      technicalNote(
        "Cross-model control",
        `Промпт подготовлен для ${modelLabelFor(item.prompt.source_model_id)} → видео сгенерировано ${item.model.label}. Это перенос, а не нативная практика целевой модели.`,
      ),
    );
  }

  if (expansion.mode === "enabled") {
    notes.push(
      technicalNote(
        "Prompt processing",
        `В provider-запросе включён ${expansion.parameter}=true. Провайдер мог расширить формулировку; расширенный текст не сохранён.`,
      ),
    );
  } else if (expansion.mode === "not_exposed") {
    notes.push(
      technicalNote(
        "Prompt processing",
        "Wan 2.2 route не раскрывает provider expansion. Показан точный prompt, переданный генератору.",
      ),
    );
  }

  if (item.prompt.negative_transport === "embedded_in_positive") {
    notes.push(
      technicalNote(
        "Prompt transport",
        "Авторские основной и negative prompt показаны раздельно; в provider-запросе ограничения были добавлены к основному тексту через «Avoid:».",
      ),
    );
  }

  if (
    item.prompt_author?.attribution_basis === "legacy-route-mapping" ||
    item.prompt_author?.attribution_basis === "legacy_generator_field"
  ) {
    notes.push(
      technicalNote(
        "Атрибуция",
        "Тег clipmaker-classic восстановлен по историческому маршруту «project clipmaker agent»; отдельного agent_id в старом артефакте нет.",
      ),
    );
  }

  if (item.provider_contract?.conforms === false) {
    const warningText = (item.provider_contract.warnings || [])
      .map((warning) => warningLabels[warning] || warning)
      .join("; ");
    notes.push(
      technicalNote(
        "Provider deviation",
        `${warningText}. Это транспортная пометка, а не оценка промпта клипмейкера.`,
        true,
      ),
    );
  }
  elements.technicalNotes.replaceChildren(...notes);
};

const renderContext = (item) => {
  const hasContext = Boolean(item.context);
  elements.contextSection.hidden = !hasContext;
  elements.promptIndex.textContent = `${hasContext ? "02" : "01"} · Формулировка`;
  elements.ratingIndex.textContent = `${hasContext ? "03" : "02"} · Общая оценка`;
  elements.guideIndex.textContent = `${hasContext ? "04" : "03"} · Ориентир`;
  elements.feedbackIndex.textContent = `${hasContext ? "05" : "04"} · Обратная связь`;
  elements.ratingQuestion.textContent = hasContext
    ? "Насколько результат соответствует контексту и промпту?"
    : "Насколько результат соответствует промпту?";
  elements.intentionGuide.textContent = hasContext
    ? "Какое действие или состояние задают контекст и промпт?"
    : "Какое действие или состояние задаёт промпт?";

  if (!hasContext) {
    elements.articleIdentity.replaceChildren();
    elements.contextDetails.replaceChildren();
    elements.contextFragments.replaceChildren();
    elements.articleLink.hidden = true;
    elements.articleLink.removeAttribute("href");
    return;
  }

  elements.articleIdentity.replaceChildren();
  const title = document.createElement("strong");
  const lead = document.createElement("span");
  title.textContent = item.context.title || item.article.label || item.sample_id;
  lead.textContent = item.context.lead || "Лид в исходном контексте отсутствует";
  elements.articleIdentity.append(title, lead);

  const contextDetails = [];
  const appendContextDetail = (label, value) => {
    if (typeof value !== "string" || !value.trim()) return;
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    wrapper.append(term, description);
    contextDetails.push(wrapper);
  };
  appendContextDetail("Раздел статьи", item.context.current_heading?.text);
  appendContextDetail("Подпись к изображению", item.context.caption);
  elements.contextDetails.replaceChildren(...contextDetails);
  elements.contextDetails.hidden = contextDetails.length === 0;

  if (item.article.url) {
    elements.articleLink.href = item.article.url;
    elements.articleLink.hidden = false;
  } else {
    elements.articleLink.hidden = true;
    elements.articleLink.removeAttribute("href");
  }

  const fragmentLabels = { before: "До изображения", after: "После изображения" };
  elements.contextFragments.replaceChildren(
    ...item.context.fragments.map((fragment) => {
      const article = document.createElement("article");
      article.className = "contextFragment";
      const label = document.createElement("small");
      const paragraph = document.createElement("p");
      label.textContent = fragmentLabels[fragment.relation] || "Фрагмент";
      paragraph.textContent = fragment.text;
      article.append(label, paragraph);
      return article;
    }),
  );
};

const renderPrompt = (item) => {
  const author = item.prompt_author || item.agent || {};
  const contractSuffix = author.contract_version ? ` · contract ${author.contract_version}` : "";
  elements.agentLabel.textContent = `Промпт · ${author.id || "автор не указан"}${contractSuffix}`;
  elements.positivePrompt.textContent = item.prompt.positive;
  const expansion = item.prompt.prompt_expansion || {};
  const provider = item.prompt.provider || "provider не указан";
  elements.providerNote.textContent =
    expansion.mode === "enabled"
      ? `Provider: ${provider}. Ниже показан точный авторский output до возможного расширения ${expansion.parameter}.`
      : `Provider: ${provider}. Ниже показан точный авторский output клипмейкера.`;

  const hasNegative = typeof item.prompt.negative === "string" && item.prompt.negative.trim();
  elements.negativePromptBlock.hidden = !hasNegative;
  elements.negativePromptStatus.hidden = Boolean(hasNegative);
  elements.negativePrompt.textContent = hasNegative ? item.prompt.negative : "";
};

const renderFormState = (item) => {
  const entry = entryFor(item.id);
  elements.ratingInputs.forEach((input) => {
    input.checked = Number(input.value) === entry?.rating;
  });
  elements.feedback.value = entry?.feedback || "";
  elements.feedbackRequirement.textContent =
    entry?.rating === 3 ? "Желателен, но не обязателен" : "Обязателен для оценок 1 и 2";
  elements.autosaveStatus.textContent = entry?.updatedAt
    ? `${entry.status === "completed" ? "Оценка завершена" : "Черновик сохранён"} · ${timeFormatter.format(
        new Date(entry.updatedAt),
      )}`
    : "Черновик сохраняется автоматически.";
  elements.submitStatus.textContent = entry?.status === "completed" ? "Эта оценка уже завершена." : "";
  elements.submitButton.textContent = "Сохранить оценку и перейти дальше";
  clearValidation();
};

const syncUrl = (item) => {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set("item", item.id);
    if (activeGroupFilter === "all") url.searchParams.delete("group");
    else url.searchParams.set("group", activeGroupFilter);
    window.history.replaceState({ item: item.id }, "", url);
  } catch {
    // Direct file previews can reject History API writes; local state still restores the item.
  }
};

const renderActiveItem = ({ focusContext = false, persist = true } = {}) => {
  const item = items[activeIndex];
  if (!item) return;
  state.activeItemId = item.id;
  hasMediaError = false;
  elements.mediaError.hidden = true;
  elements.submitButton.disabled = false;
  elements.submitButton.removeAttribute("aria-disabled");

  elements.currentNumber.textContent = String(activeIndex + 1).padStart(2, "0");
  elements.totalNumber.textContent = String(items.length);
  elements.clipTitle.textContent = item.article.label || item.sample_id;
  const promptAuthorId = item.prompt_author?.id || item.agent?.id || "—";
  elements.authorBadge.textContent = `Промпт · ${promptAuthorId}`;
  elements.approachBadge.textContent =
    item.approach?.label || item.review_group?.short_label || item.review_group?.label || "—";
  elements.modelBadge.textContent = item.model.label;
  elements.navigationStatus.textContent =
    `Видео ${activeIndex + 1} из ${items.length}. Промпт: ${promptAuthorId}. ` +
    `Подход: ${elements.approachBadge.textContent}. Модель: ${item.model.label}. ` +
    `${item.article.label || item.sample_id}.`;
  const navigatorIndexes = visibleItemIndexes();
  const navigatorPosition = navigatorIndexes.indexOf(activeIndex);
  elements.previousButton.disabled = navigatorPosition <= 0;
  elements.nextButton.disabled =
    navigatorPosition < 0 || navigatorPosition === navigatorIndexes.length - 1;

  elements.video.pause();
  elements.video.removeAttribute("src");
  elements.video.src = `../${item.video.path}`;
  elements.video.setAttribute(
    "aria-label",
    `${item.model.label}: ${item.article.label || item.sample_id}`,
  );
  elements.video.load();

  renderVideoFacts(item);
  renderTechnicalNotes(item);
  renderContext(item);
  renderPrompt(item);
  renderFormState(item);
  renderNavigatorOptions();
  renderProgress();
  syncUrl(item);
  if (persist) scheduleSave();

  const scrollBehavior = reducedMotionQuery.matches ? "auto" : "smooth";
  if (desktopLayoutQuery.matches) {
    elements.panel.scrollTo({ top: 0, behavior: scrollBehavior });
    if (focusContext) {
      (item.context ? elements.contextTitle : elements.promptTitle).focus({ preventScroll: true });
    }
  } else if (focusContext) {
    const videoColumnTop = elements.videoColumn.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: videoColumnTop, behavior: scrollBehavior });
    elements.clipTitle.focus({ preventScroll: true });
  }
};

const navigateTo = (index, options = {}) => {
  const boundedIndex = Math.min(Math.max(index, 0), items.length - 1);
  if (boundedIndex === activeIndex && !options.force) return;
  persistState();
  activeIndex = boundedIndex;
  renderActiveItem(options);
};

const navigateWithinFilter = (offset) => {
  const indexes = visibleItemIndexes();
  const position = indexes.indexOf(activeIndex);
  const target = indexes[position + offset];
  if (typeof target === "number") navigateTo(target);
};

const validateCurrent = () => {
  clearValidation();
  if (hasMediaError) {
    elements.submitStatus.textContent = "Сначала восстановите доступ к видео.";
    elements.video.focus();
    return false;
  }

  const item = items[activeIndex];
  const entry = entryFor(item.id);
  if (!entry || !isValidRating(entry.rating)) {
    elements.ratingFieldset.classList.add("hasError");
    elements.ratingError.hidden = false;
    elements.ratingInputs[0].focus();
    return false;
  }

  if (entry.rating < 3 && !entry.feedback.trim()) {
    elements.feedbackError.hidden = false;
    elements.feedback.setAttribute("aria-invalid", "true");
    elements.feedback.focus();
    return false;
  }
  return true;
};

const nextIncompleteIndex = () => {
  const indexes = visibleItemIndexes();
  const position = indexes.indexOf(activeIndex);
  if (position < 0) return -1;
  for (let offset = 1; offset <= indexes.length; offset += 1) {
    const candidate = indexes[(position + offset) % indexes.length];
    if (state.entries[items[candidate].id]?.status !== "completed") return candidate;
  }
  return -1;
};

const buildExport = () => reviewCore.buildExport(dataset, state, nowIso());

const exportJson = () => {
  persistState();
  const artifact = buildExport();
  const blob = new Blob([`${JSON.stringify(artifact, null, 2)}\n`], {
    type: "application/json;charset=utf-8",
  });
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const date = artifact.exported_at.slice(0, 10);
  link.href = href;
  link.download = `clipmaker-quality-annotations-${date}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 0);
  showToast(
    `JSON скачан: ${artifact.summary.completed} завершено, ${artifact.summary.drafts} в черновиках.`,
  );
};

const initialize = () => {
  if (!isDatasetValid) {
    elements.workspace.hidden = true;
    elements.datasetError.hidden = false;
    elements.exportButton.disabled = true;
    elements.datasetErrorText.textContent =
      "review-data.js отсутствует или не соответствует schema_version 2. Пересоберите allowlist и перезагрузите страницу.";
    return;
  }

  state = loadState();
  const requestUrl = new URL(window.location.href);
  const requestedGroup = requestUrl.searchParams.get("group");
  if (reviewGroups().some((group) => group.id === requestedGroup)) {
    activeGroupFilter = requestedGroup;
  }
  const requestedItem = requestUrl.searchParams.get("item");
  const requestedIndex = items.findIndex((item) => item.id === requestedItem);
  const storedIndex = items.findIndex((item) => item.id === state.activeItemId);
  activeIndex = requestedIndex >= 0 ? requestedIndex : Math.max(storedIndex, 0);
  if (!visibleItemIndexes().includes(activeIndex)) {
    activeIndex = visibleItemIndexes()[0] ?? 0;
  }
  elements.totalNumber.textContent = String(items.length);
  showStorageWarning();
  renderActiveItem();
};

elements.ratingInputs.forEach((input) => {
  input.addEventListener("change", () => {
    const rating = Number(input.value);
    markCurrentDraft({ rating });
    elements.feedbackRequirement.textContent =
      rating === 3 ? "Желателен, но не обязателен" : "Обязателен для оценок 1 и 2";
    elements.ratingFieldset.classList.remove("hasError");
    elements.ratingError.hidden = true;
  });
});

elements.feedback.addEventListener("input", () => {
  markCurrentDraft({ feedback: elements.feedback.value });
  elements.feedbackError.hidden = true;
  elements.feedback.removeAttribute("aria-invalid");
});

elements.feedback.addEventListener("change", persistState);
elements.previousButton.addEventListener("click", () => navigateWithinFilter(-1));
elements.nextButton.addEventListener("click", () => navigateWithinFilter(1));
elements.groupFilter.addEventListener("change", () => {
  activeGroupFilter = elements.groupFilter.value;
  const indexes = visibleItemIndexes();
  const targetIndex = indexes.includes(activeIndex) ? activeIndex : indexes[0];
  if (typeof targetIndex === "number") navigateTo(targetIndex, { force: true });
});
elements.itemSelect.addEventListener("change", () => {
  const index = items.findIndex((item) => item.id === elements.itemSelect.value);
  if (index >= 0) navigateTo(index);
});

elements.replayButton.addEventListener("click", () => {
  elements.video.currentTime = 0;
  const playPromise = elements.video.play();
  if (playPromise) {
    playPromise.catch(() => {
      showToast("Видео возвращено к первому кадру. Запустите его встроенной кнопкой.");
    });
  }
});

elements.video.addEventListener("loadedmetadata", () => {
  hasMediaError = false;
  elements.mediaError.hidden = true;
  elements.submitButton.disabled = false;
  elements.submitButton.removeAttribute("aria-disabled");
});

elements.video.addEventListener("error", () => {
  hasMediaError = true;
  elements.mediaError.hidden = false;
  elements.submitButton.disabled = true;
  elements.submitButton.setAttribute("aria-disabled", "true");
});

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!validateCurrent()) return;

  const item = items[activeIndex];
  const entry = ensureEntry(item.id);
  const completedAt = nowIso();
  Object.assign(entry, {
    feedback: entry.feedback.trim(),
    status: "completed",
    completedAt,
    updatedAt: completedAt,
  });
  elements.feedback.value = entry.feedback;
  state.savedAt = null;
  persistState();
  renderProgress();
  renderNavigatorOptions();

  const nextIndex = nextIncompleteIndex();
  if (nextIndex >= 0) {
    showToast("Оценка сохранена. Открываю следующую незавершённую генерацию.");
    navigateTo(nextIndex, { focusContext: true, force: true });
  } else if (
    activeGroupFilter !== "all" &&
    items.some((candidate) => state.entries[candidate.id]?.status !== "completed")
  ) {
    elements.submitStatus.textContent =
      "Все генерации в выбранном подходе оценены. Выберите другой подход или покажите весь набор.";
    elements.submitButton.textContent = "Сохранить изменения";
    showToast("Выбранный подход полностью оценён.");
  } else {
    elements.submitStatus.textContent = "Все генерации оценены. Результат готов к экспорту.";
    elements.submitButton.textContent = "Сохранить изменения";
    showToast(`Все ${items.length} генераций оценены. Экспортируйте итоговый JSON.`);
  }
});

elements.exportButton.addEventListener("click", exportJson);

window.addEventListener("pagehide", persistState);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") persistState();
});

window.addEventListener("storage", (event) => {
  if (event.key !== storageKey || !event.newValue) return;
  try {
    const rawIncoming = JSON.parse(event.newValue);
    if (!reviewCore.isSameDatasetState(rawIncoming, dataset)) {
      showToast("В другой вкладке открыта иная версия набора. Перезагрузите её перед продолжением.");
      return;
    }
    const incoming = normalizeState(rawIncoming);
    const merged = reviewCore.mergeStates(state, incoming);
    if (!merged.hasIncomingChanges && !merged.needsWrite) return;
    const activeItem = items[activeIndex];
    const previousActiveEntry = entryFor(activeItem.id);
    state = merged.state;
    const nextActiveEntry = entryFor(activeItem.id);
    renderProgress();
    renderNavigatorOptions();
    if (JSON.stringify(previousActiveEntry) !== JSON.stringify(nextActiveEntry)) {
      renderFormState(activeItem);
    }
    if (merged.needsWrite && !saveTimer) persistState();
    showToast("Оценки объединены с изменениями из другой вкладки.");
  } catch {
    // Ignore malformed external storage events; the current in-memory draft remains intact.
  }
});

initialize();
