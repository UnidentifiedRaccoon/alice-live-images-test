const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..");
require(path.join(ROOT, "tune", "app.js"));

const {
  applyFilters,
  normalizeManifest,
  normalizeRatingState,
  resolveMediaUrl,
} = globalThis.__tuneTestHooks;

function canonicalFixture() {
  return {
    schema_version: 1,
    manifest_role: "clipmaker-lite-tune-review",
    ticket: "PROMOPAGES-10060",
    batch_id: "tune-test",
    agent_id: "clipmaker-lite",
    contract_version: "2.2.0",
    generated_at: "2026-08-11T12:00:00Z",
    scope: {
      case_count: 1,
      target_count: 2,
      new_video_generation: false,
      new_s3_upload: false,
    },
    summary: {
      rating: { regenerate_count: 1, blank_count: 1 },
      execution_mode_counts: { i2v: 1, "deterministic-compositor": 1 },
    },
    cases: [
      {
        case_id: "01#02",
        article_number: "01",
        article_slug: "01-level-ipoteka-2026",
        title: "Брать ипотеку в 2026 году?",
        content_class: "ui_chart",
        hypothesis: "frozen chart data/text",
        source: {
          image_id: "02",
          role: "article_image",
          caption: "Объём ипотечного кредитования",
          path: "PROMOPAGES-10060/articles/01/02.png",
          url: "https://avatars.mds.yandex.net/example/orig",
          width: 1280,
          height: 753,
        },
        planning: {
          run_id: "tune-test-01-02",
          provenance: { verified: true },
          structured_intent: {
            feasibility_assessment: "Exact chart state is semantic.",
            rendering_strategy: "deterministic-compositor",
          },
        },
        accepted_sibling_model_ids: ["alibaba/wan-2.7"],
        targets: [
          {
            sheet_row: 2,
            model_id: "google/veo-3.1-lite",
            rating_state: "regenerate",
            rating_raw: "Перегенерация (-)",
            comment: "Появляется случайный текст.",
            primary_failure_category: "source_identity_graphic_continuity",
            baseline: {
              positive_prompt: "Animate the chart.",
              video_url: "https://yastatic.net/example.mp4",
              media: { duration_seconds: 4, width: 1920, height: 1080 },
            },
            tuned: {
              execution_mode: "deterministic-compositor",
              scene_plan: "Use one bounded light sweep.",
              positive_prompt: null,
              negative_prompt: null,
              runtime: { duration_seconds: 4, resolution: "1080p" },
            },
          },
          {
            sheet_row: 3,
            model_id: "alibaba/wan-2.2",
            rating_state: "blank",
            rating_raw: "",
            comment: "Движение слишком слабое.",
            primary_failure_category: "insufficient_motion",
            baseline: {
              positive_prompt: "A slight camera move.",
              repository_video_path: "clipmaker-lite-test/videos/example.mp4",
            },
            tuned: {
              execution_mode: "i2v",
              scene_plan: "Use a bounded push-in.",
              positive_prompt: "A restrained push-in keeps the chart unchanged.",
              negative_prompt: null,
            },
          },
        ],
      },
    ],
  };
}

test("normalizeManifest flattens canonical cases into model-targets", () => {
  const manifest = normalizeManifest(canonicalFixture());
  assert.equal(manifest.caseCount, 1);
  assert.equal(manifest.targetCount, 2);
  assert.equal(manifest.items[0].id, "01#02::google/veo-3.1-lite");
  assert.equal(manifest.items[0].source.width, 1280);
  assert.equal(manifest.items[0].tuned.positivePrompt, null);
  assert.equal(manifest.items[0].planning.provenance.verified, true);
  assert.deepEqual(manifest.items[0].comments, ["Появляется случайный текст."]);
});

test("normalizeManifest accepts object-mapped targets and direct baseline/tuned records", () => {
  const manifest = normalizeManifest({
    cases: [
      {
        case_id: "02#01",
        title: "Object map",
        source: { image_id: "01", path: "source.png" },
        targets: {
          "alibaba/wan-2.7": {
            rating_state: "regenerate",
            baseline: { prompt: "Before" },
            tuned: { mode: "i2v", prompt: "After" },
          },
        },
      },
      {
        case_id: "03#04",
        title: "Direct",
        model_id: "alibaba/wan-2.2",
        source: { image_id: "04", path: "source-2.png" },
        baseline: { positive_prompt: "Before direct" },
        tuned: { execution_mode: "i2v", positive_prompt: "After direct" },
      },
    ],
  });
  assert.equal(manifest.items.length, 2);
  assert.equal(manifest.items[0].modelId, "alibaba/wan-2.7");
  assert.equal(manifest.items[1].tuned.positivePrompt, "After direct");
});

test("filters compose category, model, mode and rating", () => {
  const items = normalizeManifest(canonicalFixture()).items;
  assert.equal(applyFilters(items, { mode: "deterministic-compositor" }).length, 1);
  assert.equal(
    applyFilters(items, {
      category: "insufficient_motion",
      model: "alibaba/wan-2.2",
      mode: "i2v",
      rating: "blank",
    }).length,
    1,
  );
  assert.equal(applyFilters(items, { model: "google/veo-3.1-lite", rating: "blank" }).length, 0);
});

test("media paths stay relative locally and use raw GitHub on Pages", () => {
  const repositoryPath = "clipmaker-lite-test/videos/Проба 01.mp4";
  assert.equal(
    resolveMediaUrl(repositoryPath, { hostname: "localhost" }),
    "../clipmaker-lite-test/videos/%D0%9F%D1%80%D0%BE%D0%B1%D0%B0%2001.mp4",
  );
  assert.equal(
    resolveMediaUrl(repositoryPath, {
      hostname: "unidentifiedraccoon.github.io",
      rawBase: "https://raw.example/main/",
    }),
    "https://raw.example/main/clipmaker-lite-test/videos/%D0%9F%D1%80%D0%BE%D0%B1%D0%B0%2001.mp4",
  );
  assert.equal(
    resolveMediaUrl("https://yastatic.net/video.mp4", { hostname: "localhost" }),
    "https://yastatic.net/video.mp4",
  );
  assert.equal(resolveMediaUrl("javascript:alert(1)"), "");
});

test("rating normalization handles sheet values", () => {
  assert.equal(normalizeRatingState("regenerate", "Перегенерация (-)"), "regenerate");
  assert.equal(normalizeRatingState("", "Перегенерация (-)"), "regenerate");
  assert.equal(normalizeRatingState("blank", ""), "blank");
});

test("page shell contains the Step 8 contract and accessibility affordances", () => {
  const html = fs.readFileSync(path.join(ROOT, "tune", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(ROOT, "tune", "styles.css"), "utf8");
  const script = fs.readFileSync(path.join(ROOT, "tune", "app.js"), "utf8");

  assert.match(html, /aria-current="page"/);
  assert.match(html, /Step №8/);
  assert.match(html, /id="categoryFilter"/);
  assert.match(html, /id="modelFilter"/);
  assert.match(html, /id="modeFilter"/);
  assert.match(html, /id="ratingFilter"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /\.loadState\[hidden\]\s*\{\s*display:\s*none;/);
  assert.match(script, /preload=\"metadata\"/);
  assert.doesNotMatch(script, /autoplay/);
  assert.match(script, /clipmaker-lite-test\/tune-manifest\.json/);
});

const currentManifestPath = path.join(ROOT, "clipmaker-lite-test", "tune-manifest.json");
test(
  "current generated tune manifest satisfies the UI adapter",
  { skip: !fs.existsSync(currentManifestPath) },
  () => {
    const raw = JSON.parse(fs.readFileSync(currentManifestPath, "utf8"));
    const manifest = normalizeManifest(raw);
    assert.equal(manifest.caseCount, raw.scope.case_count);
    assert.equal(manifest.targetCount, raw.scope.target_count);
    assert.equal(manifest.issues.length, 0);
    assert.equal(
      manifest.items.filter((item) => item.tuned.executionMode === "deterministic-compositor").length,
      raw.summary.execution_mode_counts["deterministic-compositor"],
    );
    assert.ok(manifest.items.every((item) => item.source.url || item.source.path));
    assert.ok(manifest.items.every((item) => item.baseline.videoUrl || item.baseline.repositoryVideoPath));
  },
);
