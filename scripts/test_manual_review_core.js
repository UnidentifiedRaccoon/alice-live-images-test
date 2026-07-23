"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const core = require("../manual-review/review-core.js");

const timestamp = "2026-07-23T10:00:00.000Z";
const makeEntry = (overrides = {}) => ({
  rating: 3,
  feedback: "",
  status: "completed",
  completedAt: timestamp,
  updatedAt: timestamp,
  ...overrides,
});

const makeItem = (id) => ({
  id,
  video: { id, path: `video/${id}.mp4`, sha256: "a".repeat(64) },
  context: { title: `Context ${id}`, fragments: [{ relation: "before", text: "Text" }] },
  prompt: { positive: `Prompt ${id}`, negative: null },
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
  dataset_id: "batch-1@dataset",
  review_ticket: "PROMOPAGES-9897",
  source: {
    ticket: "PROMOPAGES-9891",
    batch_id: "batch-1",
    manifest_path: "manifest.json",
    manifest_sha256: "c".repeat(64),
    data_sha256: "d".repeat(64),
  },
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
      schemaVersion: 1,
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
    schemaVersion: 1,
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
    schemaVersion: 1,
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
  assert.equal(artifact.annotations[0].item_id, "one");
  assert.deepEqual(artifact.annotations[0].context_snapshot, dataset.items[0].context);
  assert.deepEqual(artifact.annotations[0].prompt_snapshot, dataset.items[0].prompt);
  assert.deepEqual(
    new Set(artifact.drafts.map((entry) => entry.item_id)),
    new Set(["two", "three"]),
  );
  assert.equal(artifact.drafts.find((entry) => entry.item_id === "three").completed_at, null);
});

test("checked-in JSON Schema requires non-whitespace feedback for completed rating 1/2", () => {
  const schemaPath = path.join(__dirname, "..", "PROMOPAGES-9897", "annotation-schema.json");
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
  const completedRules = schema.$defs.completedAnnotation.allOf[1];
  assert.deepEqual(completedRules.if.properties.rating.enum, [1, 2]);
  assert.equal(completedRules.then.properties.feedback.pattern, "\\S");
});
