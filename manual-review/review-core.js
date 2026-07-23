(function registerQualityReviewCore(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.qualityReviewCore = api;
})(typeof window === "object" ? window : globalThis, function createQualityReviewCore() {
  "use strict";

  const STATE_SCHEMA_VERSION = 2;

  const isValidRating = (value) => [1, 2, 3].includes(value);
  const normalizeDateTime = (value, fallback = null) => {
    if (typeof value !== "string") return fallback;
    const milliseconds = Date.parse(value);
    if (!Number.isFinite(milliseconds)) return fallback;
    return new Date(milliseconds).toISOString();
  };
  const entryHasContent = (entry) =>
    Boolean(entry && (isValidRating(entry.rating) || String(entry.feedback || "").trim()));
  const isCompletable = (entry) =>
    Boolean(
      entry &&
        isValidRating(entry.rating) &&
        (entry.rating === 3 || String(entry.feedback || "").trim()),
    );

  const freshState = (dataset, timestamp) => ({
    schemaVersion: STATE_SCHEMA_VERSION,
    datasetId: dataset.dataset_id,
    sessionStartedAt: timestamp,
    savedAt: null,
    activeItemId: dataset.items[0]?.id || null,
    entries: {},
  });

  const normalizeEntry = (value, timestamp, expectedBasisSha256 = null, trustLegacy = false) => {
    if (!value || typeof value !== "object") return null;
    const reviewBasisSha256 = trustLegacy
      ? expectedBasisSha256
      : value.reviewBasisSha256;
    if (expectedBasisSha256 && reviewBasisSha256 !== expectedBasisSha256) return null;
    const rating = Number(value.rating);
    const feedback = typeof value.feedback === "string" ? value.feedback : "";
    const completedAt = normalizeDateTime(value.completedAt);
    const completed =
      value.status === "completed" && completedAt && isCompletable({ rating, feedback });
    return {
      rating: isValidRating(rating) ? rating : null,
      feedback,
      status: completed ? "completed" : "draft",
      completedAt: completed ? completedAt : null,
      updatedAt: normalizeDateTime(value.updatedAt, timestamp),
      reviewBasisSha256: expectedBasisSha256 || null,
    };
  };

  const normalizeCompatibleState = (value, dataset, timestamp, trustLegacy = false) => {
    const itemsById = new Map(dataset.items.map((item) => [item.id, item]));
    const entries = {};
    if (value.entries && typeof value.entries === "object") {
      Object.entries(value.entries).forEach(([itemId, entry]) => {
        const item = itemsById.get(itemId);
        const normalized = item
          ? normalizeEntry(entry, timestamp, item.review_basis_sha256, trustLegacy)
          : null;
        if (normalized) entries[itemId] = normalized;
      });
    }

    return {
      schemaVersion: STATE_SCHEMA_VERSION,
      datasetId: dataset.dataset_id,
      sessionStartedAt: normalizeDateTime(value.sessionStartedAt, timestamp),
      savedAt: normalizeDateTime(value.savedAt),
      activeItemId: itemsById.has(value.activeItemId)
        ? value.activeItemId
        : dataset.items[0]?.id || null,
      entries,
    };
  };

  const migrateState = (value, dataset, timestamp) => {
    if (!value || typeof value !== "object") return freshState(dataset, timestamp);

    const isCurrentState =
      value.schemaVersion === STATE_SCHEMA_VERSION && value.datasetId === dataset.dataset_id;
    if (isCurrentState) return normalizeCompatibleState(value, dataset, timestamp);

    // The v2 storage key is stable per review ticket. A later dataset revision may add
    // items without invalidating unchanged annotations; the per-item basis hash decides
    // which entries are still safe to carry forward.
    if (value.schemaVersion === STATE_SCHEMA_VERSION) {
      return normalizeCompatibleState(value, dataset, timestamp);
    }

    const supersededDatasetIds = Array.isArray(dataset.supersedes_dataset_ids)
      ? dataset.supersedes_dataset_ids
      : [];
    const isSupportedLegacyState =
      value.schemaVersion === 1 && supersededDatasetIds.includes(value.datasetId);
    if (isSupportedLegacyState) {
      return normalizeCompatibleState(value, dataset, timestamp, true);
    }

    return freshState(dataset, timestamp);
  };

  const normalizeState = migrateState;
  const isSameDatasetState = (value, dataset) =>
    Boolean(
      value &&
        value.schemaVersion === STATE_SCHEMA_VERSION &&
        value.datasetId === dataset.dataset_id,
    );

  const entryTime = (entry) => Date.parse(entry?.updatedAt || "") || 0;
  const serializeEntry = (entry) => JSON.stringify(entry);

  const mergeStates = (current, incoming) => {
    const entries = {};
    let hasIncomingChanges = false;
    let needsWrite = false;
    const itemIds = new Set([
      ...Object.keys(current.entries || {}),
      ...Object.keys(incoming.entries || {}),
    ]);

    itemIds.forEach((itemId) => {
      const localEntry = current.entries?.[itemId];
      const incomingEntry = incoming.entries?.[itemId];
      if (!localEntry) {
        entries[itemId] = incomingEntry;
        hasIncomingChanges = true;
        return;
      }
      if (!incomingEntry) {
        entries[itemId] = localEntry;
        needsWrite = true;
        return;
      }

      const localTime = entryTime(localEntry);
      const incomingTime = entryTime(incomingEntry);
      const localSerialized = serializeEntry(localEntry);
      const incomingSerialized = serializeEntry(incomingEntry);
      const incomingWinsTie =
        incomingTime === localTime && incomingSerialized > localSerialized;
      if (incomingTime > localTime || incomingWinsTie) {
        entries[itemId] = incomingEntry;
        hasIncomingChanges ||= localSerialized !== incomingSerialized;
      } else {
        entries[itemId] = localEntry;
        needsWrite ||= localTime > incomingTime || localSerialized !== incomingSerialized;
      }
    });

    const currentSavedAt = Date.parse(current.savedAt || "") || 0;
    const incomingSavedAt = Date.parse(incoming.savedAt || "") || 0;
    return {
      state: {
        ...current,
        entries,
        savedAt: incomingSavedAt > currentSavedAt ? incoming.savedAt : current.savedAt,
      },
      hasIncomingChanges,
      needsWrite,
    };
  };

  const nextIncompleteIndex = (items, entries, activeIndex) => {
    for (let offset = 1; offset <= items.length; offset += 1) {
      const candidate = (activeIndex + offset) % items.length;
      if (entries[items[candidate].id]?.status !== "completed") return candidate;
    }
    return -1;
  };

  const snapshotRecord = (dataset, item, entry) => ({
    annotation_id: `${dataset.review_ticket}:${item.id}`,
    item_id: item.id,
    video: {
      id: item.video.id,
      path: item.video.path,
      sha256: item.video.sha256,
    },
    context_snapshot: item.context ?? null,
    context_status: item.context_status,
    prompt_snapshot: item.prompt,
    prompt_author: item.prompt_author,
    review_group: item.review_group,
    approach: item.approach,
    review_basis_sha256: item.review_basis_sha256,
    rating: entry.rating,
    feedback: entry.feedback,
    agent_id: item.prompt_author?.id || item.agent?.id || null,
    model_id: item.model.id,
    run_id: item.agent?.planning_run_id ?? null,
    batch_id: item.agent?.batch_id ?? null,
    author_thread_id: item.agent?.author_thread_id ?? null,
    generation_job_id: item.generation?.job_id ?? null,
    request_sha256: item.generation.request_sha256,
    provider_contract: item.provider_contract,
    completed_at: entry.completedAt,
    updated_at: entry.updatedAt,
  });

  const buildExport = (dataset, state, exportedAt) => {
    const annotations = [];
    const drafts = [];
    dataset.items.forEach((item) => {
      const entry = state.entries[item.id];
      if (!entryHasContent(entry)) return;
      const isCompleted = entry.status === "completed" && isCompletable(entry);
      const exportEntry = isCompleted ? entry : { ...entry, completedAt: null };
      const record = snapshotRecord(dataset, item, exportEntry);
      if (isCompleted) annotations.push(record);
      else drafts.push(record);
    });

    return {
      schema_version: 2,
      artifact_kind: "clipmaker-quality-annotations",
      review_ticket: dataset.review_ticket,
      dataset: {
        id: dataset.dataset_id,
        data_sha256: dataset.data_sha256,
        sources: dataset.sources,
      },
      session_started_at: state.sessionStartedAt,
      exported_at: exportedAt,
      summary: {
        total: dataset.items.length,
        completed: annotations.length,
        drafts: drafts.length,
      },
      annotations,
      drafts,
    };
  };

  return {
    buildExport,
    entryHasContent,
    freshState,
    isCompletable,
    isSameDatasetState,
    isValidRating,
    mergeStates,
    migrateState,
    nextIncompleteIndex,
    normalizeEntry,
    normalizeState,
    snapshotRecord,
  };
});
