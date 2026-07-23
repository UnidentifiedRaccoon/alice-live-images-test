"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const core = require("../manual-review/review-core.js");

const timestamp = "2026-07-23T10:00:00.000Z";
const basisSha256 = "f".repeat(64);
const makeEntry = (overrides = {}) => ({
  rating: 3,
  feedback: "",
  status: "completed",
  completedAt: timestamp,
  updatedAt: timestamp,
  reviewBasisSha256: basisSha256,
  ...overrides,
});

const makeItem = (id) => ({
  id,
  video: { id, path: `video/${id}.mp4`, sha256: "a".repeat(64) },
  context: { title: `Context ${id}`, fragments: [{ relation: "before", text: "Text" }] },
  context_status: { availability: "shown", reason: null },
  prompt: { positive: `Prompt ${id}`, negative: null },
  prompt_author: {
    id: "clipmaker-lite",
    label: "Clipmaker Lite",
    contract_version: "1.1.1",
    attribution_basis: "verified-runner-provenance",
    provenance_verified: true,
  },
  review_group: {
    id: "lite-current",
    label: "Clipmaker Lite · текущая итерация",
    short_label: "Lite · текущая",
    order: 1,
  },
  approach: { id: "lite-model-native", label: "Нативный модельный промпт" },
  review_basis_sha256: basisSha256,
  agent: {
    id: "clipmaker-lite",
    planning_run_id: `run-${id}`,
    batch_id: "batch-1",
    author_thread_id: `thread-${id}`,
  },
  model: { id: "alibaba/wan-2.2" },
  generation: { job_id: `job-${id}`, request_sha256: "b".repeat(64) },
  provider_contract: { conforms: true, warnings: [] },
});

const dataset = {
  schema_version: 2,
  dataset_id: "batch-1@dataset",
  supersedes_dataset_ids: ["batch-1@old-dataset"],
  review_ticket: "PROMOPAGES-9897",
  data_sha256: "9".repeat(64),
  sources: [
    {
      id: "lite-current",
      ticket: "PROMOPAGES-9891",
      batch_id: "batch-1",
      manifest_path: "manifest.json",
      manifest_sha256: "c".repeat(64),
      data_sha256: "d".repeat(64),
    },
  ],
  items: [makeItem("one"), makeItem("two"), makeItem("three")],
};

test("rating and feedback completion rules match the annotation contract", () => {
  assert.equal(core.isCompletable(makeEntry({ rating: 1, feedback: "" })), false);
  assert.equal(core.isCompletable(makeEntry({ rating: 2, feedback: "   " })), false);
  assert.equal(core.isCompletable(makeEntry({ rating: 2, feedback: "Есть артефакт" })), true);
  assert.equal(core.isCompletable(makeEntry({ rating: 3, feedback: "" })), true);
  assert.equal(core.isCompletable(makeEntry({ rating: 4 })), false);
});

test("stored state restores valid entries and demotes an invalid completion to draft", () => {
  const restored = core.normalizeState(
    {
      schemaVersion: 2,
      datasetId: dataset.dataset_id,
      sessionStartedAt: timestamp,
      savedAt: timestamp,
      activeItemId: "two",
      entries: {
        one: makeEntry({ rating: 1, feedback: "" }),
        two: makeEntry({ rating: 3 }),
        unknown: makeEntry({ rating: 3 }),
      },
    },
    dataset,
    timestamp,
  );

  assert.equal(restored.activeItemId, "two");
  assert.equal(restored.entries.one.status, "draft");
  assert.equal(restored.entries.one.completedAt, null);
  assert.equal(restored.entries.two.status, "completed");
  assert.equal(restored.entries.unknown, undefined);
  assert.equal(restored.schemaVersion, 2);
  assert.equal(restored.datasetId, dataset.dataset_id);
});

test("stored completion with an invalid timestamp is demoted before export", () => {
  const restored = core.normalizeState(
    {
      schemaVersion: 2,
      datasetId: dataset.dataset_id,
      sessionStartedAt: timestamp,
      savedAt: "not-a-date",
      activeItemId: "one",
      entries: {
        one: makeEntry({ completedAt: null, updatedAt: "not-a-date" }),
      },
    },
    dataset,
    timestamp,
  );

  assert.equal(restored.entries.one.status, "draft");
  assert.equal(restored.entries.one.completedAt, null);
  assert.equal(restored.entries.one.updatedAt, timestamp);
  assert.equal(restored.savedAt, null);
  const artifact = core.buildExport(dataset, restored, timestamp);
  assert.equal(artifact.annotations.length, 0);
  assert.equal(artifact.drafts[0].completed_at, null);
});

test("current v2 state discards entries whose immutable review basis changed", () => {
  const restored = core.normalizeState(
    {
      schemaVersion: 2,
      datasetId: dataset.dataset_id,
      sessionStartedAt: timestamp,
      savedAt: timestamp,
      activeItemId: "one",
      entries: {
        one: makeEntry({ reviewBasisSha256: "0".repeat(64) }),
        two: makeEntry(),
      },
    },
    dataset,
    timestamp,
  );

  assert.equal(restored.entries.one, undefined);
  assert.equal(restored.entries.two.reviewBasisSha256, basisSha256);
});

test("a later v2 dataset revision keeps only shared entries with the same review basis", () => {
  const restored = core.migrateState(
    {
      schemaVersion: 2,
      datasetId: "batch-1@previous-v2-revision",
      sessionStartedAt: timestamp,
      savedAt: timestamp,
      activeItemId: "two",
      entries: {
        one: makeEntry(),
        two: makeEntry({ reviewBasisSha256: "0".repeat(64) }),
        removed: makeEntry(),
      },
    },
    dataset,
    timestamp,
  );

  assert.equal(restored.datasetId, dataset.dataset_id);
  assert.equal(restored.activeItemId, "two");
  assert.equal(restored.entries.one.status, "completed");
  assert.equal(restored.entries.two, undefined);
  assert.equal(restored.entries.removed, undefined);
});

test("live cross-tab merge accepts only the exact same dataset revision", () => {
  const current = {
    schemaVersion: 2,
    datasetId: dataset.dataset_id,
    entries: {},
  };
  const previousRevision = {
    ...current,
    datasetId: "batch-1@previous-v2-revision",
  };

  assert.equal(core.isSameDatasetState(current, dataset), true);
  assert.equal(core.isSameDatasetState(previousRevision, dataset), false);
  assert.equal(core.isSameDatasetState(null, dataset), false);
});

test("legacy v1 state migrates only from an explicitly superseded dataset", () => {
  const legacyState = {
    schemaVersion: 1,
    datasetId: "batch-1@old-dataset",
    sessionStartedAt: "2026-07-23T09:00:00.000Z",
    savedAt: timestamp,
    activeItemId: "two",
    entries: {
      one: makeEntry({ feedback: "Сохранённая оценка", reviewBasisSha256: undefined }),
      unknown: makeEntry({ reviewBasisSha256: undefined }),
    },
  };

  const migrated = core.migrateState(legacyState, dataset, timestamp);
  assert.equal(migrated.schemaVersion, 2);
  assert.equal(migrated.datasetId, dataset.dataset_id);
  assert.equal(migrated.sessionStartedAt, legacyState.sessionStartedAt);
  assert.equal(migrated.activeItemId, "two");
  assert.equal(migrated.entries.one.feedback, "Сохранённая оценка");
  assert.equal(migrated.entries.one.reviewBasisSha256, basisSha256);
  assert.equal(migrated.entries.unknown, undefined);

  const rejected = core.migrateState(
    { ...legacyState, datasetId: "unrelated-dataset" },
    dataset,
    timestamp,
  );
  assert.equal(rejected.schemaVersion, 2);
  assert.equal(rejected.datasetId, dataset.dataset_id);
  assert.deepEqual(rejected.entries, {});
  assert.equal(rejected.sessionStartedAt, timestamp);
});

test("next incomplete item wraps and reports a finished dataset", () => {
  const entries = {
    one: makeEntry(),
    two: makeEntry({ status: "draft", completedAt: null }),
    three: makeEntry(),
  };
  assert.equal(core.nextIncompleteIndex(dataset.items, entries, 2), 1);
  entries.two = makeEntry();
  assert.equal(core.nextIncompleteIndex(dataset.items, entries, 2), -1);
});

test("cross-tab merge preserves independent edits and chooses the newer same-item edit", () => {
  const current = {
    schemaVersion: 2,
    datasetId: dataset.dataset_id,
    sessionStartedAt: timestamp,
    savedAt: "2026-07-23T10:00:02.000Z",
    activeItemId: "one",
    entries: {
      one: makeEntry({ feedback: "local", updatedAt: "2026-07-23T10:00:03.000Z" }),
    },
  };
  const incoming = {
    ...current,
    savedAt: "2026-07-23T10:00:04.000Z",
    activeItemId: "two",
    entries: {
      one: makeEntry({ feedback: "stale", updatedAt: "2026-07-23T10:00:01.000Z" }),
      two: makeEntry({ feedback: "remote", updatedAt: "2026-07-23T10:00:04.000Z" }),
    },
  };

  const merged = core.mergeStates(current, incoming);
  assert.equal(merged.state.activeItemId, "one");
  assert.equal(merged.state.entries.one.feedback, "local");
  assert.equal(merged.state.entries.two.feedback, "remote");
  assert.equal(merged.needsWrite, true);
  assert.equal(merged.hasIncomingChanges, true);

  const newerIncoming = core.mergeStates(merged.state, {
    ...incoming,
    entries: {
      ...incoming.entries,
      one: makeEntry({ feedback: "new remote", updatedAt: "2026-07-23T10:00:05.000Z" }),
    },
  });
  assert.equal(newerIncoming.state.entries.one.feedback, "new remote");
});

test("equal-timestamp conflicts converge deterministically", () => {
  const base = {
    schemaVersion: 2,
    datasetId: dataset.dataset_id,
    sessionStartedAt: timestamp,
    savedAt: timestamp,
    activeItemId: "one",
  };
  const left = { ...base, entries: { one: makeEntry({ feedback: "A" }) } };
  const right = { ...base, entries: { one: makeEntry({ feedback: "B" }) } };

  const leftResult = core.mergeStates(left, right).state.entries.one;
  const rightResult = core.mergeStates(right, left).state.entries.one;
  assert.deepEqual(leftResult, rightResult);
});

test("export separates valid completions from drafts and preserves exact snapshots", () => {
  const state = {
    sessionStartedAt: timestamp,
    entries: {
      one: makeEntry({ rating: 1, feedback: "Неверное движение" }),
      two: makeEntry({ rating: 3, status: "draft", completedAt: null }),
      three: makeEntry({ rating: 2, feedback: "", status: "completed" }),
    },
  };
  const artifact = core.buildExport(dataset, state, "2026-07-23T10:05:00.000Z");

  assert.deepEqual(artifact.summary, { total: 3, completed: 1, drafts: 2 });
  assert.equal(artifact.schema_version, 2);
  assert.equal(artifact.dataset.data_sha256, dataset.data_sha256);
  assert.deepEqual(artifact.dataset.sources, dataset.sources);
  assert.equal(artifact.annotations[0].item_id, "one");
  assert.equal(artifact.annotations[0].annotation_id, "PROMOPAGES-9897:one");
  assert.deepEqual(artifact.annotations[0].context_snapshot, dataset.items[0].context);
  assert.deepEqual(artifact.annotations[0].context_status, dataset.items[0].context_status);
  assert.deepEqual(artifact.annotations[0].prompt_snapshot, dataset.items[0].prompt);
  assert.deepEqual(artifact.annotations[0].prompt_author, dataset.items[0].prompt_author);
  assert.deepEqual(artifact.annotations[0].review_group, dataset.items[0].review_group);
  assert.deepEqual(artifact.annotations[0].approach, dataset.items[0].approach);
  assert.equal(artifact.annotations[0].review_basis_sha256, basisSha256);
  assert.deepEqual(
    new Set(artifact.drafts.map((entry) => entry.item_id)),
    new Set(["two", "three"]),
  );
  assert.equal(artifact.drafts.find((entry) => entry.item_id === "three").completed_at, null);
});

test("export keeps an absent historical context and legacy identifiers as explicit nulls", () => {
  const historical = {
    ...makeItem("historical"),
    context: null,
    context_status: {
      availability: "not_available_in_artifacts",
      reason: "Контекст не сохранён в историческом артефакте",
    },
    agent: {
      id: "clipmaker-classic",
      planning_run_id: null,
      batch_id: null,
      author_thread_id: null,
    },
    prompt_author: {
      id: "clipmaker-classic",
      label: "Clipmaker Classic",
      contract_version: null,
      attribution_basis: "project-generator-record",
      provenance_verified: false,
    },
    generation: { job_id: null, request_sha256: null },
  };
  const mixedDataset = { ...dataset, items: [historical] };
  const artifact = core.buildExport(
    mixedDataset,
    { sessionStartedAt: timestamp, entries: { historical: makeEntry() } },
    timestamp,
  );
  const record = artifact.annotations[0];

  assert.equal(record.context_snapshot, null);
  assert.equal(record.agent_id, "clipmaker-classic");
  assert.equal(record.run_id, null);
  assert.equal(record.batch_id, null);
  assert.equal(record.author_thread_id, null);
  assert.equal(record.generation_job_id, null);
  assert.equal(record.request_sha256, null);
});

test("checked-in JSON Schema requires non-whitespace feedback for completed rating 1/2", () => {
  const schemaPath = path.join(__dirname, "..", "PROMOPAGES-9897", "annotation-schema.json");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const completedRules = schema.$defs.completedAnnotation.allOf[1];
  assert.equal(schema.properties.schema_version.const, 2);
  assert.equal(schema.properties.dataset.required.includes("sources"), true);
  assert.equal(schema.properties.dataset.required.includes("data_sha256"), true);
  assert.deepEqual(schema.$defs.baseAnnotation.properties.context_snapshot.type, [
    "object",
    "null",
  ]);
  assert.deepEqual(schema.$defs.baseAnnotation.properties.request_sha256.type, [
    "string",
    "null",
  ]);
  assert.deepEqual(completedRules.if.properties.rating.enum, [1, 2]);
  assert.equal(completedRules.then.properties.feedback.pattern, "\\S");
});
