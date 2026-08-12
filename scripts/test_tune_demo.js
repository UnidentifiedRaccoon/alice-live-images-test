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
  historicalMethodLabel,
  iterationLabel,
  normalizeManifest,
  normalizeIteration,
  normalizeReviewEntry,
  normalizeRatingState,
  normalizeTunedVideo,
  resolveMediaUrl,
  reviewScopeItems,
  summarizeReviews,
  tunedVideoState,
} = globalThis.__tuneTestHooks;

const ACTIVE_METHOD = "eliza-i2v";
const MODELS = [
  "google/veo-3.1-lite",
  "alibaba/wan-2.2",
  "alibaba/wan-2.7",
];

function videoReceipt(index, label = "active") {
  return {
    status: "succeeded",
    method: ACTIVE_METHOD,
    prompt_evaluated: true,
    delivery: "repository-raw",
    url: `https://raw.githubusercontent.com/example/repo/${"a".repeat(40)}/${label}-${index}.mp4`,
    repository_video_path: `clipmaker-lite-test/tune-videos/${label}-${index}.mp4`,
    sha256: String(index).padStart(64, "0").slice(-64),
    bytes: 4096 + index,
    media: {
      duration_seconds: index % 3 === 0 ? 4 : 5,
      width: 1280,
      height: 720,
      has_audio: false,
    },
    contract_check: { verified: true, status: "passed" },
  };
}

function previousTune(index) {
  const method = index < 22
    ? "deterministic-compositor"
    : index < 24
      ? "deterministic-compositor-fallback"
      : ACTIVE_METHOD;
  return {
    execution_mode: method === ACTIVE_METHOD ? "i2v" : "deterministic-compositor",
    scene_plan: `Previous v4 plan ${index}`,
    positive_prompt: method === ACTIVE_METHOD ? `Previous I2V prompt ${index}` : null,
    negative_prompt: null,
    video: {
      ...videoReceipt(index, "previous"),
      method,
      prompt_evaluated: method === ACTIVE_METHOD,
    },
  };
}

function sourceOutcome(index) {
  if (index < 19) return "";
  if (index < 23) return "same-or-unclear";
  if (index < 28) return "worse";
  return "helped";
}

function syntheticV5Fixture() {
  const cases = [];
  let targetIndex = 0;
  for (let caseIndex = 0; caseIndex < 36; caseIndex += 1) {
    const targetCount = caseIndex < 29 ? 2 : 1;
    const targets = [];
    for (let localIndex = 0; localIndex < targetCount; localIndex += 1) {
      const index = targetIndex;
      const regenerated = index < 28;
      const modelId = MODELS[(caseIndex + localIndex) % MODELS.length];
      const evaluationId = `${String(caseIndex + 1).padStart(2, "0")}#01::${modelId}`;
      const outcome = sourceOutcome(index);
      const target = {
        sheet_row: index + 2,
        model_id: modelId,
        model_label: modelId.split("/").at(-1),
        rating_state: regenerated ? "regenerate" : "blank",
        rating_raw: regenerated ? "Перегенерация (-)" : "",
        comment: regenerated ? `Исходная проблема ${index}` : null,
        primary_failure_category: index % 2
          ? "wrong_action_or_physics"
          : "source_identity_graphic_continuity",
        iteration: {
          action: regenerated ? "regenerated-v5" : "reused-helped",
          review_scope: regenerated,
          source_evaluation: {
            evaluation_id: evaluationId,
            outcome: outcome || null,
            note: outcome && outcome !== "helped" ? `Отзыв v4 ${index}` : null,
            updated_at: outcome ? "2026-08-11T16:00:00Z" : null,
          },
        },
        baseline: {
          scene_plan: `Original baseline plan ${index}`,
          positive_prompt: `Original baseline prompt ${index}`,
          video_url: `https://yastatic.net/baseline-${index}.mp4`,
          status: "succeeded",
          media: { duration_seconds: 4, width: 1920, height: 1080, bytes: 2048 },
        },
        tuned: {
          execution_mode: "i2v",
          scene_plan: regenerated ? `New v5 plan ${index}` : `Helped v4 plan ${index}`,
          positive_prompt: regenerated ? `New I2V prompt ${index}` : `Helped I2V prompt ${index}`,
          negative_prompt: null,
          runtime: { duration_seconds: 4, resolution: "1080p", generate_audio: false },
          video: videoReceipt(index),
        },
      };
      if (regenerated) target.previous_tuned = previousTune(index);
      targets.push(target);
      targetIndex += 1;
    }
    cases.push({
      case_id: `${String(caseIndex + 1).padStart(2, "0")}#01`,
      article_number: String(caseIndex + 1).padStart(2, "0"),
      article_slug: `article-${caseIndex + 1}`,
      title: `Synthetic case ${caseIndex + 1}`,
      content_class: "people",
      hypothesis: "Provider-bound I2V only",
      source: {
        image_id: "01",
        role: "article_image",
        caption: `Source ${caseIndex + 1}`,
        path: `PROMOPAGES-10060/articles/${caseIndex + 1}/01.png`,
        width: 1280,
        height: 720,
      },
      planning: {
        run_id: `v5-case-${caseIndex + 1}`,
        provenance: { verified: true },
        structured_intent: {
          feasibility_assessment: "A provider-bound I2V plan is available.",
          rendering_strategy: caseIndex % 2 ? "camera-only" : "image-to-video",
        },
      },
      targets,
    });
  }

  assert.equal(targetIndex, 65);
  return {
    schema_version: 2,
    manifest_role: "clipmaker-lite-tune-review",
    ticket: "PROMOPAGES-10060",
    batch_id: "promopages-10060-tune-review-20260811-v5-r4",
    agent_id: "clipmaker-lite",
    contract_version: "2.3.0",
    generated_at: "2026-08-11T18:00:00Z",
    scope: {
      case_count: 36,
      target_count: 65,
      review_target_count: 28,
      regenerated_target_count: 28,
      reused_helped_target_count: 37,
      new_s3_upload: false,
    },
    cases,
  };
}

test("v5 manifest exposes 65 targets with a 28/37 iteration split", () => {
  const manifest = normalizeManifest(syntheticV5Fixture());
  assert.equal(manifest.caseCount, 36);
  assert.equal(manifest.targetCount, 65);
  assert.equal(manifest.reviewTargetCount, 28);
  assert.equal(manifest.regeneratedTargetCount, 28);
  assert.equal(manifest.reusedHelpedTargetCount, 37);
  assert.equal(reviewScopeItems(manifest.items).length, 28);
  assert.equal(manifest.items.filter((item) => item.previousTuned).length, 28);
  assert.equal(manifest.issues.length, 0);
});

test("all active videos are receipt-backed Eliza I2V with no active fallback", () => {
  const manifest = normalizeManifest(syntheticV5Fixture());
  assert.ok(manifest.items.every((item) => item.tuned.executionMode === "i2v"));
  assert.ok(manifest.items.every((item) => item.tuned.video.method === ACTIVE_METHOD));
  assert.ok(manifest.items.every((item) => actualVideoMethod(item.tuned.video) === ACTIVE_METHOD));
  assert.equal(manifest.items.filter((item) => item.tuned.video.method.includes("fallback")).length, 0);
});

test("active method is read only from the provider video receipt", () => {
  assert.equal(actualVideoMethod({ method: ACTIVE_METHOD }), ACTIVE_METHOD);
  assert.equal(actualVideoMethod({}), "");
  assert.equal(actualVideoMethod({ method: "deterministic-compositor" }), "");
  assert.equal(actualVideoMethod({ method: "deterministic-compositor-fallback" }), "");
  assert.equal(
    normalizeTunedVideo({ execution_mode: "i2v", video_url: "https://cdn.example/no-receipt.mp4" }).method,
    "",
  );
});

test("iteration and historical labels separate active v5 from rejected v4", () => {
  assert.equal(iterationLabel("regenerated-v5"), "Новый I2V · v5");
  assert.equal(iterationLabel("reused-helped"), "Сохранено: помогло");
  assert.equal(historicalMethodLabel(ACTIVE_METHOD), "v4 · предыдущий I2V");
  assert.equal(
    historicalMethodLabel("deterministic-compositor-fallback"),
    "v4 · deterministic отклонён",
  );
  assert.deepEqual(normalizeIteration({ action: "reused-helped", review_scope: false }), {
    action: "reused-helped",
    reviewScope: false,
    sourceEvaluation: { evaluationId: "", outcome: "", note: "", updatedAt: "" },
  });
});

test("iteration filter defaults can isolate 28 regenerated or 37 reused targets", () => {
  const items = normalizeManifest(syntheticV5Fixture()).items;
  assert.equal(applyFilters(items, { iteration: "regenerated-v5" }).length, 28);
  assert.equal(applyFilters(items, { iteration: "reused-helped" }).length, 37);
  assert.equal(applyFilters(items, { iteration: "all" }).length, 65);
  assert.ok(
    applyFilters(items, { iteration: "regenerated-v5", model: "google/veo-3.1-lite" })
      .every((item) => item.modelId === "google/veo-3.1-lite"),
  );
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
  assert.equal(resolveMediaUrl("javascript:alert(1)"), "");
});

test("active video adapter keeps receipt metadata and QA", () => {
  const video = normalizeTunedVideo({ video: videoReceipt(7) });
  assert.equal(video.method, ACTIVE_METHOD);
  assert.equal(video.promptEvaluated, true);
  assert.equal(video.delivery, "repository-raw");
  assert.equal(video.media.duration_seconds, 5);
  assert.equal(video.qaVerified, true);
  assert.match(video.url, /raw\.githubusercontent\.com/);
});

test("review summary ignores all 37 reused-helped targets", () => {
  const manifest = normalizeManifest(syntheticV5Fixture());
  const regenerated = manifest.items.find((item) => item.iteration.reviewScope);
  const reused = manifest.items.find((item) => !item.iteration.reviewScope);
  const reviews = {
    [regenerated.id]: { outcome: "helped", note: "v5 лучше" },
    [reused.id]: { outcome: "worse", note: "не должен попасть в scope" },
  };
  const summary = summarizeReviews(manifest.items, reviews);
  assert.equal(summary.target_count, 28);
  assert.equal(summary.saved_entry_count, 1);
  assert.equal(summary.evaluated_count, 1);
  assert.equal(summary.helped_count, 1);
  assert.equal(summary.worse_count, 0);
  assert.equal(summary.unrated_count, 27);
});

test("review export schema v2 contains only regenerated-v5 evaluations", () => {
  const manifest = normalizeManifest(syntheticV5Fixture());
  const regenerated = manifest.items.find((item) => item.iteration.reviewScope);
  const reused = manifest.items.find((item) => !item.iteration.reviewScope);
  const exported = buildReviewExport(
    manifest,
    {
      [regenerated.id]: {
        outcome: "same-or-unclear",
        note: "Нужно пересмотреть",
        updated_at: "2026-08-11T19:00:00Z",
      },
      [reused.id]: { outcome: "worse", note: "Не экспортировать" },
    },
    "2026-08-11T20:00:00Z",
  );
  assert.equal(exported.schema_version, 2);
  assert.equal(exported.dataset.iteration_action, "regenerated-v5");
  assert.equal(exported.dataset.review_target_count, 28);
  assert.equal(exported.summary.target_count, 28);
  assert.equal(exported.evaluations.length, 1);
  assert.equal(exported.evaluations[0].iteration_action, "regenerated-v5");
  assert.equal(exported.evaluations[0].execution_mode, "i2v");
  assert.equal(exported.evaluations[0].method, ACTIVE_METHOD);
  assert.equal(
    exported.evaluations[0].source_evaluation.evaluation_id,
    regenerated.iteration.sourceEvaluation.evaluationId,
  );
});

test("tuned media state distinguishes available, pending and unavailable", () => {
  assert.equal(tunedVideoState({ url: "https://cdn.example/tuned.mp4" }), "available");
  assert.equal(tunedVideoState({ status: "generating" }), "pending");
  assert.equal(tunedVideoState({ status: "failed" }), "unavailable");
  assert.equal(tunedVideoState({}), "pending");
});

test("unavailable tuned media keeps the audited provider or safety reason", () => {
  const providerFailure = normalizeTunedVideo({
    video: {
      state: "unavailable",
      status: "provider-unavailable",
      provider_attempt: { error: "Provider completed with no output" },
    },
  });
  assert.equal(providerFailure.unavailableReason, "Provider completed with no output");

  const safetyBarrier = normalizeTunedVideo({
    video: {
      state: "unavailable",
      status: "provider-unavailable",
      safety_barrier: { reason: "Wan 2.2 route held by an ambiguous submit" },
    },
  });
  assert.equal(safetyBarrier.unavailableReason, "Wan 2.2 route held by an ambiguous submit");
});

test("review and rating normalization remain bounded", () => {
  assert.equal(normalizeReviewEntry({ outcome: "worse" }).outcome, "worse");
  assert.equal(normalizeReviewEntry({ outcome: "invalid" }).outcome, "");
  assert.equal(normalizeRatingState("regenerate", "Перегенерация (-)"), "regenerate");
  assert.equal(normalizeRatingState("blank", ""), "blank");
});

test("page shell exposes v5 iteration controls and no active fallback UI", () => {
  const html = fs.readFileSync(path.join(ROOT, "tune", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(ROOT, "tune", "styles.css"), "utf8");
  const script = fs.readFileSync(path.join(ROOT, "tune", "app.js"), "utf8");

  assert.match(html, /aria-current="page"/);
  assert.match(html, /id="iterationFilter"/);
  assert.match(html, /Новый I2V · v5/);
  assert.match(html, /Сохранено: помогло/);
  assert.doesNotMatch(html, /id="modeFilter"|compositorCountSummary/);
  assert.match(script, /Предыдущий tune · v4/);
  assert.match(script, /Импорт из v4/);
  assert.match(script, /schema_version:\s*2/);
  assert.match(script, /ACTIVE_VIDEO_METHOD = "eliza-i2v"/);
  assert.doesNotMatch(script, /fallbackNotice|inferPromptEvaluated|normalizeProviderAttempt/);
  assert.doesNotMatch(css, /data-method="deterministic-compositor/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(script, /preload="metadata"/);
  assert.doesNotMatch(script, /autoplay/);
});

const currentManifestPath = path.join(ROOT, "clipmaker-lite-test", "tune-manifest.json");
let currentV5Manifest = null;
if (fs.existsSync(currentManifestPath)) {
  const candidate = JSON.parse(fs.readFileSync(currentManifestPath, "utf8"));
  if (candidate.scope?.review_target_count === 28) currentV5Manifest = candidate;
}

test(
  "current v5 manifest satisfies the 65/28/37 UI contract when available",
  { skip: !currentV5Manifest },
  () => {
    const manifest = normalizeManifest(currentV5Manifest);
    assert.equal(manifest.targetCount, 65);
    assert.equal(manifest.reviewTargetCount, 28);
    assert.equal(manifest.reusedHelpedTargetCount, 37);
    assert.equal(manifest.issues.length, 0);
    assert.ok(manifest.items.every((item) => item.tuned.video.method === ACTIVE_METHOD));
  },
);
