(function registerQualityReviewCore(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.qualityReviewCore = api;
})(typeof window === "object" ? window : globalThis, function createQualityReviewCore() {
  "use strict";

  const isValidRating = (value) => [1, 2, 3].includes(value);
  const entryHasContent = (entry) =>
    Boolean(entry && (isValidRating(entry.rating) || String(entry.feedback || "").trim()));
  const isCompletable = (entry) =>
    Boolean(
      entry &&
        isValidRating(entry.rating) &&
        (entry.rating === 3 || String(entry.feedback || "").trim()),
    );

  const freshState = (dataset, timestamp) => ({
    schemaVersion: 1,
    datasetId: dataset.dataset_id,
    sessionStartedAt: timestamp,
    savedAt: null,
    activeItemId: dataset.items[0]?.id || null,
    entries: {},
  });

  const normalizeEntry = (value, timestamp) => {
    if (!value || typeof value !== "object") return null;
    const rating = Number(value.rating);
    const feedback = typeof value.feedback === "string" ? value.feedback : "";
    const completed = value.status === "completed" && isCompletable({ rating, feedback });
    return {
      rating: isValidRating(rating) ? rating : null,
      feedback,
      status: completed ? "completed" : "draft",
      completedAt:
        completed && typeof value.completedAt === "string" ? value.completedAt : null,
      updatedAt: typeof value.updatedAt === "string" ? value.updatedAt : timestamp,
    };
  };

  const normalizeState = (value, dataset, timestamp) => {
    if (!value || value.datasetId !== dataset.dataset_id || value.schemaVersion !== 1) {
      return freshState(dataset, timestamp);
    }

    const validItemIds = new Set(dataset.items.map((item) => item.id));
    const entries = {};
    if (value.entries && typeof value.entries === "object") {
      Object.entries(value.entries).forEach(([itemId, entry]) => {
        const normalized = normalizeEntry(entry, timestamp);
        if (validItemIds.has(itemId) && normalized) entries[itemId] = normalized;
      });
    }

    return {
      schemaVersion: 1,
      datasetId: dataset.dataset_id,
      sessionStartedAt:
        typeof value.sessionStartedAt === "string" ? value.sessionStartedAt : timestamp,
      savedAt: typeof value.savedAt === "string" ? value.savedAt : null,
      activeItemId: validItemIds.has(value.activeItemId)
        ? value.activeItemId
        : dataset.items[0]?.id || null,
      entries,
    };
  };

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
    annotation_id: `${dataset.dataset_id}:${item.id}`,
    item_id: item.id,
    video: {
      id: item.video.id,
      path: item.video.path,
      sha256: item.video.sha256,
    },
    context_snapshot: item.context,
    prompt_snapshot: item.prompt,
    rating: entry.rating,
    feedback: entry.feedback,
    agent_id: item.agent.id,
    model_id: item.model.id,
    run_id: item.agent.planning_run_id,
    batch_id: item.agent.batch_id,
    author_thread_id: item.agent.author_thread_id,
    generation_job_id: item.generation.job_id,
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
      schema_version: 1,
      artifact_kind: "clipmaker-quality-annotations",
      review_ticket: dataset.review_ticket,
      dataset: {
        id: dataset.dataset_id,
        source_ticket: dataset.source.ticket,
        batch_id: dataset.source.batch_id,
        manifest_path: dataset.source.manifest_path,
        manifest_sha256: dataset.source.manifest_sha256,
        data_sha256: dataset.source.data_sha256,
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
    isValidRating,
    mergeStates,
    nextIncompleteIndex,
    normalizeEntry,
    normalizeState,
    snapshotRecord,
  };
});
