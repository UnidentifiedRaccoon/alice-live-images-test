"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


const ROOT = path.resolve(__dirname, "..");
const APP_PATH = path.join(ROOT, "clipmaker-lite", "app.js");
const CASE_21_MANIFEST_PATH = path.join(
  ROOT,
  "clipmaker-lite-test",
  "case-21-manifest.json",
);

const loadHooks = () => {
  const source = fs
    .readFileSync(APP_PATH, "utf8")
    .replace(
      "  const validateCase21Manifest",
      "  globalThis.__validateSmoothExperiment = validateSmoothExperiment;\n\n" +
        "  const validateCase21Manifest",
    )
    .replace(
      "  const renderLoopAttemptHistory",
      "  globalThis.__renderModel = renderModel;\n\n" +
        "  const renderLoopAttemptHistory",
    )
    .replace(
      "  const renderSmoothSection",
      "  globalThis.__renderSmoothFeaturedReview = renderSmoothFeaturedReview;\n\n" +
        "  const renderSmoothSection",
    );
  const inertElement = {
    addEventListener() {},
  };
  const context = {
    console,
    document: {
      querySelector() {
        return inertElement;
      },
    },
    fetch() {
      return new Promise(() => {});
    },
    window: {
      location: {
        hostname: "unidentifiedraccoon.github.io",
        href: "https://unidentifiedraccoon.github.io/alice-live-images-test/clipmaker-lite/",
      },
      history: { replaceState() {} },
      matchMedia() {
        return { matches: false };
      },
    },
  };
  vm.runInNewContext(source, context, { filename: APP_PATH });
  return context;
};

const actualSmoothExperiment = () => {
  const manifest = JSON.parse(fs.readFileSync(CASE_21_MANIFEST_PATH, "utf8"));
  assert.ok(manifest.smooth_experiment, "smooth_experiment must be published");
  return manifest.smooth_experiment;
};

const clone = (value) => JSON.parse(JSON.stringify(value));


test("actual five-attempt smooth retry schema validates and rank five is retained", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );

  assert.equal(normalized.outputs.length, 4);
  assert.equal(normalized.attempt_history.length, 5);
  assert.equal(
    normalized.attempt_history.filter(
      (attempt) => attempt.activity === "smooth-motion-explicit-retry",
    ).length,
    1,
  );
  assert.ok(normalized.outputs.some((output) => output.motionProxy.rank === 5));
  assert.ok(normalized.outputs.every((output) => output.motionProxy.rankScale === 5));
});

test("smooth retry identity and proxy rank fail closed", () => {
  const hooks = loadHooks();
  const wrongActivity = clone(actualSmoothExperiment());
  wrongActivity.attempt_history[4].activity = "smooth-motion-experiment";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongActivity, new Set()),
    /identity smooth-попытки 5/,
  );

  const wrongSeries = clone(actualSmoothExperiment());
  wrongSeries.attempt_history[4].series_experiment_id = "wrong-series";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongSeries, new Set()),
    /identity smooth-попытки 5/,
  );

  const wrongRank = clone(actualSmoothExperiment());
  wrongRank.outputs[0].smooth_motion.proxy_review.proxy_rank = 6;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongRank, new Set()),
    /motion proxy review/,
  );
});

test("smooth featured review binds fail closed to the selected retry", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  assert.equal(normalized.featuredReview.status, "visual-winner");
  assert.equal(normalized.featuredReview.variant_id, "staggered-ease-retry1");
  assert.equal(normalized.outputs.filter((output) => output.isFeaturedWinner).length, 1);

  const wrongRun = clone(actualSmoothExperiment());
  wrongRun.featured_review.provider_run_id = wrongRun.outputs[0].provider_run_id;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongRun, new Set()),
    /featured review/,
  );

  const wrongPractice = clone(actualSmoothExperiment());
  wrongPractice.featured_review.practices[0].id = "generic-smoothness";
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongPractice, new Set()),
    /featured review/,
  );

  const wrongEvidence = clone(actualSmoothExperiment());
  wrongEvidence.featured_review.evidence.motion_energy_spike_count = 1;
  assert.throws(
    () => hooks.__validateSmoothExperiment(wrongEvidence, new Set()),
    /featured review/,
  );
});

test("featured callout explains visual selection and prompt practices", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const markup = hooks.__renderSmoothFeaturedReview(normalized.featuredReview);

  assert.match(markup, /Визуальный победитель · Staggered retry/);
  assert.match(markup, /Motion coverage[\s\S]*7\/7/);
  assert.match(markup, /Abrupt transitions[\s\S]*0/);
  assert.match(markup, /Motion spikes[\s\S]*0/);
  assert.match(markup, /Proxy rank[\s\S]*2\/5/);
  assert.match(markup, /Победитель выбран визуально/);
  assert.match(markup, /Part-level invariants/);
  assert.match(markup, /Ключевое отличие prompt/);
  assert.match(markup, /clock\/dial substitution/);
});

test("rendered smooth video is muted but has no loop semantics", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const markup = hooks.__renderModel(
    { article_number: "21", title: "Case 21" },
    { image: { image_id: "04" } },
    normalized.outputs[0],
    0,
    {
      idPrefix: "smoothModel",
      loopPlayback: false,
      smoothExperiment: true,
      headingLevel: 4,
    },
  );
  const videoTag = markup.match(/<video[\s\S]*?>/)[0];
  assert.match(videoTag, /\smuted(?:\s|>)/);
  assert.doesNotMatch(videoTag, /\sloop(?:\s|>)/);
  assert.doesNotMatch(videoTag, /data-loop-output/);
});

test("featured retry card has a winner badge and its exact negative prompt", () => {
  const hooks = loadHooks();
  const normalized = hooks.__validateSmoothExperiment(
    actualSmoothExperiment(),
    new Set(),
  );
  const winner = normalized.outputs.find((output) => output.isFeaturedWinner);
  const markup = hooks.__renderModel(
    { article_number: "21", title: "Case 21" },
    { image: { image_id: "04" } },
    winner,
    3,
    {
      idPrefix: "smoothModel",
      loopPlayback: false,
      smoothExperiment: true,
      headingLevel: 4,
    },
  );

  assert.match(markup, /data-featured-winner="true"/);
  assert.match(markup, /class="winnerBadge">Визуальный победитель/);
  assert.match(markup, /Дословный negative prompt/);
  assert.match(markup, /No clock or dial substitution/);
});
