const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..");
require(path.join(ROOT, "tune", "app.js"));

const {
  actualVideoMethod,
  applyFilters,
  buildReviewExport,
  fallbackAudit,
  inferPromptEvaluated,
  modeLabel,
  normalizeManifest,
  normalizeProviderAttempt,
  normalizeReviewEntry,
  normalizeRatingState,
  normalizeTunedVideo,
  resolveMediaUrl,
  summarizeReviews,
  tunedVideoState,
} = globalThis.__tuneTestHooks;

const VIDEO_METHODS = Object.freeze({
  i2v: "eliza-i2v",
  compositor: "deterministic-compositor",
  fallback: "deterministic-compositor-fallback",
});

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
              video_url: "https://raw.githubusercontent.com/example/repo/abc123/tuned.mp4",
              status: "succeeded",
              media: { duration_seconds: 5, width: 1280, height: 720, bytes: 1024 },
              qa: { verified: true, status: "passed" },
            },
          },
        ],
      },
    ],
  };
}

function threeMethodFixture() {
  const providerAttempt = {
    status: "provider-failed",
    prompt_evaluated: false,
    run_path: "clipmaker-lite-test/tune-generation/veo/07-06/run.json",
    run_sha256: "b".repeat(64),
    provider_job_id: "veo-terminal-0706",
    error: "Provider filtered the request before generation.",
  };
  const video = (method, suffix, extra = {}) => ({
    status: "succeeded",
    method,
    delivery: "repository-raw",
    url: `https://raw.githubusercontent.com/example/repo/${"a".repeat(40)}/${suffix}.mp4`,
    repository_video_path: `clipmaker-lite-test/tune-videos/${suffix}.mp4`,
    sha256: "c".repeat(64),
    bytes: 4096,
    media: {
      duration_seconds: 4,
      width: 1280,
      height: 720,
      has_audio: false,
    },
    contract_check: { verified: true, status: "passed" },
    ...extra,
  });

  return {
    schema_version: 1,
    manifest_role: "clipmaker-lite-tune-review",
    ticket: "PROMOPAGES-10060",
    batch_id: "three-method-test",
    cases: [
      {
        case_id: "method#01",
        article_number: "method",
        title: "Actual renderer method",
        source: { image_id: "01", path: "source.png", width: 1280, height: 720 },
        planning: {
          structured_intent: { rendering_strategy: "i2v" },
          provenance: { verified: true },
        },
        targets: [
          {
            model_id: "alibaba/wan-2.2",
            rating_state: "blank",
            baseline: { video_url: "https://cdn.example/baseline-22.mp4" },
            tuned: {
              execution_mode: "i2v",
              positive_prompt: "Bounded motion.",
              video: video(VIDEO_METHODS.i2v, "eliza"),
            },
          },
          {
            model_id: "alibaba/wan-2.7",
            rating_state: "regenerate",
            baseline: { video_url: "https://cdn.example/baseline-27.mp4" },
            tuned: {
              execution_mode: "deterministic-compositor",
              positive_prompt: null,
              video: video(VIDEO_METHODS.compositor, "compositor", {
                prompt_evaluated: false,
              }),
            },
          },
          {
            model_id: "google/veo-3.1-lite",
            rating_state: "regenerate",
            baseline: { video_url: "https://cdn.example/baseline-veo.mp4" },
            tuned: {
              execution_mode: "i2v",
              positive_prompt: "Provider-bound prompt.",
              video: video(VIDEO_METHODS.fallback, "fallback", {
                prompt_evaluated: false,
                provider_attempt: providerAttempt,
              }),
            },
          },
        ],
      },
    ],
  };
}

function merged65Fixture() {
  const source = JSON.parse(
    fs.readFileSync(path.join(ROOT, "clipmaker-lite-test", "tune-manifest.json"), "utf8"),
  );
  const fallbackTargets = new Set([
    "07#06::google/veo-3.1-lite",
    "10#07::google/veo-3.1-lite",
  ]);

  for (const caseRecord of source.cases) {
    for (const target of caseRecord.targets || []) {
      const targetId = `${caseRecord.case_id}::${target.model_id}`;
      const plannedMode = target.tuned.execution_mode;
      const isFallback = fallbackTargets.has(targetId);
      const method = isFallback
        ? VIDEO_METHODS.fallback
        : plannedMode === "deterministic-compositor"
          ? VIDEO_METHODS.compositor
          : VIDEO_METHODS.i2v;
      const safeTargetId = targetId.replaceAll(/[^a-z0-9]+/gi, "-").toLowerCase();
      target.tuned.video = {
        status: "succeeded",
        method,
        delivery: "repository-raw",
        url: `https://raw.githubusercontent.com/example/repo/${"d".repeat(40)}/${safeTargetId}.mp4`,
        repository_video_path: `clipmaker-lite-test/tune-videos/${safeTargetId}.mp4`,
        sha256: "e".repeat(64),
        bytes: 8192,
        prompt_evaluated: method === VIDEO_METHODS.i2v,
        media: { duration_seconds: 4, width: 1280, height: 720, has_audio: false },
        contract_check: { verified: true, status: "passed" },
      };
      if (isFallback) {
        target.tuned.video.provider_attempt = {
          status: "provider-failed",
          prompt_evaluated: false,
          run_path: `clipmaker-lite-test/tune-generation/${safeTargetId}/run.json`,
          run_sha256: "f".repeat(64),
          provider_job_id: `terminal-${safeTargetId}`,
          error: "Provider filtered the request before generation.",
        };
      }
    }
  }
  return source;
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
  assert.equal(manifest.items[1].tuned.video.qaVerified, true);
  assert.equal(
    manifest.items[1].tuned.video.url,
    "https://raw.githubusercontent.com/example/repo/abc123/tuned.mp4",
  );
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

test("tuned video adapter accepts video, video_url and repository path forms", () => {
  const nested = normalizeTunedVideo({
    video: {
      method: VIDEO_METHODS.fallback,
      prompt_evaluated: false,
      provider_attempt: {
        status: "provider-failed",
        prompt_evaluated: false,
        provider_job_id: "provider-job",
        error: "filtered",
      },
      url: "https://raw.githubusercontent.com/example/repo/abc123/nested.mp4",
      status: "ready",
      delivery: "repository-raw",
      sha256: "a".repeat(64),
      bytes: 2048,
      media: { duration_seconds: 4 },
      contract_check: { conforms: false, warnings: ["duration"] },
    },
  });
  const direct = normalizeTunedVideo({
    video_url: "https://cdn.example/direct.mp4",
    repository_video_path: "tuned/direct.mp4",
    video_status: "succeeded",
    qa_status: "checked",
  });
  const stringVideo = normalizeTunedVideo({ video: "https://cdn.example/string.mp4" });

  assert.equal(nested.url, "https://raw.githubusercontent.com/example/repo/abc123/nested.mp4");
  assert.equal(nested.media.duration_seconds, 4);
  assert.equal(nested.delivery, "repository-raw");
  assert.equal(nested.sha256, "a".repeat(64));
  assert.equal(nested.bytes, 2048);
  assert.equal(nested.qaVerified, false);
  assert.equal(nested.method, VIDEO_METHODS.fallback);
  assert.equal(nested.promptEvaluated, false);
  assert.equal(nested.providerAttempt.providerJobId, "provider-job");
  assert.equal(direct.url, "https://cdn.example/direct.mp4");
  assert.equal(direct.repositoryPath, "tuned/direct.mp4");
  assert.equal(direct.qaStatus, "checked");
  assert.equal(stringVideo.url, "https://cdn.example/string.mp4");
});

test("actual video method wins over the planned strategy and labels all renderers", () => {
  assert.equal(actualVideoMethod({ method: VIDEO_METHODS.fallback }, "i2v"), VIDEO_METHODS.fallback);
  assert.equal(actualVideoMethod({ method: VIDEO_METHODS.compositor }, "i2v"), VIDEO_METHODS.compositor);
  assert.equal(actualVideoMethod({}, "i2v"), VIDEO_METHODS.i2v);
  assert.equal(modeLabel(VIDEO_METHODS.i2v), "Eliza I2V");
  assert.equal(modeLabel(VIDEO_METHODS.compositor), "Deterministic compositor");
  assert.equal(modeLabel(VIDEO_METHODS.fallback), "Deterministic fallback");
  assert.equal(inferPromptEvaluated(VIDEO_METHODS.i2v), true);
  assert.equal(inferPromptEvaluated(VIDEO_METHODS.fallback), false);
  assert.equal(
    normalizeProviderAttempt({ promptEvaluated: false }).promptEvaluated,
    false,
  );
});

test("fallback stays planned I2V and preserves terminal provider audit in export", () => {
  const manifest = normalizeManifest(threeMethodFixture());
  const methods = manifest.items.map((item) => item.tuned.video.method);
  assert.deepEqual(methods, [
    VIDEO_METHODS.i2v,
    VIDEO_METHODS.compositor,
    VIDEO_METHODS.fallback,
  ]);
  assert.ok(manifest.items.every((item) => tunedVideoState(item.tuned.video) === "available"));

  const fallback = manifest.items[2];
  assert.equal(fallback.tuned.executionMode, "i2v");
  assert.equal(fallback.tuned.video.method, VIDEO_METHODS.fallback);
  assert.equal(fallback.tuned.video.promptEvaluated, false);
  assert.deepEqual(fallbackAudit(fallback.tuned.video), {
    title: "Prompt не оценён: provider filtered",
    status: "provider-failed",
    providerJobId: "veo-terminal-0706",
    error: "Provider filtered the request before generation.",
  });

  const exported = buildReviewExport(
    manifest,
    {
      [fallback.id]: {
        outcome: "helped",
        note: "Fallback сохраняет исходник.",
        updated_at: "2026-08-11T17:00:00Z",
      },
    },
    "2026-08-11T18:00:00Z",
  );
  const evaluation = exported.evaluations[0];
  assert.equal(evaluation.planned_execution_mode, "i2v");
  assert.equal(evaluation.method, VIDEO_METHODS.fallback);
  assert.equal(evaluation.prompt_evaluated, false);
  assert.equal(evaluation.tuned_video.method, VIDEO_METHODS.fallback);
  assert.equal(evaluation.tuned_video.prompt_evaluated, false);
  assert.equal(evaluation.tuned_video.provider_attempt.status, "provider-failed");
  assert.equal(evaluation.tuned_video.provider_attempt.prompt_evaluated, false);
  assert.equal(evaluation.tuned_video.provider_attempt.provider_job_id, "veo-terminal-0706");
  assert.match(evaluation.tuned_video.provider_attempt.error, /filtered/);
});

test("merged fixture exposes 65 available tuned videos with 41/22/2 actual methods", () => {
  const manifest = normalizeManifest(merged65Fixture());
  const methodCounts = manifest.items.reduce((counts, item) => {
    counts[item.tuned.video.method] = (counts[item.tuned.video.method] || 0) + 1;
    return counts;
  }, {});
  const fallbacks = manifest.items.filter(
    (item) => item.tuned.video.method === VIDEO_METHODS.fallback,
  );

  assert.equal(manifest.targetCount, 65);
  assert.equal(
    manifest.items.filter(
      (item) => tunedVideoState(item.tuned.video, item.tuned.executionMode) === "available",
    ).length,
    65,
  );
  assert.deepEqual(methodCounts, {
    [VIDEO_METHODS.compositor]: 22,
    [VIDEO_METHODS.i2v]: 41,
    [VIDEO_METHODS.fallback]: 2,
  });
  assert.equal(fallbacks.length, 2);
  assert.ok(fallbacks.every((item) => item.tuned.executionMode === "i2v"));
  assert.ok(fallbacks.every((item) => item.tuned.video.promptEvaluated === false));
  assert.ok(fallbacks.every((item) => fallbackAudit(item.tuned.video).status === "provider-failed"));
});

test("tuned media state distinguishes available, pending, unavailable and compositor", () => {
  assert.equal(tunedVideoState({ url: "https://cdn.example/tuned.mp4" }, "i2v"), "available");
  assert.equal(tunedVideoState({ status: "generating" }, "i2v"), "pending");
  assert.equal(tunedVideoState({ status: "failed" }, "i2v"), "unavailable");
  assert.equal(tunedVideoState({}, "deterministic-compositor"), "pending");
  assert.equal(tunedVideoState({}, "i2v"), "pending");
});

test("review summary and export are stable per case and model", () => {
  const manifest = normalizeManifest(canonicalFixture());
  const reviews = {
    [manifest.items[0].id]: {
      outcome: "helped",
      note: "Текст больше не искажается.",
      updated_at: "2026-08-11T15:00:00Z",
    },
    [manifest.items[1].id]: {
      outcome: "same-or-unclear",
      note: "Нужно посмотреть полный ролик.",
      updated_at: "2026-08-11T15:05:00Z",
    },
  };
  const summary = summarizeReviews(manifest.items, reviews);
  const exported = buildReviewExport(manifest, reviews, "2026-08-11T16:00:00Z");

  assert.equal(summary.target_count, 2);
  assert.equal(summary.evaluated_count, 2);
  assert.equal(summary.helped_count, 1);
  assert.equal(summary.same_or_unclear_count, 1);
  assert.equal(summary.worse_count, 0);
  assert.equal(exported.export_role, "clipmaker-lite-tune-evaluation");
  assert.equal(exported.exported_at, "2026-08-11T16:00:00Z");
  assert.equal(exported.evaluations.length, 2);
  assert.equal(exported.evaluations[0].evaluation_id, "01#02::google/veo-3.1-lite");
  assert.equal(exported.evaluations[0].planned_execution_mode, "deterministic-compositor");
  assert.equal(exported.evaluations[0].method, VIDEO_METHODS.compositor);
  assert.equal(exported.evaluations[0].prompt_evaluated, false);
  assert.equal(exported.evaluations[0].tuned_video.state, "pending");
  assert.equal(exported.evaluations[1].method, VIDEO_METHODS.i2v);
  assert.equal(exported.evaluations[1].prompt_evaluated, true);
  assert.equal(exported.evaluations[1].tuned_video.state, "available");
  assert.equal(normalizeReviewEntry({ outcome: "worse" }).outcome, "worse");
  assert.equal(normalizeReviewEntry({ outcome: "invalid" }).outcome, "");
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
  assert.match(html, /id="exportReviews"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /\.loadState\[hidden\]\s*\{\s*display:\s*none;/);
  assert.match(script, /preload=\"metadata\"/);
  assert.doesNotMatch(script, /autoplay/);
  assert.match(script, /clipmaker-lite-test\/tune-manifest\.json/);
  assert.match(script, /localStorage/);
  assert.match(script, /same-or-unclear/);
  assert.match(script, /Tuned · MP4/);
  assert.match(script, /Eliza I2V/);
  assert.match(script, /Deterministic fallback/);
  assert.match(script, /Prompt не оценён: provider filtered/);
  assert.match(script, /const isCompositor = item\.tuned\.executionMode === "deterministic-compositor"/);
  assert.match(css, /\.methodBadge\[data-method="deterministic-compositor-fallback"\]/);
  assert.match(css, /\.fallbackNotice/);
  assert.match(script, /methodBadge/);
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
