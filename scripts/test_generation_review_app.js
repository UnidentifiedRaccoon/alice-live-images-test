"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


const ROOT = path.resolve(__dirname, "..");
const APP_PATH = path.join(ROOT, "generation-review", "app.js");
const HTML_PATH = path.join(ROOT, "generation-review", "index.html");
const BATCH_ID = "promopages-live-images-20260813-v1";
const MODELS = [
  "alibaba/wan-2.2",
  "alibaba/wan-2.7",
  "google/veo-3.1-lite",
];
const MODEL_FOLDERS = {
  "alibaba/wan-2.2": "wan_2_2",
  "alibaba/wan-2.7": "wan_2_7",
  "google/veo-3.1-lite": "veo_3_1",
};
const ARTICLE_FIXTURES = [
  {
    publication_id: "6a4f5fe924801975680d9be5",
    brand: "Банки.ру",
    title: "В каких банках можно выгодно купить доллар?",
    article_url:
      "https://banki.promo.page/save/v-kakih-bankah-mojno-vygodno-kupit-dollar-6a4f5fe924801975680d9be5_0_0",
    image_id: "01",
    media_id: "6a4f718952e3ce75a3110deb",
    width: 2000,
    height: 1125,
    source_url:
      "https://avatars.mds.yandex.net/get-promoarticles/5126709/pub_6a4f5fe924801975680d9be5_6a4f718952e3ce75a3110deb/orig",
    cabinet_path: "banki-ru__5b0fb7c448c85e2421e049ab",
    caption: "",
  },
  {
    publication_id: "6a048ddca495b52c9d873940",
    brand: "Level Group",
    title: "Брать ипотеку в II половине 2026 года? Отвечают эксперты",
    article_url:
      "https://level-group.promo.page/media/brat-ipoteku-v-ii-polovine-2026-goda-otvechaiut-eksperty-6a048ddca495b52c9d873940_0_0",
    image_id: "04",
    media_id: "6a049156a495b52c9d87cb75",
    width: 1920,
    height: 1023,
    source_url:
      "https://avatars.mds.yandex.net/get-promoarticles/6165752/pub_6a048ddca495b52c9d873940_6a049156a495b52c9d87cb75/orig",
    cabinet_path: "level-group__69ee06293ba10e0ae4b765d1",
    caption: "Покупатели выбирают квартиру в офисе продаж Level Group",
  },
];


const clone = (value) => JSON.parse(JSON.stringify(value));

const makeManifest = () => {
  let outputNumber = 0;
  const articles = ARTICLE_FIXTURES.map((fixture) => {
    const outputs = MODELS.map((modelId) => {
      outputNumber += 1;
      const sha256 = outputNumber.toString(16).repeat(64);
      const attemptId = `attempt-${outputNumber}`;
      const prompt = {
        positive: `Subtle editorial motion for ${fixture.media_id} with stable geometry.`,
        negative: "No morphing, no text changes, no camera shake.",
      };
      const videoUrl =
        "https://yastatic.net/s3/promopages-front-bundles/" +
        `front-images/exp_video/${fixture.cabinet_path}/` +
        `${fixture.publication_id}/${MODEL_FOLDERS[modelId]}/` +
        `image_${fixture.image_id}--sha256-${sha256.slice(0, 12)}.mp4`;
      return {
        model_id: modelId,
        status: "succeeded",
        selected_attempt_id: attemptId,
        selected_prompt: { ...prompt },
        attempt_count: 1,
        attempts: [
          {
            attempt_id: attemptId,
            status: "succeeded",
            prompt: { ...prompt },
            provider_run_id: `provider-${outputNumber}`,
            error: null,
          },
        ],
        video_url: videoUrl,
        media: {
          sha256,
          bytes: 1_000_000 + outputNumber,
          width: modelId === "alibaba/wan-2.2" ? 1280 : 1920,
          height: modelId === "alibaba/wan-2.2" ? 720 : 1080,
          duration_seconds: modelId === "google/veo-3.1-lite" ? 4 : 5,
        },
        contract_check: { conforms: true, warnings: [] },
        error: null,
      };
    });
    return {
      publication_id: fixture.publication_id,
      brand: fixture.brand,
      title: fixture.title,
      article_url: fixture.article_url,
      image: {
        image_id: fixture.image_id,
        media_id: fixture.media_id,
        width: fixture.width,
        height: fixture.height,
        caption: fixture.caption,
        source_url: fixture.source_url,
        provenance: {
          verified: true,
          agent_id: "clipmaker-lite",
          contract_version: "2.1.4",
          runner_version: 8,
        },
        outputs,
      },
    };
  });
  return {
    schema_version: 1,
    manifest_role: "clipmaker-lite-public-review",
    batch_id: BATCH_ID,
    producer: {
      agent_id: "clipmaker-lite",
      contract_version: "2.1.4",
      runner_version: 8,
    },
    models: MODELS,
    article_count: 2,
    image_count: 2,
    expected_outputs: 6,
    articles,
  };
};

const loadHooks = () => {
  const source = fs.readFileSync(APP_PATH, "utf8");
  const context = {
    console,
    URL,
    URLSearchParams,
    document: {
      readyState: "loading",
      addEventListener() {},
    },
  };
  vm.runInNewContext(source, context, { filename: APP_PATH });
  return context.__generationReviewTestHooks;
};


test("page is an isolated accessible review surface using shared styles", () => {
  const html = fs.readFileSync(HTML_PATH, "utf8");
  assert.match(html, /lang="ru"/);
  assert.match(html, /href="\.\.\/shared\.css\?v=12"/);
  assert.match(html, /href="\.\.\/clipmaker-lite\/styles\.css\?v=13"/);
  assert.match(html, /class="skipLink"/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /<label class="caseSelectLabel" for="caseSelect">/);
  assert.match(html, /id="caseViewport"[\s\S]*aria-busy="true"/);
  assert.doesNotMatch(html, /clipmaker-lite\/app\.js/);
  assert.doesNotMatch(html, /promopages-10060-manifest/);
});

test("validates the exact two-image, three-model public contract", () => {
  const hooks = loadHooks();
  const manifest = makeManifest();
  assert.equal(hooks.validateManifest(manifest), manifest);

  const unavailable = clone(manifest);
  const output = unavailable.articles[0].image.outputs[1];
  output.status = "unavailable";
  output.selected_attempt_id = null;
  output.selected_prompt = null;
  output.video_url = null;
  output.media = null;
  output.contract_check = null;
  output.error = "Provider returned no technically valid MP4 after the final attempt";
  output.attempts[0].status = "provider-failed";
  output.attempts[0].error = output.error;
  assert.equal(hooks.validateManifest(unavailable), unavailable);
});

test("rejects identity, source, provenance, model and S3 hash drift", () => {
  const hooks = loadHooks();
  const mutations = {
    batch(manifest) {
      manifest.batch_id = "another-batch";
    },
    source(manifest) {
      manifest.articles[0].image.source_url += "?changed=1";
    },
    provenance(manifest) {
      manifest.articles[1].image.provenance.verified = false;
    },
    modelOrder(manifest) {
      manifest.articles[0].image.outputs.reverse();
    },
    s3Route(manifest) {
      manifest.articles[0].image.outputs[0].video_url =
        manifest.articles[0].image.outputs[0].video_url.replace("wan_2_2", "wan_2_7");
    },
    mediaHash(manifest) {
      manifest.articles[1].image.outputs[2].media.sha256 = "f".repeat(64);
    },
    selectedPrompt(manifest) {
      manifest.articles[1].image.outputs[1].selected_prompt.positive = "Changed";
    },
  };

  for (const [name, mutate] of Object.entries(mutations)) {
    const manifest = makeManifest();
    mutate(manifest);
    assert.throws(
      () => hooks.validateManifest(manifest),
      undefined,
      `${name} mutation must fail closed`,
    );
  }
});

test("resolves direct links by batch, publication and exact image", () => {
  const hooks = loadHooks();
  const manifest = makeManifest();
  const levelQuery =
    `?batch=${BATCH_ID}` +
    "&case=6a048ddca495b52c9d873940&image=04";
  assert.equal(hooks.parseSelection(manifest, levelQuery), 1);
  assert.equal(hooks.parseSelection(manifest, ""), 0);
  assert.throws(
    () => hooks.parseSelection(manifest, `?batch=wrong&case=${manifest.articles[0].publication_id}`),
    /Неизвестный batch/,
  );
  assert.throws(
    () =>
      hooks.parseSelection(
        manifest,
        `?batch=${BATCH_ID}&case=${manifest.articles[0].publication_id}&image=04`,
      ),
    /Изображение 04 отсутствует/,
  );
});

test("escapes manifest text before rendering", () => {
  const hooks = loadHooks();
  assert.equal(
    hooks.escapeHtml('<img src=x onerror="alert(1)">'),
    "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;",
  );
});
