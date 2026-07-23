window.qualityReviewDataset = {
  "schema_version": 2,
  "dataset_id": "promopages-9897-mixed@8df673dac745",
  "supersedes_dataset_ids": [
    "promopages-9891-lite3-20260723@f6fdff5dba9a"
  ],
  "review_ticket": "PROMOPAGES-9897",
  "data_sha256": "8df673dac7455969e5d431f87e02c8821c7ba6da8ccfc3d166fc05bba0cec413",
  "sources": [
    {
      "id": "clipmaker-lite-current",
      "review_group_id": "clipmaker-lite-current",
      "kind": "batch_manifest",
      "ticket": "PROMOPAGES-9891",
      "batch_id": "promopages-9891-lite3-20260723",
      "manifest_path": "PROMOPAGES-9857/clipmaker-lite-runs/promopages-9891-lite3-20260723/manifest.json",
      "manifest_sha256": "0cfc4a045882e3ef6a54e29c85e869f6b56f4389fa3ce10ff379776d001d0e19",
      "manifest_updated_at": "2026-07-23T08:11:12Z",
      "item_count": 15
    },
    {
      "id": "clipmaker-lite-previous",
      "review_group_id": "clipmaker-lite-previous",
      "kind": "generation_manifest",
      "ticket": "PROMOPAGES-9891",
      "batch_id": null,
      "manifest_path": "PROMOPAGES-9857/clipmaker-lite-generation-manifest.json",
      "manifest_sha256": "3789b77b182903dae68f96b9297ec97fd0578eacb562f1cdf0d22fa76b01a2c3",
      "manifest_updated_at": "2026-07-22T17:21:50Z",
      "item_count": 15,
      "native_item_count": 10,
      "cross_model_control_item_count": 5
    },
    {
      "id": "clipmaker-classic-main",
      "review_group_id": "clipmaker-classic-main",
      "kind": "generation_manifest",
      "ticket": "PROMOPAGES-9856",
      "batch_id": null,
      "manifest_path": "PROMOPAGES-9857/video-generation-manifest.json",
      "manifest_sha256": "7903d799dee751a938feea7422a595ea06d8530f330ff20f25a08fba3f6aba65",
      "manifest_updated_at": "2026-07-21T15:17:59Z",
      "item_count": 15,
      "cross_model_transfer_item_count": 2
    },
    {
      "id": "clipmaker-classic-experiments",
      "review_group_id": "clipmaker-classic-experiments",
      "kind": "explicit_artifact_allowlist",
      "ticket": "PROMOPAGES-9856",
      "batch_id": null,
      "artifact_root": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments",
      "artifact_index_sha256": "b6cabaa56847edab2581506cf60fc74782acd6e54e60a034a58736afe4cb860c",
      "experiment_ids": [
        "portrait-angry-outburst-v1",
        "portrait-angry-outburst-wan27-v2",
        "portrait-angry-outburst-wan27-extend-v3",
        "portrait-permissive-v1",
        "portrait-permissive-v2",
        "portrait-permissive-veo-safe-v1"
      ],
      "item_count": 12,
      "excluded_failed_item_count": 2
    },
    {
      "id": "sample-catalog",
      "review_group_id": null,
      "kind": "sample_manifest",
      "ticket": null,
      "batch_id": null,
      "manifest_path": "PROMOPAGES-9857/video-samples.json",
      "manifest_sha256": "a0c620d8c6d6f97489a324eb0201c9235e5b80e0dd4fc026eb9945abe4573822",
      "manifest_updated_at": null,
      "item_count": 5
    }
  ],
  "items": [
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2",
        "author_thread_id": "019f8bda-76b8-7e83-ab3b-072635bbb2d2",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "a29d4e4c4a5447779cd9d9042eedf337",
        "request_sha256": "ce0569cfef291f1b83bb84964efe17b66ed0f906f0500a3c12156fe65602b322",
        "submitted_at": "2026-07-22T22:09:46Z",
        "completed_at": "2026-07-22T22:10:46Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/02.mp4",
        "sha256": "8a3cfee8f5e4aba8fe7e3b42cb2ce1492d49120d5a9eaab14ac460862ff9b0fc",
        "bytes": 313961,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/01-pharmocean-magiia-magniia/content.json",
        "source_sha256": "859cd295cb7d6fde59765681c3862ef29f09ba6a70c7931dbe4cda66ef46c19a",
        "article_id": "01-pharmocean-magiia-magniia",
        "title": "Магия Магния",
        "lead": "Зачем нужен магний, каким бывает и какой магний лучше",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 3,
          "role": "article_image",
          "file": "02.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 2,
            "type": "paragraph",
            "text": "Магний традиционно считается «витамином от стресса», однако помимо успокаивающего и расслабляющего эффекта этот незаменимый макроэлемент взвалил на себя тысячу обязанностей: он участвует в создании ДНК, производстве белка, превращении еды в энергию, регуляции количества сахара в крови, контроле артериального давления, сокращении мышц, в том числе сердечных и выработке гормонов."
          },
          {
            "relation": "after",
            "block_index": 4,
            "type": "paragraph",
            "text": "И это далеко не полный перечень его многочисленных функций!"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Fixed close-up. The woman’s raised fingers slowly curl tighter as her jaw clenches and her eyebrows lift with mounting tension; a brief natural blink follows, then her hands and jaw loosen slightly while she keeps looking straight ahead.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "aspect_ratio": "source",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/02.prompt.json",
        "prompt_sha256": "975e3bdaee43713b3feff4f08fe2f093f01f085acecf07bff691ed26786c6abe",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/02.run.json",
        "run_sha256": "cddb894c58b9590fbb55904837600e5ada0bcdfd6b66e8b77c3d26347904c401",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2/result.json",
        "lite_result_sha256": "33b85dcaa5d1868b06184d5967eda77dd469089570f245acdd59d2662aaaf530"
      },
      "review_basis_sha256": "fb77100a2e29e19e3fab423e6a7ab126efcfa6aaa6c154dc64976e0a50cf3ba5"
    },
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7",
        "author_thread_id": "019f8bda-e68e-73d3-9439-46b3aebfa20a",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "mcgKqSaukfCnAolpRUus",
        "request_sha256": "b3d236778fb30d70f6ca07c90546b800ba714de0079fe95850fa5f4b60cefa1f",
        "submitted_at": "2026-07-22T22:15:07Z",
        "completed_at": "2026-07-22T22:17:14Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/02.mp4",
        "sha256": "2c8f6ee381a8f2d6b364e0c41cf53e197227d433a839ac6fcffb2507f7e80fb5",
        "bytes": 4309139,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/01-pharmocean-magiia-magniia/content.json",
        "source_sha256": "859cd295cb7d6fde59765681c3862ef29f09ba6a70c7931dbe4cda66ef46c19a",
        "article_id": "01-pharmocean-magiia-magniia",
        "title": "Магия Магния",
        "lead": "Зачем нужен магний, каким бывает и какой магний лучше",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 3,
          "role": "article_image",
          "file": "02.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 2,
            "type": "paragraph",
            "text": "Магний традиционно считается «витамином от стресса», однако помимо успокаивающего и расслабляющего эффекта этот незаменимый макроэлемент взвалил на себя тысячу обязанностей: он участвует в создании ДНК, производстве белка, превращении еды в энергию, регуляции количества сахара в крови, контроле артериального давления, сокращении мышц, в том числе сердечных и выработке гормонов."
          },
          {
            "relation": "after",
            "block_index": 4,
            "type": "paragraph",
            "text": "И это далеко не полный перечень его многочисленных функций!"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Her anxious tension builds continuously: both hands tremble slightly near her cheeks as the curled fingers tighten inward, her brows lift and facial muscles tense, then one eyelid gives two brief involuntary twitches near the end. Keep the camera fixed in the close frontal framing, ending on her strained, alarmed expression.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "verification-failed",
        "conforms": false,
        "warnings": [
          "audio",
          "resolution",
          "aspect_ratio"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "aspect_ratio": "4:3",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/02.prompt.json",
        "prompt_sha256": "7a3ee5892f2da783f864e69530e6b93c9b9f6e50e58589a02fada346c917fd68",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/02.run.json",
        "run_sha256": "cbf54b8a9c87afece8e202c4b13585b0a78672694b302b1aff9d2e361890b5a6",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7/result.json",
        "lite_result_sha256": "1212bf063c9841c3256376d967e952c025c7637bc4a824ae11ebd9f36a341a15"
      },
      "review_basis_sha256": "b36879dff01ce4da5fbdf721afec085e60bfca90c4f67871932e73d7daacb817"
    },
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite",
        "author_thread_id": "019f8bda-f06b-7bf2-9832-f02afa2a220e",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "PepC15lhIREo7DNRao2V",
        "request_sha256": "ea1ee1a06a9bda65495c6e3d4551ca444f953abcae11fff0a8ede50f31671272",
        "submitted_at": "2026-07-22T22:24:31Z",
        "completed_at": "2026-07-22T22:26:19Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/02.mp4",
        "sha256": "eedd32586f3ed3e8f242e5b1f47f02a8cee880c0bf12122093a97c9ca1897ba1",
        "bytes": 3538862,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/01-pharmocean-magiia-magniia/content.json",
        "source_sha256": "859cd295cb7d6fde59765681c3862ef29f09ba6a70c7931dbe4cda66ef46c19a",
        "article_id": "01-pharmocean-magiia-magniia",
        "title": "Магия Магния",
        "lead": "Зачем нужен магний, каким бывает и какой магний лучше",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 3,
          "role": "article_image",
          "file": "02.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 2,
            "type": "paragraph",
            "text": "Магний традиционно считается «витамином от стресса», однако помимо успокаивающего и расслабляющего эффекта этот незаменимый макроэлемент взвалил на себя тысячу обязанностей: он участвует в создании ДНК, производстве белка, превращении еды в энергию, регуляции количества сахара в крови, контроле артериального давления, сокращении мышц, в том числе сердечных и выработке гормонов."
          },
          {
            "relation": "after",
            "block_index": 4,
            "type": "paragraph",
            "text": "И это далеко не полный перечень его многочисленных функций!"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Fixed camera, single continuous shot. The woman’s lower eyelid begins to twitch subtly as her eyes stay wide; tension builds through her clenched jaw, raised shoulders, and fingers curling tighter beside her face. She then releases a short controlled breath, her fingers loosen slightly and her shoulders drop a little, ending still visibly strained.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/02.prompt.json",
        "prompt_sha256": "650189a547a7e6b5fdfff51a6cdaa24673b6bd44f8cca26e910aa3d329729563",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/02.run.json",
        "run_sha256": "131f92dcdff116ef5319bce1869cc6655aec5294ad67222352c25a5cd32d2d4c",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite/result.json",
        "lite_result_sha256": "64c36abef90e3c5b00677b9e8ad883442ff726a7304599b29a8582b4858c449a"
      },
      "review_basis_sha256": "e03090a9709fd04191a311d707511addde9b46ec403bd8e6c95e4aaf39b154c4"
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-2",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-2",
        "author_thread_id": "019f8bda-f6e6-79c2-a4c2-abd847feea85",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "1eae66e7e6884baa97aec8924a77ef28",
        "request_sha256": "903be741c572a412e09d6f1b52369f7e6fd7ce5ce197b9b820060ae67354fb38",
        "submitted_at": "2026-07-22T22:10:46Z",
        "completed_at": "2026-07-22T22:11:46Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-2",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/05.mp4",
        "sha256": "4e4523ca1f6fed7b90acc32e260962d393e4840f6c4f819bf96675ccfae96312",
        "bytes": 148491,
        "duration_seconds": 3.233,
        "width": 1200,
        "height": 736,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/04-graceface-antivozrastnaia-syvorotka/content.json",
        "source_sha256": "12176f529a5ee48ed8064b0ee1b791ab5783c52cfbd8515a4d8b68e067e8c084",
        "article_id": "04-graceface-antivozrastnaia-syvorotka",
        "title": "Нашла лучшую антивозрастную сыворотку за смешные деньги",
        "lead": "Теперь точно куплю в подарок маме.\nКак это ни обидно, мы все стареем. С возрастом приходится усиленно бороться за свою красоту. Кто-то начинает раньше, кто-то позже.\nПримерно до 37-38 лет я даже не думала, что меня тоже коснётся проблема старения. Дело в том, что у женщин моей семьи – отличная генетика. Бабушка всегда выглядела гораздо моложе своих лет (и у неё даже в возрасте за 80 были",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 17,
          "role": "article_image",
          "file": "05.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 16,
            "type": "paragraph",
            "text": "И совершенно случайно, во время сёрфинга по маркептплейсам, наткнулась на трюфельную сыворотку другого производителя. Вот она."
          },
          {
            "relation": "after",
            "block_index": 18,
            "type": "paragraph",
            "text": "Омолаживающая сыворотка для лица с трюфелем от GRACEFACE привлекла внимание сразу по трём пунктам. Первый – разрекламированный трюфель в составе. Второй – красивый стеклянный флакон с пипеткой, выглядит дорого-богато. И третий – цена."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Fixed camera. The clear serum droplet at the pipette tip slowly elongates under gravity, narrows into a glossy thread, then detaches and falls straight down, leaving a tiny fresh bead forming at the tip by the end. The pipette and product arrangement stay still; subtle highlights glide through the viscous liquid.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "aspect_ratio": "source",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/05.prompt.json",
        "prompt_sha256": "5142bcf53a2adab758b1ecd21b06bdc7819435c4fa3d667ac88253cc6bbeeb53",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/05.run.json",
        "run_sha256": "30cc84ad642cb06c55d3d0f4200bd2aa83b00211753612245b52ac6e83c0ba86",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-wan-2-2/result.json",
        "lite_result_sha256": "ad291e9717a1e8b6d1a03c4df38155a96b2988ebc08a8e6d448578a812785f0e"
      },
      "review_basis_sha256": "53f079a5257716cd025af7bb211d6e9b01f1add4cef4c2b6efb02c8de35f5de6"
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-7",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-7",
        "author_thread_id": "019f8bda-ed7c-7581-9d12-09e208eeddfd",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "eJYvxGPwrBw5ZICVEMO7",
        "request_sha256": "4554a88324903aadc8194f200769133b1c8b81701f4b7410607a31fa53647fd2",
        "submitted_at": "2026-07-22T22:17:15Z",
        "completed_at": "2026-07-22T22:18:30Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-7",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/05.mp4",
        "sha256": "87dbe2e6ef620c8523bfceb105ed6ead9b75386cffbcfd8ae3c39e740aa05c71",
        "bytes": 1543704,
        "duration_seconds": 5.0,
        "width": 1820,
        "height": 1138,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/04-graceface-antivozrastnaia-syvorotka/content.json",
        "source_sha256": "12176f529a5ee48ed8064b0ee1b791ab5783c52cfbd8515a4d8b68e067e8c084",
        "article_id": "04-graceface-antivozrastnaia-syvorotka",
        "title": "Нашла лучшую антивозрастную сыворотку за смешные деньги",
        "lead": "Теперь точно куплю в подарок маме.\nКак это ни обидно, мы все стареем. С возрастом приходится усиленно бороться за свою красоту. Кто-то начинает раньше, кто-то позже.\nПримерно до 37-38 лет я даже не думала, что меня тоже коснётся проблема старения. Дело в том, что у женщин моей семьи – отличная генетика. Бабушка всегда выглядела гораздо моложе своих лет (и у неё даже в возрасте за 80 были",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 17,
          "role": "article_image",
          "file": "05.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 16,
            "type": "paragraph",
            "text": "И совершенно случайно, во время сёрфинга по маркептплейсам, наткнулась на трюфельную сыворотку другого производителя. Вот она."
          },
          {
            "relation": "after",
            "block_index": 18,
            "type": "paragraph",
            "text": "Омолаживающая сыворотка для лица с трюфелем от GRACEFACE привлекла внимание сразу по трём пунктам. Первый – разрекламированный трюфель в составе. Второй – красивый стеклянный флакон с пипеткой, выглядит дорого-богато. И третий – цена."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Keep the camera fixed. Clear serum slowly gathers at the pipette tip, elongates under gravity, then detaches and falls toward the truffles near the end; a new tiny bead begins forming on the tip. Preserve the calm product-display composition.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "verification-failed",
        "conforms": false,
        "warnings": [
          "audio",
          "resolution",
          "aspect_ratio"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/05.prompt.json",
        "prompt_sha256": "8ea75b541536410a65a8e623927ef0525d4db42b6d41a73913aaaf95c4dd3d51",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/05.run.json",
        "run_sha256": "f1618de2303de6565424438fb1eee0b8f89687b3e8215c88838e1dd1d362cb5a",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-wan-2-7/result.json",
        "lite_result_sha256": "91ab21853c08d7c45019147d3366b45a847aea9bf81cb8d36d1c87002aa110d0"
      },
      "review_basis_sha256": "705154c76559827402b6c6b60acd5b00ee21d770ac8ab903bbd73c88034d22e3"
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite",
        "author_thread_id": "019f8bda-f0e3-7783-bb7b-e2c923b8ce01",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "BMGeOzWysGhf6Va4VOnJ",
        "request_sha256": "b49527b7b98f8e4267dccecba82ad484ea6e3029b54af7a71537436c8bc37597",
        "submitted_at": "2026-07-22T22:26:21Z",
        "completed_at": "2026-07-22T22:28:07Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/05.mp4",
        "sha256": "42a7947804419ffb88dc2bf0c75716b1755f7adb03c8b20bb31d2de8303bc9ad",
        "bytes": 1221012,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/04-graceface-antivozrastnaia-syvorotka/content.json",
        "source_sha256": "12176f529a5ee48ed8064b0ee1b791ab5783c52cfbd8515a4d8b68e067e8c084",
        "article_id": "04-graceface-antivozrastnaia-syvorotka",
        "title": "Нашла лучшую антивозрастную сыворотку за смешные деньги",
        "lead": "Теперь точно куплю в подарок маме.\nКак это ни обидно, мы все стареем. С возрастом приходится усиленно бороться за свою красоту. Кто-то начинает раньше, кто-то позже.\nПримерно до 37-38 лет я даже не думала, что меня тоже коснётся проблема старения. Дело в том, что у женщин моей семьи – отличная генетика. Бабушка всегда выглядела гораздо моложе своих лет (и у неё даже в возрасте за 80 были",
        "current_heading": null,
        "caption": "",
        "image_position": {
          "block_index": 17,
          "role": "article_image",
          "file": "05.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 16,
            "type": "paragraph",
            "text": "И совершенно случайно, во время сёрфинга по маркептплейсам, наткнулась на трюфельную сыворотку другого производителя. Вот она."
          },
          {
            "relation": "after",
            "block_index": 18,
            "type": "paragraph",
            "text": "Омолаживающая сыворотка для лица с трюфелем от GRACEFACE привлекла внимание сразу по трём пунктам. Первый – разрекламированный трюфель в составе. Второй – красивый стеклянный флакон с пипеткой, выглядит дорого-богато. И третий – цена."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Slow, subtle camera push-in. The clear serum at the pipette tip gradually swells and stretches, then detaches near the end and falls onto the white surface, settling into a small glossy bead. Keep the bottle, dropper, and truffles otherwise still in one continuous product shot.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/05.prompt.json",
        "prompt_sha256": "51e9486c343f50bddda379404205aeb5db1795b846a3b6b2234b85442a6b1e86",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/05.run.json",
        "run_sha256": "47bec8a057d2866b2aeac05e203603fab91efdbe559695f43876b19727dfc1a0",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite/result.json",
        "lite_result_sha256": "7e01189ab684d7cc71dc4f0400fdedd56fc1f71a87804fa42579db748f727dba"
      },
      "review_basis_sha256": "53e8dd19a99f13d6087ea3cb2d8424ecc63af333e4f81ee705abe51b4db65ab0"
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-2",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-2",
        "author_thread_id": "019f8bdb-6547-77b1-b452-75a04318c9d1",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "788832f31a2541aeae392e15002f63e6",
        "request_sha256": "a25b6a55ca5b7f995c0a48272a6cd485f1634d56f1ff899c111a77f1aab5aab4",
        "submitted_at": "2026-07-22T22:11:46Z",
        "completed_at": "2026-07-22T22:12:46Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-2",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/03.mp4",
        "sha256": "a4431ec49f62b42eecb938994f3ba9475d86e5e473ff039a3eb7d9df525fed84",
        "bytes": 393297,
        "duration_seconds": 3.233,
        "width": 1408,
        "height": 624,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/06-4lapy-koshachii-napolnitel/content.json",
        "source_sha256": "4360ca3f4c5eee1a46b4adaafddedb7a93a95ea51f1257a98c56974969d7c72a",
        "article_id": "06-4lapy-koshachii-napolnitel",
        "title": "Как убрать запах кошачьего туалета? Выбираем наполнитель",
        "lead": "Подобрали варианты эффективных и комфортных для кошки наполнителей",
        "current_heading": {
          "block_index": 11,
          "level": 3,
          "text": "Совет №3. Регулярно меняйте наполнитель в лотке"
        },
        "caption": "Если у вас дома живёт несколько кошек, выбирайте впитывающий наполнитель. Главное, помните, что лоток нужно регулярно чистить. Это не даст размножаться вредным бактериям",
        "image_position": {
          "block_index": 22,
          "role": "article_image",
          "file": "03.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 21,
            "type": "paragraph",
            "text": "Независимо от типа наполнителя, раз в месяц обязательно проводите полную уборку и дезинфекцию лотка. Помните, что кошки — чистюли, и грязный лоток может стать причиной отказа от него."
          },
          {
            "relation": "after",
            "block_index": 23,
            "type": "heading",
            "text": "Совет №4. Используйте силикагелевые наполнители"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "The cat calmly steps out of the litter box to the right, placing its lowered front paw on the floor and smoothly shifting its weight forward. Its other front paw follows over the rim as the head tracks the movement, ending balanced in a natural walking stance. Fixed camera.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "aspect_ratio": "source",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/03.prompt.json",
        "prompt_sha256": "f0e534b50498fb8278db739753a3464ca33bd2ceac4ef952372a99c623af65eb",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/03.run.json",
        "run_sha256": "1e9ce6659dc8f33b714a844ba4a57958901e4fb8cd6692257304ae263dddc587",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-wan-2-2/result.json",
        "lite_result_sha256": "97e93335576bf43616a8f790832d89fc139527d8d382da64c5cc1f7cd8e61fb0"
      },
      "review_basis_sha256": "8747c88699634ea8ad7bc99159cfd612fb265e8edd275a2df24861588925215d"
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-7",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-7",
        "author_thread_id": "019f8bdb-6cc3-7982-bec2-090c1b99d4eb",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "ppY8mJyRnnOkOEUOZJm4",
        "request_sha256": "f00ef10e5fc4cfd335528bc258e044c27944479d185d82e5cc513b550dce1a6a",
        "submitted_at": "2026-07-22T22:18:32Z",
        "completed_at": "2026-07-22T22:19:54Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-7",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/03.mp4",
        "sha256": "539f12a91fd0d59352200e49cfe381f9d5c9bdb3674ead9568a173212e5b19ca",
        "bytes": 5193228,
        "duration_seconds": 5.0,
        "width": 2146,
        "height": 966,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/06-4lapy-koshachii-napolnitel/content.json",
        "source_sha256": "4360ca3f4c5eee1a46b4adaafddedb7a93a95ea51f1257a98c56974969d7c72a",
        "article_id": "06-4lapy-koshachii-napolnitel",
        "title": "Как убрать запах кошачьего туалета? Выбираем наполнитель",
        "lead": "Подобрали варианты эффективных и комфортных для кошки наполнителей",
        "current_heading": {
          "block_index": 11,
          "level": 3,
          "text": "Совет №3. Регулярно меняйте наполнитель в лотке"
        },
        "caption": "Если у вас дома живёт несколько кошек, выбирайте впитывающий наполнитель. Главное, помните, что лоток нужно регулярно чистить. Это не даст размножаться вредным бактериям",
        "image_position": {
          "block_index": 22,
          "role": "article_image",
          "file": "03.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 21,
            "type": "paragraph",
            "text": "Независимо от типа наполнителя, раз в месяц обязательно проводите полную уборку и дезинфекцию лотка. Помните, что кошки — чистюли, и грязный лоток может стать причиной отказа от него."
          },
          {
            "relation": "after",
            "block_index": 23,
            "type": "heading",
            "text": "Совет №4. Используйте силикагелевые наполнители"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "The cat calmly steps down from the litter box, places the extended front paw on the floor, shifts its weight forward, then brings the other paws down and walks one measured step toward the right. Its head stays low and alert, with subtle ear, whisker, and tail movement. Fixed camera.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "verification-failed",
        "conforms": false,
        "warnings": [
          "audio",
          "resolution",
          "aspect_ratio"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/03.prompt.json",
        "prompt_sha256": "ebefd80f06e3368fca950f10fc2fcafd8c5815ff5ad5be8041b4f65e7064c4eb",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/03.run.json",
        "run_sha256": "bd4bbd6aa707639d7e3fc58a75da6915e5b06c409f22ee0f581315945adbd07c",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-wan-2-7/result.json",
        "lite_result_sha256": "b91b3286fb348b17ae46cd0df8399ff5501ff885c08601c4fcc4ac5d5fe13878"
      },
      "review_basis_sha256": "e9c472cfbbfccb4f71ddd9d86b398bd3c93d21b5173fef809091878976b89bcf"
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite",
        "author_thread_id": "019f8bdb-6aa0-7e42-85b0-48543353661f",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "oar7FT6G03EZZrYijnCi",
        "request_sha256": "2a3fc63157e3f03378cff3958f560c6da4e9f0df6f2333ba7c498fa6d7b7f009",
        "submitted_at": "2026-07-22T22:28:10Z",
        "completed_at": "2026-07-22T22:30:08Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/03.mp4",
        "sha256": "f8caa4e9f29dc24702f3728f2ee7b7b903977f316c91cf828fb1c5c0dfd41a49",
        "bytes": 7227535,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/06-4lapy-koshachii-napolnitel/content.json",
        "source_sha256": "4360ca3f4c5eee1a46b4adaafddedb7a93a95ea51f1257a98c56974969d7c72a",
        "article_id": "06-4lapy-koshachii-napolnitel",
        "title": "Как убрать запах кошачьего туалета? Выбираем наполнитель",
        "lead": "Подобрали варианты эффективных и комфортных для кошки наполнителей",
        "current_heading": {
          "block_index": 11,
          "level": 3,
          "text": "Совет №3. Регулярно меняйте наполнитель в лотке"
        },
        "caption": "Если у вас дома живёт несколько кошек, выбирайте впитывающий наполнитель. Главное, помните, что лоток нужно регулярно чистить. Это не даст размножаться вредным бактериям",
        "image_position": {
          "block_index": 22,
          "role": "article_image",
          "file": "03.jpeg"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 21,
            "type": "paragraph",
            "text": "Независимо от типа наполнителя, раз в месяц обязательно проводите полную уборку и дезинфекцию лотка. Помните, что кошки — чистюли, и грязный лоток может стать причиной отказа от него."
          },
          {
            "relation": "after",
            "block_index": 23,
            "type": "heading",
            "text": "Совет №4. Используйте силикагелевые наполнители"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Fixed camera. The cat calmly steps out of the litter tray toward the right, places the extended front paw on the floor, brings the other front paw over the rim, and shifts its weight forward in one smooth, confident motion. Its head tracks slightly ahead while the ears, whiskers, and tail move subtly with the step, ending naturally mid-walk beside the tray.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/03.prompt.json",
        "prompt_sha256": "572992de886bac15496d968058b1a4f2d79cceec1e3417e5074bbe03207bc17d",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/03.run.json",
        "run_sha256": "79cf4e5eb748258584261aad6c606c078c57bd6471eab61470e2c1142f336d5b",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite/result.json",
        "lite_result_sha256": "69207c46033a9ae11e3a4e09dd1ffb873810fce6051e0b56b3484a18e5e76e57"
      },
      "review_basis_sha256": "91bb22fc4174d902320ae6facda6602553c1cc21231fff695825b374e3662417"
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-2",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-2",
        "author_thread_id": "019f8bdb-6834-7940-920f-e52d0aa29967",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "1b1fbb343b7a48a1852ecf854f550bb1",
        "request_sha256": "6ec992b105a576bfddb7cd391338f36d591ff62a9fdc9704e204c0a2a22b6115",
        "submitted_at": "2026-07-22T22:12:46Z",
        "completed_at": "2026-07-22T22:13:47Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-2",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/09.mp4",
        "sha256": "ab2301ede6c4514cda4534ce1c7bd036a970b5dfa09466d905a82246f539e0a3",
        "bytes": 439244,
        "duration_seconds": 3.233,
        "width": 1264,
        "height": 704,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/13-ilinka-elitnyi-zhk/content.json",
        "source_sha256": "700ff43d87c96494025c293edb31389c08cf7bf05f4cc274cc9c0ca5d345a06c",
        "article_id": "13-ilinka-elitnyi-zhk",
        "title": "Показываем, что за элитный ЖК строят напротив Кремля",
        "lead": "Рассказываем о премиальном комплексе «Царев сад» в историческом районе Москвы",
        "current_heading": {
          "block_index": 26,
          "level": 2,
          "text": "Всё необходимое — на территории комплекса"
        },
        "caption": "Площадь спа-комплекса — более 5000 кв. м, здесь есть процедурные кабинеты, фитнес-зал и парные помещения",
        "image_position": {
          "block_index": 28,
          "role": "article_image",
          "file": "09.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 27,
            "type": "paragraph",
            "text": "Чтобы сыграть с единомышленниками в бильярд или расслабиться в сауне, необязательно выезжать за пределы комплекса. Прямо на территории «Резиденции 1864» есть спа-комплекс с фитнес-зоной и сауной, ресторан, бильярдная, кинотеатр, модные бутики и салоны красоты — всё, чтобы жить полной жизнью и не тратить время на дорогу."
          },
          {
            "relation": "after",
            "block_index": 29,
            "type": "paragraph",
            "text": "«Резиденция 1864» уже готова для заселения. Вам не придется ждать окончания строительства — получите ключи сразу после покупки и можете заезжать в коллекционные апартаменты."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "The camera remains fixed as the narrow waterfall streams flow steadily into the pool. Soft ripples spread outward across the turquoise water, gently shifting the underwater light reflections; nearby leaves tremble almost imperceptibly from the moving air. The ripples settle into a calm, continuous shimmer by the end.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "aspect_ratio": "source",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/09.prompt.json",
        "prompt_sha256": "951ab54a60f511660cb1f34e60118e4fd9d45ed1130b872268ed73d4f24e6160",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/09.run.json",
        "run_sha256": "ba1d15faef2f6d57c780867e7c0c4419fa4117fa21c3cd34761a326e3ca4d6ea",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-wan-2-2/result.json",
        "lite_result_sha256": "cb964d5399535af12b23c709f993cb58dc6cb21726fca381855959124b747aeb"
      },
      "review_basis_sha256": "911cc2944f081ab27e0e0dbc839a8f0f1ed94e40e04a41ea98f9d48a19e5a2d0"
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-7",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-7",
        "author_thread_id": "019f8bdb-689b-7773-b144-8f6fe84f45f9",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "OUExFOCitZoiO8AoOKMF",
        "request_sha256": "02ed7c661953f05549f9544fd4f1b811478f61fcfd6724a8fa813cd7fd39988b",
        "submitted_at": "2026-07-22T22:19:55Z",
        "completed_at": "2026-07-22T22:21:46Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-7",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/09.mp4",
        "sha256": "670be47b18967c8ed2f4da018620aa8e4285e9f565b52b30db8599e9dd1ff95b",
        "bytes": 13558133,
        "duration_seconds": 5.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/13-ilinka-elitnyi-zhk/content.json",
        "source_sha256": "700ff43d87c96494025c293edb31389c08cf7bf05f4cc274cc9c0ca5d345a06c",
        "article_id": "13-ilinka-elitnyi-zhk",
        "title": "Показываем, что за элитный ЖК строят напротив Кремля",
        "lead": "Рассказываем о премиальном комплексе «Царев сад» в историческом районе Москвы",
        "current_heading": {
          "block_index": 26,
          "level": 2,
          "text": "Всё необходимое — на территории комплекса"
        },
        "caption": "Площадь спа-комплекса — более 5000 кв. м, здесь есть процедурные кабинеты, фитнес-зал и парные помещения",
        "image_position": {
          "block_index": 28,
          "role": "article_image",
          "file": "09.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 27,
            "type": "paragraph",
            "text": "Чтобы сыграть с единомышленниками в бильярд или расслабиться в сауне, необязательно выезжать за пределы комплекса. Прямо на территории «Резиденции 1864» есть спа-комплекс с фитнес-зоной и сауной, ресторан, бильярдная, кинотеатр, модные бутики и салоны красоты — всё, чтобы жить полной жизнью и не тратить время на дорогу."
          },
          {
            "relation": "after",
            "block_index": 29,
            "type": "paragraph",
            "text": "«Резиденция 1864» уже готова для заселения. Вам не придется ждать окончания строительства — получите ключи сразу после покупки и можете заезжать в коллекционные апартаменты."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Keep the camera fixed. The narrow waterfall pours steadily into the pool for the full shot, sending overlapping ripples across the turquoise water. Underwater light shimmers and refracts over the tiled walls while the nearest leaves sway faintly in the humid air; the ripples gradually soften toward the end.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "verification-failed",
        "conforms": false,
        "warnings": [
          "audio"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/09.prompt.json",
        "prompt_sha256": "c37d4b0b430adf49e64d22c946c8d7c3c309b29631fb9b230d5577af7800d33d",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/09.run.json",
        "run_sha256": "5ab6ccdeca009f7871836aef5ca20ce34291ad8a5c1dfcae0d9276c63625848a",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-wan-2-7/result.json",
        "lite_result_sha256": "abe27aa81f462b7f52b1a6cfe34870209ebab12f20599d353948d81144d9eba6"
      },
      "review_basis_sha256": "f64bfdb45c3d25d101a534d9ea4c99adbbf584638b6ba1876e903ddb7e9c84a9"
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite",
        "author_thread_id": "019f8bdb-da5b-7aa1-8656-1d9063b5f0e8",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "xKjC2Ou6YRIdPRq6Y872",
        "request_sha256": "8873d331345668bd6fe78bc8bc7d72951c3580794b87a73aa2db84a36d075686",
        "submitted_at": "2026-07-22T22:30:12Z",
        "completed_at": "2026-07-22T22:32:18Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/09.mp4",
        "sha256": "83a3066f7529c524fc577d9b7e064f2d738ca0bedca741715eca8e7322340ff4",
        "bytes": 17457610,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/13-ilinka-elitnyi-zhk/content.json",
        "source_sha256": "700ff43d87c96494025c293edb31389c08cf7bf05f4cc274cc9c0ca5d345a06c",
        "article_id": "13-ilinka-elitnyi-zhk",
        "title": "Показываем, что за элитный ЖК строят напротив Кремля",
        "lead": "Рассказываем о премиальном комплексе «Царев сад» в историческом районе Москвы",
        "current_heading": {
          "block_index": 26,
          "level": 2,
          "text": "Всё необходимое — на территории комплекса"
        },
        "caption": "Площадь спа-комплекса — более 5000 кв. м, здесь есть процедурные кабинеты, фитнес-зал и парные помещения",
        "image_position": {
          "block_index": 28,
          "role": "article_image",
          "file": "09.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 27,
            "type": "paragraph",
            "text": "Чтобы сыграть с единомышленниками в бильярд или расслабиться в сауне, необязательно выезжать за пределы комплекса. Прямо на территории «Резиденции 1864» есть спа-комплекс с фитнес-зоной и сауной, ресторан, бильярдная, кинотеатр, модные бутики и салоны красоты — всё, чтобы жить полной жизнью и не тратить время на дорогу."
          },
          {
            "relation": "after",
            "block_index": 29,
            "type": "paragraph",
            "text": "«Резиденция 1864» уже готова для заселения. Вам не придется ждать окончания строительства — получите ключи сразу после покупки и можете заезжать в коллекционные апартаменты."
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "A very slow camera push toward the pool. The narrow waterfall streams steadily down the wall, creating expanding ripples across the water while the underwater light reflections shimmer gently. Keep the motion calm and continuous, with the ripples naturally spreading through the foreground by the end.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/09.prompt.json",
        "prompt_sha256": "c2692a7cdfd9dee4eca5254b335e4053c62d81b941e170b65e26522bcea83979",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/09.run.json",
        "run_sha256": "a75012321bef32c48203be6617ae40a82f26ffa6834688d2a29779f93853287b",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite/result.json",
        "lite_result_sha256": "718f0387354a253d442de89372e044c61048f81bb16ac167b2da384c63d5c4c5"
      },
      "review_basis_sha256": "1f8ed396422c56075432267084d8ba4c592d6e99dbe890e338ddbf612aad88c5"
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-2",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-2",
        "author_thread_id": "019f8bdb-d7d3-79a1-9352-a8f8be3ae19f",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "900b0f324cb84a98b0c52f0c6ea7ab4c",
        "request_sha256": "4c384c8c85ba622fb7b2f84c9b91fd84e338b5a919104ddc04150087a6c46b83",
        "submitted_at": "2026-07-22T22:13:47Z",
        "completed_at": "2026-07-22T22:14:46Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-2",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/04.mp4",
        "sha256": "d48d80d616d747a6a9b11b38585dd0af29270f561388bfa9b05c4ff9367cbc0c",
        "bytes": 192448,
        "duration_seconds": 3.233,
        "width": 1216,
        "height": 720,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/20-sravni-kreditnyi-reiting/content.json",
        "source_sha256": "bad2e96cc7affb4c7c5c7d6f51c59064ce327cb8295552284a2fc68580f3f04b",
        "article_id": "20-sravni-kreditnyi-reiting",
        "title": "Как повысить кредитный рейтинг, узнайте на Сравни",
        "lead": "Неприятно, когда банк отказал в выдаче кредита, а вы уже представили, какой ремонт сделаете на кухне или почти записались на онлайн-курс. Понять, почему пришло такое решение, не получится — ни поддержка, ни сотрудники отделения не раскроют настоящую причину.\nВот бы был сервис, который заранее предскажет и объяснит ответ банка. Оказывается, он уже есть — это «Кредитный рейтинг» от финансового",
        "current_heading": {
          "block_index": 12,
          "level": 2,
          "text": "Узнает, на какую сумму вам одобрят кредит"
        },
        "caption": "При доходе 100 тысяч рублей в месяц и наличии двух кредитных карт сервис покажет сумму до 2,49 млн рублей",
        "image_position": {
          "block_index": 15,
          "role": "article_image",
          "file": "04.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 14,
            "type": "paragraph",
            "text": "Чтобы узнать потенциальную сумму кредита, используйте сервис «Финансовый потенциал» от Сравни сразу после расчета кредитного рейтинга. Укажите размер официальной зарплаты, а сервис подскажет максимальную сумму кредита, ежемесячный платеж, примерную ставку и срок."
          },
          {
            "relation": "after",
            "block_index": 16,
            "type": "heading",
            "text": "Предложит варианты, как повысить кредитный рейтинг"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "A single fixed shot of the financial dashboard. A soft blue highlight travels clockwise along the existing blue arc of the circular chart at a steady pace, then the arc gives one subtle confirmation pulse while the displayed loan amount and monthly payment briefly brighten and settle. Keep all numbers, labels, cards, checkboxes, and layout unchanged.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "aspect_ratio": "source",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/04.prompt.json",
        "prompt_sha256": "21175d34c2504cce4fa8d55847f451370338879ac93ddc2e2d072c77b54c6940",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/04.run.json",
        "run_sha256": "2642cff66f258f66cb9de36fdf250fb35e7e4c15086d0b32393e3dc67ab38729",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-wan-2-2/result.json",
        "lite_result_sha256": "b25a38f82c600719c7843ed1f173fa63c07ded165f45da14af530fd58259a2cc"
      },
      "review_basis_sha256": "f83702bd18a095afdf4e4505305cfc48a28817f5652676a97043d180db81d560"
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-7",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-7",
        "author_thread_id": "019f8bdb-d239-71a0-84e9-c19f38f6c9f3",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "gIT0QHO3KgbLiqK4dBE3",
        "request_sha256": "67710964da8d4182feb4efbe6d684a953390d77fa3643ef12466c7bc5bbac006",
        "submitted_at": "2026-07-22T22:21:48Z",
        "completed_at": "2026-07-22T22:24:05Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-7",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/04.mp4",
        "sha256": "d1f5fcd6dcd337d7b12ce6e7b1aa339a085364fefd22f2d1d1f81615cb486aa8",
        "bytes": 1816802,
        "duration_seconds": 5.0,
        "width": 1858,
        "height": 1116,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/20-sravni-kreditnyi-reiting/content.json",
        "source_sha256": "bad2e96cc7affb4c7c5c7d6f51c59064ce327cb8295552284a2fc68580f3f04b",
        "article_id": "20-sravni-kreditnyi-reiting",
        "title": "Как повысить кредитный рейтинг, узнайте на Сравни",
        "lead": "Неприятно, когда банк отказал в выдаче кредита, а вы уже представили, какой ремонт сделаете на кухне или почти записались на онлайн-курс. Понять, почему пришло такое решение, не получится — ни поддержка, ни сотрудники отделения не раскроют настоящую причину.\nВот бы был сервис, который заранее предскажет и объяснит ответ банка. Оказывается, он уже есть — это «Кредитный рейтинг» от финансового",
        "current_heading": {
          "block_index": 12,
          "level": 2,
          "text": "Узнает, на какую сумму вам одобрят кредит"
        },
        "caption": "При доходе 100 тысяч рублей в месяц и наличии двух кредитных карт сервис покажет сумму до 2,49 млн рублей",
        "image_position": {
          "block_index": 15,
          "role": "article_image",
          "file": "04.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 14,
            "type": "paragraph",
            "text": "Чтобы узнать потенциальную сумму кредита, используйте сервис «Финансовый потенциал» от Сравни сразу после расчета кредитного рейтинга. Укажите размер официальной зарплаты, а сервис подскажет максимальную сумму кредита, ежемесячный платеж, примерную ставку и срок."
          },
          {
            "relation": "after",
            "block_index": 16,
            "type": "heading",
            "text": "Предложит варианты, как повысить кредитный рейтинг"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Keep the camera fixed. The purple load arc gently advances a few degrees while the two checked card rows receive a soft sequential highlight; the loan amount and monthly payment subtly count into their displayed values, then settle as the arc stops. Preserve the clean, readable interface.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "verification-failed",
        "conforms": false,
        "warnings": [
          "audio",
          "resolution",
          "aspect_ratio"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/04.prompt.json",
        "prompt_sha256": "cb430f64ad9fe2eac99ee24a1b7ec69cbf3397a37d4df75105857f457d283e8a",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/04.run.json",
        "run_sha256": "e57e5ad91a7998180c7e601f6c08c22a2298963a5c221f7e7a09748c715e1ecf",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-wan-2-7/result.json",
        "lite_result_sha256": "79d245b25379a9c39a152854f85ccd63a6140a288b23b0543bd62c0c38312a57"
      },
      "review_basis_sha256": "1f0cd8c95302d4697c6884bc9e0b775e24a72f656697362573ec95a7bd6b676f"
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0
      },
      "approach": {
        "id": "clipmaker-lite-current",
        "label": "Lite · текущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.2.1",
        "attribution_basis": "isolated_runner_verified",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.2.1",
        "planning_run_id": "promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite",
        "author_thread_id": "019f8bdb-da21-7df3-913c-351d69e8f33e",
        "batch_id": "promopages-9891-lite3-20260723",
        "provenance_verified": true
      },
      "generation": {
        "job_id": "FRP1YR3ES9MQtuu8G4Nb",
        "request_sha256": "a30bfdecd4c6155803cec37b013f71203c9ad6b09b11232c8628ce0d6512cda1",
        "submitted_at": "2026-07-22T22:32:21Z",
        "completed_at": "2026-07-22T22:34:00Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/04.mp4",
        "sha256": "2bf02ded218f4d91460c43bb08e6040cc635846bb9d6b5fb6a5ce2b91a59dcfa",
        "bytes": 690989,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": {
        "input_scope": "full_article_json",
        "source_path": "PROMOPAGES-9884/articles/20-sravni-kreditnyi-reiting/content.json",
        "source_sha256": "bad2e96cc7affb4c7c5c7d6f51c59064ce327cb8295552284a2fc68580f3f04b",
        "article_id": "20-sravni-kreditnyi-reiting",
        "title": "Как повысить кредитный рейтинг, узнайте на Сравни",
        "lead": "Неприятно, когда банк отказал в выдаче кредита, а вы уже представили, какой ремонт сделаете на кухне или почти записались на онлайн-курс. Понять, почему пришло такое решение, не получится — ни поддержка, ни сотрудники отделения не раскроют настоящую причину.\nВот бы был сервис, который заранее предскажет и объяснит ответ банка. Оказывается, он уже есть — это «Кредитный рейтинг» от финансового",
        "current_heading": {
          "block_index": 12,
          "level": 2,
          "text": "Узнает, на какую сумму вам одобрят кредит"
        },
        "caption": "При доходе 100 тысяч рублей в месяц и наличии двух кредитных карт сервис покажет сумму до 2,49 млн рублей",
        "image_position": {
          "block_index": 15,
          "role": "article_image",
          "file": "04.png"
        },
        "fragments": [
          {
            "relation": "before",
            "block_index": 14,
            "type": "paragraph",
            "text": "Чтобы узнать потенциальную сумму кредита, используйте сервис «Финансовый потенциал» от Сравни сразу после расчета кредитного рейтинга. Укажите размер официальной зарплаты, а сервис подскажет максимальную сумму кредита, ежемесячный платеж, примерную ставку и срок."
          },
          {
            "relation": "after",
            "block_index": 16,
            "type": "heading",
            "text": "Предложит варианты, как повысить кредитный рейтинг"
          }
        ]
      },
      "context_status": {
        "availability": "shown",
        "reason": null
      },
      "prompt": {
        "positive": "Keep the camera fixed on the interface. The lower credit card checkbox smoothly switches off; in the same continuous response, the purple gauge arc retracts clockwise and the available credit amount counts upward, easing into its updated value near the end. All other UI elements remain still.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "aspect_ratio": "16:9",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/04.prompt.json",
        "prompt_sha256": "2e1c3c7fade91e4d9c45713a5a2a89f104bc5c21d25ce34c46e8eda4bf8c2ada",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/04.run.json",
        "run_sha256": "6b98c7ecd3fa582b7d4c56de000c3c0cd99e3b4d6912cd15488ab40d294a5591",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite/result.json",
        "lite_result_sha256": "2e4fbb460d3590623e129f5b17922d24b2455f3b1fb035078064b35a1a807796"
      },
      "review_basis_sha256": "70c7b7a9f2bdc6f6376b3be5b084d011bf3d7ea972d9c4e3e9793238aa805fb7"
    },
    {
      "id": "01-pharmocean-magiia-magniia-02-wan-streamlit-wan-2-2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-cross-model-control",
        "label": "Lite · перенос Wan 2.7 → Wan 2.2"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_lite_prompt_reused_cross_model",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-01-portrait-hands-wan-2-7",
        "author_thread_id": "019f8a91-5a37-7362-a4e7-42e3996117e8",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "01-pharmocean-magiia-magniia-02-wan-streamlit-wan-2-2",
        "request_sha256": null,
        "submitted_at": null,
        "completed_at": "2026-07-22T17:21:43.939059Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "01-pharmocean-magiia-magniia-02-wan-streamlit-wan-2-2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-streamlit-wan-2.2/02.mp4",
        "sha256": "2fb80e8d968e333a73c96e39c5168c8fc11f4ed8986131a5c688fe49f5fa5d74",
        "bytes": 359591,
        "duration_seconds": 3.233333,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": null
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Her tense reaction builds continuously: both hands tremble subtly and move a little closer to her face as her fingers curl tighter, her eyes dart briefly and then refocus on the camera, and her clenched expression intensifies before easing slightly near the end. Keep the camera fixed.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "disabled",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": false,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "verified",
        "review_status": "verified",
        "conforms": true,
        "warnings": [],
        "requested": {
          "fps": 30,
          "frames": 97,
          "last_frame": null,
          "loop": false,
          "resolution": "720p",
          "seed": 1
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-streamlit-wan-2.2/02.prompt.json",
        "prompt_sha256": "f594dd05336c47ed341f4e7ca10e2a4c8d82d8962ce01b8d8d4947c5c044c4a8",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-streamlit-wan-2.2/02.run.json",
        "run_sha256": "11963f22dfbbf98734772ab5e9fd87e1bf9b64442d8365865720889277fc720b",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-01-portrait-hands-wan-2-7/result.json",
        "lite_result_sha256": "1fb79865fa6ebfe22b9d2e0209a0d48c7eeca2e2295f1152171a8225a537ec1b"
      },
      "review_basis_sha256": "d380fc3bf53ba2869b08dbfd4c67f56d6cbae2c86bdb609df0e03c88e96c9010"
    },
    {
      "id": "promopages-9891-schemafix-01-portrait-hands-wan-2-7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-01-portrait-hands-wan-2-7",
        "author_thread_id": "019f8a91-5a37-7362-a4e7-42e3996117e8",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "vbMNZQ2spMXzHCCTaAQs",
        "request_sha256": "0521bffa9ef802371ebc165bf542c19bb5fa86c9d97321c2c0724f6beb49efde",
        "submitted_at": "2026-07-22T16:21:26Z",
        "completed_at": "2026-07-22T16:23:26Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-schemafix-01-portrait-hands-wan-2-7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-2.7/02.mp4",
        "sha256": "fb48c11542ae4bb23818ca71030b4a2fb414864be612508d6d544edcb5aea1dd",
        "bytes": 4400591,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Her tense reaction builds continuously: both hands tremble subtly and move a little closer to her face as her fingers curl tighter, her eyes dart briefly and then refocus on the camera, and her clenched expression intensifies before easing slightly near the end. Keep the camera fixed.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "audio does not match the Lite request",
          "resolution does not match the Lite request",
          "aspect_ratio does not match the Lite request"
        ],
        "requested": {
          "aspect_ratio": "4:3",
          "duration_seconds": 5,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-2.7/02.prompt.json",
        "prompt_sha256": "710d41149ae03e712a9c499dba14481f68d9c34d5fed0d708ab365ba8e69f723",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/wan-2.7/02.run.json",
        "run_sha256": "35b691f31d8fa171ee3cdcfd2bc531a4a8a3f9f9c2da27a75d35efe9a8ca40f6",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-01-portrait-hands-wan-2-7/result.json",
        "lite_result_sha256": "1fb79865fa6ebfe22b9d2e0209a0d48c7eeca2e2295f1152171a8225a537ec1b"
      },
      "review_basis_sha256": "1401b92f4724d985bcff3edfc5a0a0866295f49822d284c2c9525de4955e10f3"
    },
    {
      "id": "promopages-9891-schemafix-01-portrait-hands-veo-3-1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-01-portrait-hands-veo-3-1-lite",
        "author_thread_id": "019f8a92-0d38-7342-9a19-cba0dee9f8d5",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "7yGkEaqKfGMGqxfEoFS6",
        "request_sha256": "ae9530fcb0a699162bb11ecdd8fdce87f7afc47d3b7efbda31da247eab5e2782",
        "submitted_at": "2026-07-22T16:23:30Z",
        "completed_at": "2026-07-22T16:25:21Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-schemafix-01-portrait-hands-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/veo-3.1-lite/02.mp4",
        "sha256": "29ab24d9273eb88f826b1e41e72a579027fc3c37aae37c43918626e530fd6675",
        "bytes": 4056919,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Slowly push in as the woman takes a shallow inhale and her anxious tension steadily builds. Her raised fingers curl slightly tighter toward her face, her jaw clenches, and one eyelid gives a brief subtle twitch near the end. Keep it one continuous restrained reaction, ending at the peak of tension.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 4,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/veo-3.1-lite/02.prompt.json",
        "prompt_sha256": "993fa79fd96d8f4364c4d2d9ed2be41ff7d2fa263ca971f431267b91e6233521",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/veo-3.1-lite/02.run.json",
        "run_sha256": "2ff1137096b2bb3ee6cdf9f0a88045f60fca46b68a15923aa787c5a35df12860",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-01-portrait-hands-veo-3-1-lite/result.json",
        "lite_result_sha256": "b18a75356708f958105f82567579e852b48b22095e18e92e25a1e3108582e651"
      },
      "review_basis_sha256": "3d68db5fed44e81c8190b42abf9018461ac5025fab77a0b7a51a85365d720625"
    },
    {
      "id": "04-graceface-antivozrastnaia-syvorotka-05-wan-streamlit-wan-2-2",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-cross-model-control",
        "label": "Lite · перенос Wan 2.7 → Wan 2.2"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_lite_prompt_reused_cross_model",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-02-product-dropper-wan-2-7",
        "author_thread_id": "019f8a92-6c5a-7c50-88d0-c38e98104f78",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "04-graceface-antivozrastnaia-syvorotka-05-wan-streamlit-wan-2-2",
        "request_sha256": null,
        "submitted_at": "2026-07-22T17:08:25.842428Z",
        "completed_at": "2026-07-22T17:21:43.965078Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "04-graceface-antivozrastnaia-syvorotka-05-wan-streamlit-wan-2-2",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-streamlit-wan-2.2/05.mp4",
        "sha256": "5877c122833ea91576a2acaca7cd8d9f943323558a01014374c18162ce87245a",
        "bytes": 151577,
        "duration_seconds": 3.233333,
        "width": 1200,
        "height": 736,
        "fps": 30.0,
        "frames": 97,
        "has_audio": null
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Keep the camera fixed. Clear serum slowly travels down the pipette and gathers into a rounded droplet at the tip; the droplet elongates under gravity, detaches near the end, and falls toward the cut truffle while the pipette and bottle remain still.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "disabled",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": false,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "verified",
        "review_status": "verified",
        "conforms": true,
        "warnings": [],
        "requested": {
          "fps": 30,
          "frames": 97,
          "last_frame": null,
          "loop": false,
          "resolution": "720p",
          "seed": 1
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-streamlit-wan-2.2/05.prompt.json",
        "prompt_sha256": "7c60db90259bb4b4e222c2fd9a797ae2bda7fcfbfdccc466e74ca3b49e811b5b",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-streamlit-wan-2.2/05.run.json",
        "run_sha256": "b7e9847c79dbbbe1e757c858fa8d9c1b97b6557eaa6f0b1df829c036522a2279",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-02-product-dropper-wan-2-7/result.json",
        "lite_result_sha256": "773666ce09639d143f3c3dab0e297ad39a607151ef5267331563744b79170457"
      },
      "review_basis_sha256": "e07db75b28b9f5297b101b52a399a9a80eba1bf34a620cd850be4d2a66f13d22"
    },
    {
      "id": "promopages-9891-schemafix-02-product-dropper-wan-2-7",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-02-product-dropper-wan-2-7",
        "author_thread_id": "019f8a92-6c5a-7c50-88d0-c38e98104f78",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "YNaiRojaJnv0YrDOtIZ9",
        "request_sha256": "f55671e1fbf5589f5808c1f64c214cced6bd0ce1b3e4338836da90c5a9c303fc",
        "submitted_at": "2026-07-22T16:25:23Z",
        "completed_at": "2026-07-22T16:39:34Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-schemafix-02-product-dropper-wan-2-7",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-2.7/05.mp4",
        "sha256": "a26558f7c959f9501ff62d907fadb9cc185915305a625bb43ee602ab8099bd24",
        "bytes": 1623035,
        "duration_seconds": 5.0,
        "width": 1820,
        "height": 1138,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Keep the camera fixed. Clear serum slowly travels down the pipette and gathers into a rounded droplet at the tip; the droplet elongates under gravity, detaches near the end, and falls toward the cut truffle while the pipette and bottle remain still.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "audio does not match the Lite request",
          "resolution does not match the Lite request",
          "aspect_ratio does not match the Lite request"
        ],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 5,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-2.7/05.prompt.json",
        "prompt_sha256": "825cd53e1b514fa76ee01906ddcd8049719cebec759a5fa2b1fef73365ebd933",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/wan-2.7/05.run.json",
        "run_sha256": "b34d7d28684d03d86d05efed10db7b48284a3ac238be1698c347f52b1fb45142",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-02-product-dropper-wan-2-7/result.json",
        "lite_result_sha256": "773666ce09639d143f3c3dab0e297ad39a607151ef5267331563744b79170457"
      },
      "review_basis_sha256": "9ab42b6637cb14d8999e6e56ef598992125e3b200deda0e8867d34735b40fbd1"
    },
    {
      "id": "promopages-9891-schemafix-02-product-dropper-veo-3-1-lite",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-02-product-dropper-veo-3-1-lite",
        "author_thread_id": "019f8a92-a395-7d33-8348-16327e24d1d1",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "nDsfBGCRo9Sn8UoXRS4c",
        "request_sha256": "9188a2ebce1d812029e7d8c684dee3b29222425c77c7fb2412b3f874a5062ff7",
        "submitted_at": "2026-07-22T16:39:38Z",
        "completed_at": "2026-07-22T16:41:27Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-schemafix-02-product-dropper-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/veo-3.1-lite/05.mp4",
        "sha256": "c0f3486ad1ce6dd46b4a10eee67cd8579b8b6b7537a885d0c60cef3eed896cb2",
        "bytes": 1528197,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "A very slow push-in toward the pipette tip. The clear serum droplet gradually swells and stretches under gravity, then detaches near the end and falls smoothly toward the white surface while a tiny bead remains on the tip. Single continuous shot.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 4,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/veo-3.1-lite/05.prompt.json",
        "prompt_sha256": "fe0804e935bcc17d9b9b574bcdd5e907fc08661f1b507f9541806fb311613ae1",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/veo-3.1-lite/05.run.json",
        "run_sha256": "6e2a04cc726b976295f19268982d0c0258e394263f1784b1a84ac0b0703cdf05",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-02-product-dropper-veo-3-1-lite/result.json",
        "lite_result_sha256": "46134a5f1dfd508a1a0b8d0cb29795bdf69e478027f42eca5a69012b9499c18b"
      },
      "review_basis_sha256": "ba4bdbfd1d275ba063588394634c5a6be3fcdaf423aa37f36351ed2edf356afe"
    },
    {
      "id": "06-4lapy-koshachii-napolnitel-03-wan-streamlit-wan-2-2",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-cross-model-control",
        "label": "Lite · перенос Wan 2.7 → Wan 2.2"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_lite_prompt_reused_cross_model",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-03-animal-step-wan-2-7",
        "author_thread_id": "019f8a92-ee62-7411-94d3-7b1d24dab1bc",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "06-4lapy-koshachii-napolnitel-03-wan-streamlit-wan-2-2",
        "request_sha256": null,
        "submitted_at": "2026-07-22T17:09:26.239722Z",
        "completed_at": "2026-07-22T17:21:43.992777Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "06-4lapy-koshachii-napolnitel-03-wan-streamlit-wan-2-2",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-streamlit-wan-2.2/03.mp4",
        "sha256": "3fdae596e81e1406335de3f80d8bf0f27e84d554ed186023a72b97ff33e373d9",
        "bytes": 400119,
        "duration_seconds": 3.233333,
        "width": 1408,
        "height": 624,
        "fps": 30.0,
        "frames": 97,
        "has_audio": null
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "The cat calmly steps forward out of the litter tray, placing each paw naturally on the floor as its weight shifts smoothly off the rim. Its head stays alert and turns slightly toward screen right, with subtle ear and tail movement. Keep the camera fixed, ending with the cat fully on the floor and continuing one gentle step forward.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "disabled",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": false,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "verified",
        "review_status": "verified",
        "conforms": true,
        "warnings": [],
        "requested": {
          "fps": 30,
          "frames": 97,
          "last_frame": null,
          "loop": false,
          "resolution": "720p",
          "seed": 1
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-streamlit-wan-2.2/03.prompt.json",
        "prompt_sha256": "730c221a13265da76f1fca9e62e1630c19706617b7ac5675593dcebc539327a6",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-streamlit-wan-2.2/03.run.json",
        "run_sha256": "9161c5ef08bacc2b72facc7bbdde01d0648a0d7b08014d451074e50772f95e0a",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-03-animal-step-wan-2-7/result.json",
        "lite_result_sha256": "463b1433f6ab13e4c2c99e07671ddeabb249e2d9d3813fab7d4e0ba440ab2e07"
      },
      "review_basis_sha256": "11725c8c720c80733df664cf9ab21c5a040d89bd299842afd12cba4022c807a7"
    },
    {
      "id": "promopages-9891-schemafix-03-animal-step-wan-2-7",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-03-animal-step-wan-2-7",
        "author_thread_id": "019f8a92-ee62-7411-94d3-7b1d24dab1bc",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "mainLZN4giKNSQaFg4bw",
        "request_sha256": "9816583c0174b51f458773b919f3d743106a229283a5a557e21a24f9f9466c9b",
        "submitted_at": "2026-07-22T16:41:30Z",
        "completed_at": "2026-07-22T16:42:49Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-schemafix-03-animal-step-wan-2-7",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-2.7/03.mp4",
        "sha256": "90a4eea562e8b73fa1da00cd55091083b2bc9252bff714307b12f4816cf53e2b",
        "bytes": 5005200,
        "duration_seconds": 5.0,
        "width": 2146,
        "height": 966,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "The cat calmly steps forward out of the litter tray, placing each paw naturally on the floor as its weight shifts smoothly off the rim. Its head stays alert and turns slightly toward screen right, with subtle ear and tail movement. Keep the camera fixed, ending with the cat fully on the floor and continuing one gentle step forward.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "audio does not match the Lite request",
          "resolution does not match the Lite request",
          "aspect_ratio does not match the Lite request"
        ],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 5,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-2.7/03.prompt.json",
        "prompt_sha256": "c604aed9ac9f891c9e576c6de17cf684502e264f37a04164816489ec71b54501",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/wan-2.7/03.run.json",
        "run_sha256": "5878bf9e5de400c3136221fed18ef87c90a50b04cfca9536f5f579910ec21e87",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-03-animal-step-wan-2-7/result.json",
        "lite_result_sha256": "463b1433f6ab13e4c2c99e07671ddeabb249e2d9d3813fab7d4e0ba440ab2e07"
      },
      "review_basis_sha256": "5cf8e39e5baa449ed9a3c5bc301ea12728093c4e53dffb07379db235f1d99da5"
    },
    {
      "id": "promopages-9891-schemafix-03-animal-step-veo-3-1-lite",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-03-animal-step-veo-3-1-lite",
        "author_thread_id": "019f8a93-285f-7280-9fb1-03e31aa4f59b",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "LC6Kzt4hI7jHiixSZgwX",
        "request_sha256": "3ce4f0edf21e5ce7b2173de5446a667c8d24dbf6921a2214af0e81cc96674981",
        "submitted_at": "2026-07-22T16:42:53Z",
        "completed_at": "2026-07-22T16:44:48Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-schemafix-03-animal-step-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/veo-3.1-lite/03.mp4",
        "sha256": "54d8d276cf78d50c4892187f762f1988547bd6fc09b6bbe1e7fb656c4837919d",
        "bytes": 5702273,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Fixed camera. The cat calmly completes its step out of the litter tray: the lowered front paw lands on the floor, its weight shifts forward, the other front paw follows, and it finishes standing relaxed beside the tray. Subtle head, whisker, and ear motion accompanies the smooth, unhurried movement in one continuous shot.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 4,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/veo-3.1-lite/03.prompt.json",
        "prompt_sha256": "d7386d349ab6de053a8606a216030b47441dfd6ff248a5a97e22ddb7156d2114",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/veo-3.1-lite/03.run.json",
        "run_sha256": "6f1b510ee574dc721713102eb3bccc44a2a2c4ff4623667d12d994a90fa92ff5",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-03-animal-step-veo-3-1-lite/result.json",
        "lite_result_sha256": "012935700e0062e3082975fe8a13716b752d66acbd5ca9a750e374087e85e940"
      },
      "review_basis_sha256": "01c10be06281de8466b2b6ef44d22af2f96d10d3fc7d712d2339c0eecb5e6877"
    },
    {
      "id": "13-ilinka-elitnyi-zhk-09-wan-streamlit-wan-2-2",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-cross-model-control",
        "label": "Lite · перенос Wan 2.7 → Wan 2.2"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_lite_prompt_reused_cross_model",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-04-interior-water-wan-2-7",
        "author_thread_id": "019f8a93-587e-7001-acbe-5171fcdf6826",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "13-ilinka-elitnyi-zhk-09-wan-streamlit-wan-2-2",
        "request_sha256": null,
        "submitted_at": "2026-07-22T17:11:00.974847Z",
        "completed_at": "2026-07-22T17:21:44.024755Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "13-ilinka-elitnyi-zhk-09-wan-streamlit-wan-2-2",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-streamlit-wan-2.2/09.mp4",
        "sha256": "b37b4e2c6d783111977395caeffc414cb30deab5defaa5e7c3405a50dfc3c29c",
        "bytes": 406365,
        "duration_seconds": 3.233333,
        "width": 1264,
        "height": 704,
        "fps": 30.0,
        "frames": 97,
        "has_audio": null
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Gentle ripples travel continuously across the pool, making the turquoise underwater reflections drift and shimmer over the tiles. A few leaves on the living wall sway almost imperceptibly. The camera makes a very slow push toward the water and daybed, settling into a calm view as the ripples softly diminish near the end.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "disabled",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": false,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "verified",
        "review_status": "verified",
        "conforms": true,
        "warnings": [],
        "requested": {
          "fps": 30,
          "frames": 97,
          "last_frame": null,
          "loop": false,
          "resolution": "720p",
          "seed": 1
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-streamlit-wan-2.2/09.prompt.json",
        "prompt_sha256": "fc4a0e018ff5305136f448da7fd0091557dd126dd77f5bd3fe638c338b824746",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-streamlit-wan-2.2/09.run.json",
        "run_sha256": "fa9b847e0e358f33a0610fdbcdca40e77c3f1bd580eda74c720f5081280d35ef",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-04-interior-water-wan-2-7/result.json",
        "lite_result_sha256": "9f5bca28aeac35e48f85f4c81c24ef0a730e8701ba31ad17cb814d4317d0fbd6"
      },
      "review_basis_sha256": "157f18f9a6b0939c4455de9d0bb29e12095161cd61d5d134f13026166759d672"
    },
    {
      "id": "promopages-9891-schemafix-04-interior-water-wan-2-7",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-04-interior-water-wan-2-7",
        "author_thread_id": "019f8a93-587e-7001-acbe-5171fcdf6826",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "7IloVlIraZI6NidF7G7i",
        "request_sha256": "8df73a5025d9d55539b539cefef7f380246eb339b77d81c46342d9262de63b57",
        "submitted_at": "2026-07-22T16:19:24Z",
        "completed_at": "2026-07-22T16:20:43Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-schemafix-04-interior-water-wan-2-7",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-2.7/09.mp4",
        "sha256": "ba481f7dd9cdc28a75fd1f29179cae7bf9403702c5afc249716327e77eafd11b",
        "bytes": 23910119,
        "duration_seconds": 5.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Gentle ripples travel continuously across the pool, making the turquoise underwater reflections drift and shimmer over the tiles. A few leaves on the living wall sway almost imperceptibly. The camera makes a very slow push toward the water and daybed, settling into a calm view as the ripples softly diminish near the end.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "audio does not match the Lite request"
        ],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 5,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-2.7/09.prompt.json",
        "prompt_sha256": "65646e4e3860e8afdeb0abbbfbdfecd24bbd2d9cc37d62f2e2a83a75606cbc05",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/wan-2.7/09.run.json",
        "run_sha256": "21d47972d682cf82408f4208fa3a27abe140a31e08de8d4103bd146ca7e309ae",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-04-interior-water-wan-2-7/result.json",
        "lite_result_sha256": "9f5bca28aeac35e48f85f4c81c24ef0a730e8701ba31ad17cb814d4317d0fbd6"
      },
      "review_basis_sha256": "1088600e9563c552c774b50ce351d5f7c662e568f51935f624f115eaca64238e"
    },
    {
      "id": "promopages-9891-schemafix-04-interior-water-veo-3-1-lite",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-04-interior-water-veo-3-1-lite",
        "author_thread_id": "019f8a93-a19e-76e3-ad15-3acb87bcfb9b",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "jbh3AbWt6HFdLacy6gIk",
        "request_sha256": "aafbe7b5a46a9f679682e9a3b74d7e0bd83e28b2fa3aae4c427b36e99a022acf",
        "submitted_at": "2026-07-22T16:44:53Z",
        "completed_at": "2026-07-22T16:47:41Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-schemafix-04-interior-water-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/veo-3.1-lite/09.mp4",
        "sha256": "d0bf46e5d7ad884dd8baabc1fa5abe7630c9f4817159124ca6f33697a1b0605a",
        "bytes": 21101978,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Hold the camera fixed. The wall cascade flows steadily into the pool, sending gentle overlapping ripples across the water toward the foreground. Turquoise underwater light reflections shimmer and drift naturally over the tiled basin while a few leaves beside the cascade move almost imperceptibly in the humid air. The ripples broaden and settle into a calm, softly undulating surface near the end.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 4,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/veo-3.1-lite/09.prompt.json",
        "prompt_sha256": "eb19edd7c210aaf421efe17274028bba96d0819dfcd4d31cfedeb1f29582b938",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/veo-3.1-lite/09.run.json",
        "run_sha256": "188b6138e48250bb2cf7a524db7cd222f173d2c05345e5e176d675202cecd179",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-04-interior-water-veo-3-1-lite/result.json",
        "lite_result_sha256": "2a2bbaa060281f62c0676a31f34872b7630b00fb31d6b0e21daa352dd329f31c"
      },
      "review_basis_sha256": "80e3beff0ad51e045f0fcb344d4fc5b3a9f08d4555dedd2f3c12908fdc92bef7"
    },
    {
      "id": "20-sravni-kreditnyi-reiting-04-wan-streamlit-wan-2-2",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-cross-model-control",
        "label": "Lite · перенос Wan 2.7 → Wan 2.2"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_lite_prompt_reused_cross_model",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-05-finance-ui-wan-2-7",
        "author_thread_id": "019f8a93-ec0c-7ff2-a605-7882d7b9be21",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "20-sravni-kreditnyi-reiting-04-wan-streamlit-wan-2-2",
        "request_sha256": null,
        "submitted_at": "2026-07-22T17:12:35.241760Z",
        "completed_at": "2026-07-22T17:21:44.050274Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "20-sravni-kreditnyi-reiting-04-wan-streamlit-wan-2-2",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-streamlit-wan-2.2/04.mp4",
        "sha256": "1cdf6e2aaab1228f9d64badfd9c249e2012829e06fb219e6bfd68b6195f31e9c",
        "bytes": 202709,
        "duration_seconds": 3.233333,
        "width": 1216,
        "height": 720,
        "fps": 30.0,
        "frames": 97,
        "has_audio": null
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Keep the interface fixed and readable. The purple arc on the circular chart advances smoothly clockwise at a measured pace, then settles with a gentle pulse; the two active blue checkmarks respond with one subtle synchronized glow. Use a very slow, slight push-in toward the chart and loan amount, ending naturally on the completed calculation.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "disabled",
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": false,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "verified",
        "review_status": "verified",
        "conforms": true,
        "warnings": [],
        "requested": {
          "fps": 30,
          "frames": 97,
          "last_frame": null,
          "loop": false,
          "resolution": "720p",
          "seed": 1
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-streamlit-wan-2.2/04.prompt.json",
        "prompt_sha256": "1f3070fdac7d15babb6ade0be03bec0cb9b28467c887f95975ce0b7e540f19ea",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-streamlit-wan-2.2/04.run.json",
        "run_sha256": "0cd5cb24364be2185d61ae8d6d90f373f3bec5e2668c09bf45696ed598ccdf10",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-05-finance-ui-wan-2-7/result.json",
        "lite_result_sha256": "98d64df54758144ca452b67325a00db65800166f4ced313e7cb29a464b0b2598"
      },
      "review_basis_sha256": "12dc218a0edc671b02a04d2e2ab0912faacbbf3c1445b3e2b59f819958b3b366"
    },
    {
      "id": "promopages-9891-schemafix-05-finance-ui-wan-2-7",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-05-finance-ui-wan-2-7",
        "author_thread_id": "019f8a93-ec0c-7ff2-a605-7882d7b9be21",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "ZKnVvYNeidkDzLEsmdSS",
        "request_sha256": "6899d0601dc0ad5da829c29d5efd46982a6166f54015d70d5794e9f11f532fbb",
        "submitted_at": "2026-07-22T16:47:43Z",
        "completed_at": "2026-07-22T16:49:32Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9891-schemafix-05-finance-ui-wan-2-7",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-2.7/04.mp4",
        "sha256": "85ee260d61ed1028d4e801a55a6c51987e257c89d100787bc40dc14845eacee8",
        "bytes": 4099167,
        "duration_seconds": 5.0,
        "width": 1858,
        "height": 1116,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Keep the interface fixed and readable. The purple arc on the circular chart advances smoothly clockwise at a measured pace, then settles with a gentle pulse; the two active blue checkmarks respond with one subtle synchronized glow. Use a very slow, slight push-in toward the chart and loan amount, ending naturally on the completed calculation.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.7",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "audio does not match the Lite request",
          "resolution does not match the Lite request",
          "aspect_ratio does not match the Lite request"
        ],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 5,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-2.7/04.prompt.json",
        "prompt_sha256": "925000a5018a55d132ef796cf8ff407a51d8fe8bf4e8c26084a7e8c2a8f1cde4",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/wan-2.7/04.run.json",
        "run_sha256": "471fb5bb45f32146ff554b496dd6b4c700126645ef66bd118458faa28d616a86",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-05-finance-ui-wan-2-7/result.json",
        "lite_result_sha256": "98d64df54758144ca452b67325a00db65800166f4ced313e7cb29a464b0b2598"
      },
      "review_basis_sha256": "342d8a7248775e6c948f28fdfc2aa8865f31d39c82a65488f189942c1342369f"
    },
    {
      "id": "promopages-9891-schemafix-05-finance-ui-veo-3-1-lite",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1
      },
      "approach": {
        "id": "clipmaker-lite-previous-native",
        "label": "Lite · предыдущая итерация"
      },
      "prompt_author": {
        "id": "clipmaker-lite",
        "label": "Clipmaker Lite",
        "contract_version": "1.1.1",
        "attribution_basis": "historical_isolated_runner_receipt",
        "provenance_verified": true
      },
      "agent": {
        "id": "clipmaker-lite",
        "contract_version": "1.1.1",
        "planning_run_id": "promopages-9891-schemafix-05-finance-ui-veo-3-1-lite",
        "author_thread_id": "019f8a94-518d-7a11-8031-80cbc79adb87",
        "batch_id": null,
        "provenance_verified": true
      },
      "generation": {
        "job_id": "ROr5FKmmLv7NcitC7YDr",
        "request_sha256": "8fbd3b44af31ca31285eafd742a0cd186ae8db4cdc5a37d920b8846850764c34",
        "submitted_at": "2026-07-22T16:49:36Z",
        "completed_at": "2026-07-22T16:51:24Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9891-schemafix-05-finance-ui-veo-3-1-lite",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/veo-3.1-lite/04.mp4",
        "sha256": "47db419f7251fcef80f134122c9e9445fa00c11f58c4fa95e5da96a58e283845",
        "bytes": 697326,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "omitted_by_review_policy",
        "reason": "Контекст не показывается для этой исторической итерации."
      },
      "prompt": {
        "positive": "Fixed camera. Animate one smooth financial recalculation: the blue arc of the circular indicator grows clockwise from a short stroke to its displayed 15.8% length over four seconds, easing gently as it reaches the final position. The two blue checkmarks give a subtle synchronized confirmation pulse during the calculation. Keep all interface text and numbers stable and readable, ending on the source-image state.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "google/veo-3.1-lite",
        "native_for_generation_model": true,
        "negative_transport": "none"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "aspect_ratio": "16:9",
          "duration_seconds": 4,
          "generate_audio": false,
          "resolution": "1080p"
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/veo-3.1-lite/04.prompt.json",
        "prompt_sha256": "456fca66238b49fe2d19df2ff0fd6dc59408dec8231f890c267c48cb95b0ed90",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/veo-3.1-lite/04.run.json",
        "run_sha256": "04224c1addf900ad086a9a7827730952f91f38873f60ab3d35e554f83553650a",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-schemafix-05-finance-ui-veo-3-1-lite/result.json",
        "lite_result_sha256": "6466bde0725d1cf5b94492e9ca1abb85fd1157a72df877b16db63a351552f6d3"
      },
      "review_basis_sha256": "dbdea4adb8f17b1e30b979bf1001a47a7bc838cd33731bb6fe0b78019df8f834"
    },
    {
      "id": "promopages-9856-classic-01-portrait-hands-wan-2.2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "a8d8de645856486cb8a859b89846ae07",
        "request_sha256": "3f703e03ed92e5174eda0b5d6847f0a946fe755a8ba2dac5d9d3f1c19b8991d4",
        "submitted_at": "2026-07-21T11:53:12Z",
        "completed_at": "2026-07-21T11:54:13Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-01-portrait-hands-wan-2.2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.2/02.mp4",
        "sha256": "1049fabec1885a15d93550bb666f09938b3b49d358773560d3a31c8476ce2d80",
        "bytes": 287246,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the centered tight close-up of a woman looking directly at the camera with wide blue-gray eyes, a clenched-teeth grimace, brown hair in a bun, and both splayed hands raised beside her cheeks. Preserve her exact identity, facial proportions, eye color and gaze, hairstyle, navy-and-white striped top, the anatomy and original positions of every visible finger, the softly blurred indoor background, lighting, crop, composition, and aspect ratio.\n\nThe first frame already shows a tense posed gesture, not the start of speech or a larger hand action. During the clip, she maintains the same expression and hand pose while completing one small natural blink. By the final frames, her eyes have returned to the same direct gaze and her face and hands are steady in their original positions.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nOnly subtle natural breathing is visible in her shoulders. Natural lighting and colors, realistic physics, coherent facial and hand anatomy, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "Speaking, opening the mouth wider, exaggerated expression, large head turn, hands moving toward or away from the face, changed identity or facial proportions, asymmetric eyes, altered gaze, deformed hands, extra or missing fingers, fused fingers, changed hand pose, changed hairstyle, invented wind, altered striped clothing, automatic reframing, invented off-frame anatomy, camera drift or orbit, crop, zoom, shake, flicker, morphing, duplication, disappearing features, motion artifacts, unfinished action, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.2/02.prompt.json",
        "prompt_sha256": "aa5f85555d4b9780fd032132dfb9cd2e670acf4bcfd0fc984404fb5fdaa0058f",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.2/02.run.json",
        "run_sha256": "3a1c89e8e280ff97853fd3183d87b5a15f79cf8ca4a41bc4b7fd8d5855045dbe",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "96d382506c8b82c695f5a8c8af2f6a739bd43c7694a0d3ef28aca7e7ff0c0e27"
    },
    {
      "id": "promopages-9856-classic-01-portrait-hands-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "n1LUAicYzuuf8XAXJjHd",
        "request_sha256": "19cf3f4274e4cc4634d90f08827fd9ea3cfa75315457c3c992bd4f9b43d864c0",
        "submitted_at": "2026-07-21T15:05:24Z",
        "completed_at": "2026-07-21T15:06:50Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-01-portrait-hands-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.7/02.mp4",
        "sha256": "7d64f7fe1c8cb179afd8adc54d2757c4f8b10abebbaf8cd8112fd767294a0a9d",
        "bytes": 3006757,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the centered tight close-up of a woman looking directly at the camera with wide blue-gray eyes, a clenched-teeth grimace, brown hair in a bun, and both splayed hands raised beside her cheeks. Preserve her exact identity, facial proportions, eye color and gaze, hairstyle, navy-and-white striped top, the anatomy and original positions of every visible finger, the softly blurred indoor background, lighting, crop, composition, and aspect ratio.\n\nThe first frame already shows a tense posed gesture, not the start of speech or a larger hand action. During the clip, she maintains the same expression and hand pose while completing one small natural blink. By the final frames, her eyes have returned to the same direct gaze and her face and hands are steady in their original positions.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nOnly subtle natural breathing is visible in her shoulders. Natural lighting and colors, realistic physics, coherent facial and hand anatomy, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "Speaking, opening the mouth wider, exaggerated expression, large head turn, hands moving toward or away from the face, changed identity or facial proportions, asymmetric eyes, altered gaze, deformed hands, extra or missing fingers, fused fingers, changed hand pose, changed hairstyle, invented wind, altered striped clothing, automatic reframing, invented off-frame anatomy, camera drift or orbit, crop, zoom, shake, flicker, morphing, duplication, disappearing features, motion artifacts, unfinished action, cartoon or CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": false,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.7/02.prompt.json",
        "prompt_sha256": "ab02b7262225fb13eff47bf24afa4a8c1904aaf8703a9752096e9a6b34c660ec",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/wan-2.7/02.run.json",
        "run_sha256": "dd4f4c11b8cdf795dd47a63484c1ca04ec899cbf89c292e8ed3ec0f784f6d256",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "10df660022fcc4e3dbc018cf614248a02278cee4c4a7e86fb86d1635638faab8"
    },
    {
      "id": "promopages-9856-classic-01-portrait-hands-veo-3.1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "iepxtvK1v71kREk2FWEg",
        "request_sha256": "9ef6b8c28cb7540920ea3f7a7a5371010428a0933b6db0bd594fd475ba94ce6f",
        "submitted_at": "2026-07-21T15:06:54Z",
        "completed_at": "2026-07-21T15:08:42Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-01-portrait-hands-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/veo-3.1-lite/02.mp4",
        "sha256": "e4d73aecccd7b5fcb237278fecbe619e2d98ba2e2e2834a76b398dc4ad6ab740",
        "bytes": 3532544,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the centered tight close-up of a woman looking directly at the camera with wide blue-gray eyes, a clenched-teeth grimace, brown hair in a bun, and both splayed hands raised beside her cheeks. Preserve her exact identity, facial proportions, eye color and gaze, hairstyle, navy-and-white striped top, the anatomy and original positions of every visible finger, the softly blurred indoor background, lighting, crop, composition, and aspect ratio.\n\nThe first frame already shows a tense posed gesture, not the start of speech or a larger hand action. During the clip, she maintains the same expression and hand pose while completing one small natural blink. By the final frames, her eyes have returned to the same direct gaze and her face and hands are steady in their original positions.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nOnly subtle natural breathing is visible in her shoulders. Natural lighting and colors, realistic physics, coherent facial and hand anatomy, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "Speaking, opening the mouth wider, exaggerated expression, large head turn, hands moving toward or away from the face, changed identity or facial proportions, asymmetric eyes, altered gaze, deformed hands, extra or missing fingers, fused fingers, changed hand pose, changed hairstyle, invented wind, altered striped clothing, automatic reframing, invented off-frame anatomy, camera drift or orbit, crop, zoom, shake, flicker, morphing, duplication, disappearing features, motion artifacts, unfinished action, cartoon or CGI look",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": "alibaba/wan-2.2",
        "native_for_generation_model": false,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/veo-3.1-lite/02.prompt.json",
        "prompt_sha256": "5c1fe4fc2f4fbcbe1df33381b82b5076e0f0a095a22671e408acb0621a3a2edf",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/veo-3.1-lite/02.run.json",
        "run_sha256": "8418f2e3c88cdf6abcae51a796ce740d49fa18147134275c8f5a575b3074e210",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "e5d3e2e254fac5e83f2c0e9a13a63d0574fa20ce207ac3533e399770e43e44e0"
    },
    {
      "id": "promopages-9856-classic-02-product-dropper-wan-2.2",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "3c891e6ad66442f79c773505edbbca5a",
        "request_sha256": "c1d56e509c0a51f4913d5c68fd9f8925d8b1ca9c5e2509e99f39c8b98221480a",
        "submitted_at": "2026-07-21T11:54:13Z",
        "completed_at": "2026-07-21T11:55:50Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-02-product-dropper-wan-2.2",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.2/05.mp4",
        "sha256": "94abef9f9cf1c450dc4472018a5bb282c72b177ec6c7dac3ba51616c7bb896e4",
        "bytes": 183773,
        "duration_seconds": 3.233,
        "width": 1200,
        "height": 736,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the serum bottle standing beside one whole and one cut truffle, with the open gold-capped glass pipette angled above it and one clear serum drop suspended from the tip. Preserve the bottle silhouette, open neck and threads, pipette angle, gold cap, liquid level and color, both truffles, exact readable label and branding, transparent materials, reflections, shadows, original crop, composition, and aspect ratio.\n\nThe first frame already shows one hanging serum drop. During the clip, that drop makes one tiny surface-tension quiver, elongating only slightly without detaching. By the final frames, it has settled into the same stable rounded pendant shape while every product element remains fixed.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nNatural studio lighting and colors, realistic liquid physics, coherent glass and object geometry, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "Drop detaching or falling, new drops, dripping, splashing, changing liquid volume, product rotation, product transformation, opening or moving the bottle, moving pipette, changed item count, floating objects, changed or unreadable label, misspelled or warped letters, replaced branding, warped bottle threads or pipette, opaque glass, melted transparency, inconsistent refraction, changing material or shadow contact, camera drift, zoom, orbit, reframing, crop, shake, flicker, morphing, duplication, disappearing objects, motion artifacts, unfinished motion, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.2/05.prompt.json",
        "prompt_sha256": "23946c697c9b8f260485ab4295fa6c0811c82734004cde1789e380b785a96416",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.2/05.run.json",
        "run_sha256": "6e01a45d184acda625aa31746057cb1407fdc4ec4b7b86d6dbb60b686f065617",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "e1517281b359f3441e5cfe245f1686d251e6da46f6fc45bc6bbcba66684e7b3b"
    },
    {
      "id": "promopages-9856-classic-02-product-dropper-wan-2.7",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "zFq2VtCdsmBIUJOyfgEP",
        "request_sha256": "532abfa3ccd52c1ea3f4b94d895e502f20c0f1c2679df3818076b9baf253bd4f",
        "submitted_at": "2026-07-21T14:04:17Z",
        "completed_at": "2026-07-21T14:06:04Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-02-product-dropper-wan-2.7",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.7/05.mp4",
        "sha256": "5feef365eb5f77c12585c386d0f5ee665f6c77c22cab73afe4a586e6654bab9d",
        "bytes": 1006014,
        "duration_seconds": 3.0,
        "width": 1820,
        "height": 1138,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided product still life. Preserve the bottle, angled pipette, one compact solid serum drop attached to its tip, two truffle pieces, readable label, glass transparency, reflections, shadows, crop and aspect ratio.\n\nMotion begins immediately at normal real-time speed. The attached drop makes one tiny surface-tension quiver: its lower edge shifts by only a few millimeters and rebounds once, without stretching into a thread. Within the first second it returns to the same compact solid rounded pendant shape, still attached to the pipette. Hold that unchanged state for the rest of the shot. The bottle, pipette and truffles remain completely fixed.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nGenerate single shot. Natural studio lighting, realistic surface tension, coherent glass and product geometry, stable lettering, smooth temporal consistency, photorealistic motion.",
        "negative": "slow motion, delayed quiver, long drop, stretched neck, liquid thread, hollow loop or ring, drop detachment, falling or extra drops, contact with truffle or shelf, dripping, splash, changing liquid volume, pipette or bottle motion, product rotation, warped label or glass, opaque glass, altered reflection, camera movement, zoom, crop, flicker, morphing, duplication",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.7/05.prompt.json",
        "prompt_sha256": "87e1719d773dcf5291163dd735dea5e4eb190de9e7e4096c95b533e7aa53276e",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/wan-2.7/05.run.json",
        "run_sha256": "b716a6c072c8f1372e2d18faad5bf14b7d1fb68b89bb8bdd06c0b5e6079fce33",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "e13078d33938150ea9174419932878a81db66b79f248f4c76b4ea98017ed071b"
    },
    {
      "id": "promopages-9856-classic-02-product-dropper-veo-3.1-lite",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "sjdNf5VIBRwW1mfKiwTN",
        "request_sha256": "92eb3271909d52e4d3ec1ba5c566bef05456e00a1c4ccec4311ea1b4bf0f2792",
        "submitted_at": "2026-07-21T14:06:07Z",
        "completed_at": "2026-07-21T14:07:23Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-02-product-dropper-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/veo-3.1-lite/05.mp4",
        "sha256": "7639d2bb59c3c43bd6d882377d433a88c076078d4c4b19e3c9d12b2b6be959e2",
        "bytes": 1035260,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Motion begins immediately at normal real-time speed. The existing compact solid serum drop stays attached to the pipette and makes one tiny surface-tension quiver: its lower edge shifts by only a few millimeters and rebounds once, without stretching into a thread. Within the first second it returns to the same compact rounded pendant shape. Hold that unchanged state for the rest of the shot. The bottle, pipette and truffles remain fixed; preserve the readable label, glass transparency, reflections, shadows, crop and composition. Keep the camera locked with no reframing. Realistic surface tension, stable product geometry and lettering, smooth temporal consistency, photorealistic motion.",
        "negative": "slow-motion pacing, delayed quiver, long drop, stretched neck, liquid thread, hollow loop or ring, drop detachment, falling or extra droplets, contact with truffle or shelf, pouring, splash, changed liquid volume, pipette or bottle motion, product rotation, warped label or glass, opaque glass, altered reflections, camera movement, reframing, flicker, morphing, duplicated objects",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/veo-3.1-lite/05.prompt.json",
        "prompt_sha256": "8c7e1b236b110715ae5bc02090313f7ff18fb3a3579b651d8bd335a74d34c075",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/video/veo-3.1-lite/05.run.json",
        "run_sha256": "4b12045139a5d42a3b665e8a399ce91a7c2769d348e0bc20cc6cd4fe6cbc368c",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "4dc81535beaceefc711f91e6f642cbd1d0713b1515b5bfe33a3f65f7b242b2ea"
    },
    {
      "id": "promopages-9856-classic-03-animal-step-wan-2.2",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "fd17f2a9e20743e5a64905a5448a00c4",
        "request_sha256": "360c243e1cc46175e68c044439735312f5e11432d572cf1b804b4fd814f47eb4",
        "submitted_at": "2026-07-21T11:55:50Z",
        "completed_at": "2026-07-21T11:57:27Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-03-animal-step-wan-2.2",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.2/03.mp4",
        "sha256": "684ae9fd9968e03eb8ce959ac3cd4bd09bb5bc2395dd09779045ad35defe56a2",
        "bytes": 378836,
        "duration_seconds": 3.233,
        "width": 1408,
        "height": 624,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the gray tabby cat halfway out of the pale green litter box, with one forepaw planted on the wooden floor, the other forepaw lifted above the box edge, and its head facing frame right. Preserve the cat’s species, tabby coat pattern, white chest and paws, face, eyes, ears, whiskers, visible limb count and occlusions, the litter box, surrounding furniture and plant, the original composition and aspect ratio.\n\nThe first frame already shows the final phase of one careful step out of the litter box. During the clip, the cat gently lowers the raised forepaw onto the wooden floor and makes one small forward weight shift without taking another step. By the final frames, both visible forepaws are settled, the body remains partly over the litter box, and the cat pauses while looking toward frame right.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nOnly subtle natural breathing and slight whisker and fur settling accompany the weight shift. Natural lighting and colors, realistic physics, coherent animal anatomy and object geometry, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "continued walking, extra steps, jumping, leaving frame, reversing direction, large body movement, large head turn, changed species or coat pattern, altered face, eyes, ears or whiskers, extra or missing limbs, warped paws or legs, invented hidden hind limbs or tail, broken ground contact, changed litter-box contact, transformed litter box, moving furniture or plant, camera drift, orbit or reframing, flicker, morphing, duplication, disappearing objects, unfinished action, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.2/03.prompt.json",
        "prompt_sha256": "56d14fb7e685244e2624fabfee4ebe95b180429377c38e29ff137c23ba342ffa",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.2/03.run.json",
        "run_sha256": "6e0e1dd670157c9b058d6dca052ec7a0f1dd8c6ac86f1054b67df931da8935e7",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "e3287c23852f9a27616e9db952709dda3acfbd2327e53b9f07a474e7d64b1853"
    },
    {
      "id": "promopages-9856-classic-03-animal-step-wan-2.7",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "RhB0kpCTWRCNubYIdeIq",
        "request_sha256": "e2634fb834392d409480febb7545a5089ebf441c1db8ae90bf5a5c601fba5c59",
        "submitted_at": "2026-07-21T13:52:40Z",
        "completed_at": "2026-07-21T13:53:48Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-03-animal-step-wan-2.7",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.7/03.mp4",
        "sha256": "56f4390ae98c46b4e73a05099ea1cc3939fa9679e37c1bc72c490cadf623c666",
        "bytes": 2341811,
        "duration_seconds": 3.0,
        "width": 2146,
        "height": 966,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the gray tabby-and-white cat halfway out of the pale green litter box, facing frame right, with one front paw planted on the wooden floor and the other suspended mid-step. Preserve the coat pattern, face, eyes, ears, whiskers, visible limb count and overlaps, paw contacts, litter-box geometry, room, crop and aspect ratio.\n\nMotion begins immediately at normal real-time feline stepping speed. The raised front paw travels downward and slightly forward; its pads contact the wooden floor within the first second. The shoulder and chest follow the paw as one natural forward weight transfer completes by 1.8 seconds. No second step begins. The cat then pauses with both front paws grounded, its body still partly supported by the litter box and its gaze toward frame right.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nGenerate single shot. Realistic weight, momentum and ground contact, coherent feline anatomy, stable fur detail, smooth temporal consistency, photorealistic motion.",
        "negative": "slow motion, time-stretched or delayed paw landing, prolonged easing, second step, continued walking, jumping, leaving frame, reversing direction, large head turn, changed coat pattern or face, invented hidden limbs, extra limbs, warped paws or legs, broken ground contact, floating cat, changed litter box, pan, zoom, reframing, crop, shake, flicker, morphing, duplication, motion artifacts",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.7/03.prompt.json",
        "prompt_sha256": "ec5363cc3a647ac04d2ea9543ce44925e57b709893db669a10763488ce252541",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/wan-2.7/03.run.json",
        "run_sha256": "4c311aca19ae9b80268f81d248c3023ef0b7d3a91caa7305133c369232e4d33d",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "7d7f5542d532bf824eb5e12bdfb9c0a261d09cd536c0e9092d4ecec4e8218603"
    },
    {
      "id": "promopages-9856-classic-03-animal-step-veo-3.1-lite",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "bJBqOgbf1pIDTW99nFzV",
        "request_sha256": "ed1512d2bf1999360745dea4b4829e37a6cbf4ceee4d260039c957298c777f1d",
        "submitted_at": "2026-07-21T13:29:05Z",
        "completed_at": "2026-07-21T13:30:55Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-03-animal-step-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/veo-3.1-lite/03.mp4",
        "sha256": "8258a297d237b8d7ef915620d8195044d41ba6e0ceedec8851164953f2940afa",
        "bytes": 3625688,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Motion begins immediately at normal real-time feline stepping speed. The cat’s raised front paw moves downward and slightly forward, and its pads contact the wooden floor within the first second. The shoulder and chest follow with one natural forward weight transfer completed by 1.8 seconds. No second step begins. The cat then pauses with both front paws grounded, its body still partly supported by the litter tray and its gaze toward frame right. Preserve the coat pattern, face, whiskers, visible limb count and overlaps, tray geometry, background, crop and composition. Keep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing. Realistic momentum and ground contact, coherent feline anatomy, stable fur detail, smooth temporal consistency, photorealistic motion.",
        "negative": "slow-motion pacing, time-stretched paw landing, delayed action, prolonged easing, second step, continued walking, jumping, turning around, cat leaving frame, changed direction, changed coat pattern, invented hidden limbs, extra limbs, duplicated paws, warped legs, unnatural gait, broken paw-floor contact, changed tray shape, moving background, camera drift, zoom, reframing, shake, flicker, morphing, motion smear",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/veo-3.1-lite/03.prompt.json",
        "prompt_sha256": "d7501b810804b48762d02d9dac76e7812440c723dc82731f3cb383dd03c210ac",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/video/veo-3.1-lite/03.run.json",
        "run_sha256": "29eb9904ebbf931768aee9fb5b423a4de03e0a7fd0badcc2eadd26deecd1002d",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "4ea308710efb395798a35b8736f08f8c1c36b4e25a1227396f77074435cfa9e0"
    },
    {
      "id": "promopages-9856-classic-04-interior-water-wan-2.2",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "f60d84b4966c4ffb9d47e4dfa5f295be",
        "request_sha256": "109a7fe7bebe377308b3d2e26d52db68e059ed73f1a6e3bf86eace6280618ca8",
        "submitted_at": "2026-07-21T11:57:28Z",
        "completed_at": "2026-07-21T11:59:06Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-04-interior-water-wan-2.2",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.2/09.mp4",
        "sha256": "c5206a40992a36df6d490b75f1b2291245c4c89dc74637176c21d26f9ff3374c",
        "bytes": 454575,
        "duration_seconds": 3.233,
        "width": 1264,
        "height": 704,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided frame. Start exactly from the frontal luxury pool interior with the vertical water curtain already falling into the turquoise tiled pool. Preserve the straight travertine walls, vertical living wall, round cream chaise and pillows, pool dimensions, water level, reflections, lighting, original composition and aspect ratio.\n\nThe first frame already shows a steady indoor cascade. During the clip, the falling water continues smoothly as one soft ripple spreads from the impact point and gradually dissipates. By the final frames, the pool surface is gently settled beneath the unchanged cascade.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nAllow only subtle, physically coherent shimmer in the visible water and its reflections. Natural lighting and colors, realistic fluid physics, exact architectural geometry, smooth temporal consistency, stable fine details, photorealistic motion.",
        "negative": "moving furniture, opening doors or drawers, added windows, changing room layout, warped walls or pool edges, drifting verticals, changing water level, uncontrolled splashing, impossible flow, invented waves, detached or incoherent reflections, changing shadow direction, moving foliage, crop, reframing, camera motion, shake, flicker, morphing, duplication, disappearing objects, motion artifacts, unfinished action, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.2/09.prompt.json",
        "prompt_sha256": "e58067816a4855118ced6837c054bbdf93f5d319c9d62cc051e00aed9dd45d87",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.2/09.run.json",
        "run_sha256": "60c5efb6dbd0968d2fc7387471704cf768a697a8406246a8735b8ccc5dceee28",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "27a17df9c15554d827ed14942ae37b01cf4e9558b428dcc9c34494d981b3c016"
    },
    {
      "id": "promopages-9856-classic-04-interior-water-wan-2.7",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "9sDAd05X3ZwXPZtYuEgK",
        "request_sha256": "a35a07a31c346298074ff75155fff6a5c8fbfaf2df4abb149c965e6c39fa8e37",
        "submitted_at": "2026-07-21T13:59:54Z",
        "completed_at": "2026-07-21T14:01:10Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-04-interior-water-wan-2.7",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.7/09.mp4",
        "sha256": "282787b7bcc293d2247ed5d407cca027ea0046924ab7964d41558ce057e39c69",
        "bytes": 7827013,
        "duration_seconds": 3.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic image-to-video continuation of the provided pool interior. Preserve the exact stone panels, vertical living wall, turquoise tile grid, water level, daybed and cushions, lighting, reflections, crop and aspect ratio.\n\nMotion begins immediately at normal real-time speed under normal gravity. The existing waterfall remains a continuous downward sheet. Its impact produces one narrow ripple immediately; the ripple travels outward across the nearby pool, loses amplitude and completes its readable spread by 2 seconds. The waterfall continues at the same rate while the surrounding surface holds a low natural disturbance for the rest of the shot. Underwater reflections respond synchronously to the moving water.\n\nKeep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing.\n\nGenerate single shot. Realistic gravity, fluid momentum and light reflection, exact architectural geometry, smooth temporal consistency, photorealistic motion.",
        "negative": "slow motion, time-stretched water, delayed ripple, waterfall stopping, surging or reversing, invented splashes, large waves, changing water level, moving furniture, changed room layout, warped stone panels, drifting verticals, altered tile grid, incoherent or delayed reflections, moving foliage, new light source, camera movement, zoom, reframing, crop, shake, flicker, morphing, duplication",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.7/09.prompt.json",
        "prompt_sha256": "bd4a2b2a296a17bb34865de03ed3da7afe18fcfaf49b12cabb50b2610ea553cb",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/wan-2.7/09.run.json",
        "run_sha256": "26114f6bc7de537ee85e3d5d7447287a8cf9aa7b26ffe756d99b98814f2b0331",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "41cfd0be33764f8d3ec2ffb13e66dee8858593cc9272d7879787db49c414031d"
    },
    {
      "id": "promopages-9856-classic-04-interior-water-veo-3.1-lite",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "gZnwvMoKmXFOXR0DYsdP",
        "request_sha256": "7399bdd1b0115282302c24ad01ffea9ba210ce786e779043da9829ec82a95fcb",
        "submitted_at": "2026-07-21T13:30:59Z",
        "completed_at": "2026-07-21T13:33:33Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-04-interior-water-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/veo-3.1-lite/09.mp4",
        "sha256": "4f48a160dea4b62e1d885f78c958b32442b933143c664365ba824fc3864c6030",
        "bytes": 14732524,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Motion begins immediately at normal real-time speed under normal gravity. The existing waterfall remains a continuous downward sheet. Its impact produces one narrow ripple immediately; the ripple travels outward across the nearby pool and loses amplitude after completing its readable spread by 2 seconds. The waterfall continues at the same rate for the rest of the shot, and underwater reflections respond synchronously to the water. Preserve the water level, turquoise tile grid, straight stone panels, vertical living wall, daybed and cushions, lighting, crop and composition. Keep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing. Realistic fluid momentum and reflections, exact architectural geometry, smooth temporal consistency, photorealistic motion.",
        "negative": "slow-motion water, time-stretched flow, delayed ripple, waterfall stopping, surging or reversing, invented splashes, large waves, changing water level, moving furniture, changed room layout, warped stone panels, bent verticals, altered tile grid, changing foliage, incoherent or delayed reflections, new light sources, camera movement, reframing, shake, flicker, morphing",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/veo-3.1-lite/09.prompt.json",
        "prompt_sha256": "eca671bf8dbc379757afc45afbf38aa27c6e4ba3bd2a5490ef21884c9c434999",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/video/veo-3.1-lite/09.run.json",
        "run_sha256": "70de0ecdbc9364b0a8599368ace733c05474031461889576627e7e6237f35373",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "b0690adeb28b81138023d9504fef7458cae62327d9b3636e02fdfd4941a9a5de"
    },
    {
      "id": "promopages-9856-classic-05-finance-ui-wan-2.2",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "1087e066c82648d081668c068404e391",
        "request_sha256": "f44326aacadc159a7e758baf48a32f913867fdd1b1c52ed699db992785430b0b",
        "submitted_at": "2026-07-21T11:59:06Z",
        "completed_at": "2026-07-21T12:00:44Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-05-finance-ui-wan-2.2",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.2/04.mp4",
        "sha256": "769c53ba4aa70c05d4b5d5abc3dee1dddd942a74c84b8c5cbb3cd02b5851301d",
        "bytes": 291772,
        "duration_seconds": 3.233,
        "width": 1216,
        "height": 720,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A faithful image-to-video continuation of the provided flat raster financial interface. Start exactly from the complete first frame. Preserve all readable Cyrillic text, the “Финансовый потенциал” header, every number and currency symbol, the 15.8% circular chart, the loan and income values, both selected credit-card rows, their amounts and dates, the blue checkboxes, icons, spacing, alignment and panel geometry in exact visual registration, together with the original layout, crop and aspect ratio. The content and state already shown remain unchanged. During the clip, hold the entire interface and chart completely steady without control activation, data animation or content change. By the final frames, the same UI state and chart geometry remain fully settled and stable. Keep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing. Maintain crisp stable typography, unchanged values, exact circular-chart geometry, clean edges and smooth temporal consistency.",
        "negative": "scrolling, clicking, typing, hover changes, changed UI state, invented controls, moving cards, chart fill animation, rescaled chart, redrawn ring segments, chart rebuild, rewritten or unreadable text, altered numbers, changed selection, missing icons, warped layout, zoom, pan, reframing, crop, flicker, morphing, duplicated elements, motion artifacts",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.2/04.prompt.json",
        "prompt_sha256": "f1b5437886f378115edeebe5cc49a9d04e117c95c678396839b37566af6ccffc",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.2/04.run.json",
        "run_sha256": "b3f47cbe4f14054cad1d9e2c9a1a796dd665c12ffa6c839485235f1151cc20ca",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "5eefb9342676d8682f964463e0cfe052802d936f6db5ca9d9c0af505d6cebc81"
    },
    {
      "id": "promopages-9856-classic-05-finance-ui-wan-2.7",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "jWDK6PPJStTctLG8UORH",
        "request_sha256": "0a7a16d6e873db3bcc40f7cfc071af10a0d252106e253926a6c35387665a7e2a",
        "submitted_at": "2026-07-21T14:01:12Z",
        "completed_at": "2026-07-21T14:02:24Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-05-finance-ui-wan-2.7",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.7/04.mp4",
        "sha256": "41e39c27e757baa02de651680860bbd60918c8d3ff5ca5fca30ce6a1ceedd75e",
        "bytes": 865049,
        "duration_seconds": 3.0,
        "width": 1858,
        "height": 1116,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Treat the provided frame as one static flat-raster screenshot, not a live interface. Hold the complete financial screen unchanged from the first frame through the final frame. Preserve every Russian glyph, ruble amount, date, percentage, checked state, icon, credit-card row, ring-chart arc, spacing, panel boundary, crop and aspect ratio in the same visual registration. No interaction, data animation, chart fill, recomputation or content change occurs. Keep the camera locked and the original composition stable. Preserve the full main subject and all key scene elements in frame. No zoom, orbit, pan, tilt or reframing. Use crisp stable typography, unchanged values, exact chart geometry, clean edges and smooth temporal consistency. Generate single shot.",
        "negative": "interface interaction or data animation, scrolling, clicking, typing, hover changes, changed UI state, invented controls, altered values, moving cards, changed chart values, redrawn chart ring, moving chart segment, altered chart label, rewritten or unreadable Russian text, warped numbers or currency symbols, moving panels, local parallax, zoom, pan, reframing, crop, flicker, morphing, unstable edges",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.7/04.prompt.json",
        "prompt_sha256": "4c8f6b618f85e54a19921e44e1d6bd16a8db3ab27945e7c016500474e5af8449",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/wan-2.7/04.run.json",
        "run_sha256": "3533e4c083e68b2f1c933ddfe33d589de5764c5455c3fb65a7e5b54c7a0ab59e",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "86385349bd1aa610a265b16243d3c767b29fa77e4bec77b9b25c9c56e7c757a0"
    },
    {
      "id": "promopages-9856-classic-05-finance-ui-veo-3.1-lite",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2
      },
      "approach": {
        "id": "clipmaker-classic-main",
        "label": "Classic · основной подход"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "G2HTsf7C82us95hPvzEA",
        "request_sha256": "39d6977046121609ff4aca5b2688ba8b1d89a5d1fa5f4f5da60438e0bf590eb0",
        "submitted_at": "2026-07-21T14:08:58Z",
        "completed_at": "2026-07-21T14:10:13Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-05-finance-ui-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/veo-3.1-lite/04.mp4",
        "sha256": "bd596d665029a137123600f421ca9d0c9e7e013ed077be28aeabd511638c02d9",
        "bytes": 666420,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "The provided first and last frames are intentionally identical. Treat them as one static flat-raster screenshot, not a live interface, and keep every intermediate frame identical too. Hold the complete financial screen unchanged from first through last frame. Preserve every Russian glyph, monetary value, date, percentage, checked state, icon, credit-card row, donut-chart arc, spacing, panel boundary, crop and aspect ratio in the same visual registration. No interaction, data animation, chart fill, recomputation or content change occurs. Keep the camera locked with no reframing. Crisp stable typography, unchanged values, exact chart geometry, clean edges and smooth temporal consistency.",
        "negative": "scrolling, clicking, typing, hover changes, changed UI state, invented controls, altered monetary values, moving cards, changed chart values, redrawn donut series, chart rebuild, rewritten or unreadable Russian text, warped glyphs, changed dates, moving checkboxes, reframing, zoom, pan, flicker, morphing, blurred edges, motion artifacts",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": null,
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/veo-3.1-lite/04.prompt.json",
        "prompt_sha256": "cef15bf7a79ba703293162f6fdcfeac9a7aae684a3140f626cc956bd1d5ad9fc",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/video/veo-3.1-lite/04.run.json",
        "run_sha256": "982677ab811872ef22034ced6a3b13e1090d79fe29b54e4c0d7efff679c7eb3c",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "9b6593c327d2fdf6daca29f8f56d7146c669329d705d54206500df4920c860bb"
    },
    {
      "id": "promopages-9856-classic-portrait-angry-outburst-v1-wan-2.2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-angry-outburst-v1",
        "label": "Classic · portrait-angry-outburst-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": null,
        "request_sha256": "95722fd7f4f182c6c2403f25740cfcb42aec49cd6f138f7f29f248b22aaf3040",
        "submitted_at": null,
        "completed_at": "2026-07-22T11:28:06Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-angry-outburst-v1-wan-2.2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.2/02.mp4",
        "sha256": "356138ec4083dfa8b1b959ff1ce40c36b4d4e6bafb66a022e706a535af88016d",
        "bytes": 473320,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "A photorealistic continuation of the exact first frame. The woman immediately performs one continuous angry, frustrated outburst: she visibly shouts while rapidly shaking both raised claw-like hands in small synchronized motions within their original areas beside her face. Her motion is energetic, expressive, and natural. She finishes still visibly angry and frustrated, with both hands raised and the same emotional intensity, never smiling or calming down. Preserve her identity, striped clothing, background, lighting, composition, crop, and aspect ratio. Keep the camera completely locked with no reframing.",
        "negative": "smiling, friendliness, calming down, emotional softening or reversal, passive or nearly static performance, closed-mouth reaction, unrelated second action, hands lowering or leaving their original areas, hands crossing or touching the face, asymmetric hand motion, changed finger pose, extra or fused fingers, face or hand deformation, identity or clothing change, background change, cuts, scene change, camera movement, reframing, crop, shake, flicker, morphing, duplication, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": {
        "id": "portrait-angry-outburst-v1",
        "objective": "Apply model-specific I2V prompting to produce one continuous energetic angry outburst while preserving the original composition and the same angry or frustrated emotional sign through the final frame.",
        "prompt_strategy": "model_specific",
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.2/02.prompt.json",
        "prompt_sha256": "f14447639c0d77ab20f1ee5ce8bb05d9f9a6bcdff8eb853ee7f3e8bc4b81d653",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.2/02.run.json",
        "run_sha256": "76ec823bf1576e60b3ffd318860181dc6c93ca19528a6f9a5199b0e72352a3fe",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "27c49b8a407c6f9ba1a81633509c7118123e0ad539eb8cbf1c4f09474ae1d985"
    },
    {
      "id": "promopages-9856-classic-portrait-angry-outburst-v1-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-angry-outburst-v1",
        "label": "Classic · portrait-angry-outburst-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "4pdDjJkXfQdDcQ3wIQ52",
        "request_sha256": "e5f9ac28faff021ccda0e11d3436dae19d6110ae19e43bc1a5cdb27ccd79b1f5",
        "submitted_at": "2026-07-22T11:27:09Z",
        "completed_at": "2026-07-22T11:28:35Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-angry-outburst-v1-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.7/02.mp4",
        "sha256": "3bc02fa241f985e4165a12c62379cb13a446123a45c70326b12ca820b4d522d7",
        "bytes": 3338784,
        "duration_seconds": 3.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Generate a single-shot video. Continue directly from the provided frame. Preserve the same woman, wide-eyed tense expression, raised brows, teeth-baring mouth, hairstyle, striped top, both raised claw-like hands, lighting, background, crop and aspect ratio. Motion starts immediately at normal real-time speed. She performs one sustained angry, frustrated outburst: she visibly yells while both hands shake simultaneously in fast, tight side-to-side wrist and forearm oscillations, staying within their original left and right areas beside her face. Her eyes and brows retain the same angry emotional sign, her fingers retain their claw curvature, and the hands never lower, cross or leave their areas. The synchronized shout and hand shaking form one causal action that peaks and completes by about 1.8 seconds. She finishes with both hands still raised and her face equally angry and frustrated, with no smile, friendliness, softening or calming. Hold that tense final state for the remaining frames. Keep the camera locked and the original composition stable. No zoom, orbit, pan, tilt or reframing. Natural expressive mechanics, coherent mouth and hand anatomy, stable identity and background, smooth temporal consistency, photorealistic motion.",
        "negative": "weak or nearly static motion, smile, friendliness, emotional softening, calming down, emotional reversal, laughter, hands lowering or leaving their original areas, unsynchronized hand motion, large arm swings, changed claw-like hand pose, deformed hands, extra fingers, head turn, camera motion, zoom, pan, tilt, reframing, crop change, cuts, second scene, slow motion, time-stretched action, flicker, morphing, identity change, motion artifacts, CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-angry-outburst-v1",
        "objective": "Apply model-specific I2V prompting to produce one continuous energetic angry outburst while preserving the original composition and the same angry or frustrated emotional sign through the final frame.",
        "prompt_strategy": "model_specific",
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.7/02.prompt.json",
        "prompt_sha256": "f823bfb673d57c670afc08166d4d2ab5842f111ea38bad6787ebd3a1bd646787",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/wan-2.7/02.run.json",
        "run_sha256": "62d79e35ffbd4c052f0aca6a874537fac852242a69d9c96675006de347d8395d",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "ee8c048c4022e23f21215354fb82710964e688c908d4471d8a9d6a223318c612"
    },
    {
      "id": "promopages-9856-classic-portrait-angry-outburst-v1-veo-3.1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-angry-outburst-v1",
        "label": "Classic · portrait-angry-outburst-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "Gid34U5cYkHChrHdieaS",
        "request_sha256": "aa0113d82fe2fba8e65f3ee36c9655344abe01994ac57d1b693c0f3de242da6b",
        "submitted_at": "2026-07-22T11:27:30Z",
        "completed_at": "2026-07-22T11:29:19Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-angry-outburst-v1-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/veo-3.1-lite/02.mp4",
        "sha256": "e447fbc2c1869ba59b4a71bbc2677380c34dce6ea8849c65eed8351ad7b69984",
        "bytes": 3606635,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Locked-off tripod close-up using the input image as the exact opening composition. Keep the camera, crop, background, focus and lighting fixed. Preserve the same woman's identity, tied-up hair, striped top and both raised claw-like hands. She immediately performs one sustained angry, frustrated outburst at natural real-time speed. She visibly yells one forceful continuous exclamation while both raised hands shake rapidly and synchronously in short, tight side-to-side pulses inside their original left and right areas. Her eyes remain wide, her brows remain tense, her jaw and lips articulate the shout naturally, and every finger keeps its claw-like spread. Her face, shoulders and hands move as one causally synchronized performance without a separate gesture or second beat. The outburst finishes by about 2.0 seconds with both hands still raised and her expression equally angry, frustrated and tense. Hold that tense final state through the final frame, never smiling, softening or calming. Photorealistic motion, coherent facial and hand anatomy, stable identity and background, smooth temporal consistency.",
        "negative": "smile, friendliness, cheerful expression, emotional softening or reversal, calming down, laughter, weak or nearly static performance, delayed action, slow-motion pacing, disconnected or alternating hand motion, large arm swings, lowered hands, hands leaving their original areas, changed claw-like pose, closed fists, deformed or duplicated hands, extra or fused fingers, identity drift, warped mouth or teeth, large head turn, body lunge, camera drift, zoom, orbit, pan, tilt, reframing, abrupt cuts, scene change, background motion, flicker, morphing, smeared motion, cartoon or CGI look",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-angry-outburst-v1",
        "objective": "Apply model-specific I2V prompting to produce one continuous energetic angry outburst while preserving the original composition and the same angry or frustrated emotional sign through the final frame.",
        "prompt_strategy": "model_specific",
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/veo-3.1-lite/02.prompt.json",
        "prompt_sha256": "2c98e73f052a2c8fcedf5da8d5f64f627a5c0f76a236864575ddcd0daa7f6ba3",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-v1/veo-3.1-lite/02.run.json",
        "run_sha256": "3275d02b06c1f595837f34b4841b2ce61c912bb3a2966bba0bc57412ad939177",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "c2fd0af067361eb2fd24b20bae8a560e6ba369e9c68cbbdf474cbea27a03e338"
    },
    {
      "id": "promopages-9856-classic-portrait-angry-outburst-wan27-v2-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-angry-outburst-wan27-v2",
        "label": "Classic · portrait-angry-outburst-wan27-v2"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "ES97PCKFRYXvkvcZMEAl",
        "request_sha256": "acde01d2b47a883e027fc150e7344a79fab3ca0679d581d34f67e8fec10615de",
        "submitted_at": "2026-07-22T11:31:04Z",
        "completed_at": "2026-07-22T11:34:36Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-angry-outburst-wan27-v2-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-v2/wan-2.7/02.mp4",
        "sha256": "db8d104fe6117be5ae350327a02117745f3bcb28eec21903fc3a2be8129f077e",
        "bytes": 3498114,
        "duration_seconds": 3.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Generate a single-shot video. Use the provided image as the exact opening frame and keep a locked close-up. Motion starts immediately at normal real-time speed. The woman performs one sustained angry, frustrated outburst: she visibly yells while both raised claw-like hands shake hard and fast beside her face. Both wrists snap side to side together through four tight, clearly readable oscillations; the fingertips travel several centimeters within their original left and right screen areas and show natural motion blur. Her mouth and jaw articulate the same continuous yell, her eyes stay wide and her brows stay tense. The hands never lower, cross her face or leave their original areas, and every finger keeps its claw-like spread. The shaking finishes by about 2.4 seconds with both hands still raised. Her expression remains equally angry and frustrated through the final frame, never smiling, softening or calming. Preserve her identity, hairstyle, striped top, background, lighting, crop and aspect ratio. No camera motion, zoom, pan, tilt, orbit or reframing. Coherent mouth and hand anatomy, stable identity, realistic force and timing, smooth temporal consistency, photorealistic motion.",
        "negative": "frozen hands, tiny hand twitch, weak or nearly static motion, slow hand movement, delayed action, smile, friendliness, emotional softening, calming down, emotional reversal, laughter, hands lowering or leaving their areas, alternating hand motion, large arm swings, closed fists, changed finger spread, deformed hands, extra fingers, camera motion, reframing, cuts, slow motion, time-stretched action, flicker, morphing, identity change, CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-angry-outburst-wan27-v2",
        "objective": "Target the weak-motion failure in the first Wan 2.7 angry-outburst run by specifying readable hand travel and repeated fast oscillation while preserving one locked shot and the same angry emotional sign.",
        "prompt_strategy": "model_specific",
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-v2/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-v2/wan-2.7/02.prompt.json",
        "prompt_sha256": "0b9b6ba2fc0dd028331f2e4e295750dffb1b8bfd6e7dd045b123307fb93fd802",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-v2/wan-2.7/02.run.json",
        "run_sha256": "97cc28aa23617b50081d213712f8cd5f0366c6354afb7c0467017da031b431ef",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "796e6fd01ba7464e5099938ced93a7525807b4a4d30c327eb024156abe771b05"
    },
    {
      "id": "promopages-9856-classic-portrait-angry-outburst-wan27-extend-v3-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-angry-outburst-wan27-extend-v3",
        "label": "Classic · portrait-angry-outburst-wan27-extend-v3"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "WlJQiXzWa9ujtEsunypu",
        "request_sha256": "0b64d33c295363ddb279db0ede4d7a7009ac6fe1b6fa14e7cf80427ead7b9006",
        "submitted_at": "2026-07-22T11:37:12Z",
        "completed_at": "2026-07-22T11:39:30Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-angry-outburst-wan27-extend-v3-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-extend-v3/wan-2.7/02.mp4",
        "sha256": "5ef408a6c1cbd0aac6e0f7d255b5a00c50a696962816ded9c6fba017907ea919",
        "bytes": 3146893,
        "duration_seconds": 3.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 90,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Generate a single-shot video. Locked close-up from the exact input frame. The same visibly furious woman screams continuously at normal real-time speed and vigorously shakes both raised claw-like hands beside her face in fast repeated side-to-side motions. Her hands stay inside their original left and right frame areas and her fingers remain spread. She stays furious from the first through the final frame, never smiling or calming down. Keep her identity, clothing, camera, crop, background and lighting unchanged. Energetic natural motion, realistic mouth and hands, stable anatomy, photorealistic video.",
        "negative": "smile, laughter, cheerful or friendly expression, calming down, emotional softening or reversal, frozen hands, tiny or slow hand motion, weak performance, delayed action, hands lowering, crossing the face or leaving frame, closed fists, deformed hands, extra fingers, distorted mouth or teeth, identity change, camera movement, zoom, pan, tilt, reframing, cuts, second scene, slow motion, flicker, morphing, CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "separate"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 3,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-angry-outburst-wan27-extend-v3",
        "objective": "Test a short motion-only Wan 2.7 prompt with provider prompt extension enabled after detailed controlled prompts suppressed hand motion or introduced facial drift.",
        "prompt_strategy": "model_specific",
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-extend-v3/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-extend-v3/wan-2.7/02.prompt.json",
        "prompt_sha256": "fb072406d5cbe62bf228864408485c835fdf37d543096b8b3bf081aaaf18347f",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-angry-outburst-wan27-extend-v3/wan-2.7/02.run.json",
        "run_sha256": "b829af5954494d7e9dba7057e885cc865a8a814f604aae3744a7a07f8934f374",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "f26efc64a54dc8ce70a1b451ede4eab29b43d365add287d0fee7f2bb8d1ca3c5"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-v1-wan-2.2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-v1",
        "label": "Classic · portrait-permissive-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "d78c61c15024487990d424ce406425c3",
        "request_sha256": "669f511a36f49023933a28d0c36b04788ddc967c86cd1b5f49e36e5f8ad6032a",
        "submitted_at": "2026-07-21T15:39:29Z",
        "completed_at": "2026-07-21T15:41:03Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-v1-wan-2.2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.2/02.mp4",
        "sha256": "5b2e84ee66d885ea84fa4a3ef9f0a52a740e5ec1f8220ee5f3903b9ddf83d8b4",
        "bytes": 426637,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a lively photorealistic continuation of this exact first frame. In one continuous shot, the woman has an intense spontaneous emotional reaction toward the camera. Her face, mouth, head, shoulders, and raised hands are free to move naturally and expressively; let the performance develop on its own instead of holding the initial pose. Motion starts immediately at normal real-time speed. Preserve the same person, striped clothing, setting, lighting, and framing. Keep the camera locked.",
        "negative": "identity replacement, extra limbs or fingers, severe face or hand anatomy failure, abrupt cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": {
        "id": "portrait-permissive-v1",
        "objective": "Compare useful model improvisation from the same permissive portrait prompt without prescribing a specific gesture, blink, mouth action, or final pose.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.2/02.prompt.json",
        "prompt_sha256": "3eb0c08c4d0d3adc472bfc6949495b41a3b6f4f62933c5f179abeeeeae2f63fd",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.2/02.run.json",
        "run_sha256": "81a57fd3f112b5d3674bfd693c7f50248439aa523f01fe38c11289d698d59cf6",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "5fe7eacf3ca8608f3c5459c6845ebf1ddebc114d014ae5addee72952b694661c"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-v1-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-v1",
        "label": "Classic · portrait-permissive-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "WOFJLb66CHcz6ynAr40z",
        "request_sha256": "939f22baa07bc5eb1ab60b90b64b073b1abb528a2cdb2d4d4928763e7a4f4734",
        "submitted_at": "2026-07-21T15:40:34Z",
        "completed_at": "2026-07-21T15:41:49Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-v1-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.7/02.mp4",
        "sha256": "57c2fcf844dc3cce307d59f25c94e0af09897652663eb32b1555b7f6fce6d602",
        "bytes": 5387084,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a lively photorealistic continuation of this exact first frame. In one continuous shot, the woman has an intense spontaneous emotional reaction toward the camera. Her face, mouth, head, shoulders, and raised hands are free to move naturally and expressively; let the performance develop on its own instead of holding the initial pose. Motion starts immediately at normal real-time speed. Preserve the same person, striped clothing, setting, lighting, and framing. Keep the camera locked.",
        "negative": "identity replacement, extra limbs or fingers, severe face or hand anatomy failure, abrupt cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-permissive-v1",
        "objective": "Compare useful model improvisation from the same permissive portrait prompt without prescribing a specific gesture, blink, mouth action, or final pose.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.7/02.prompt.json",
        "prompt_sha256": "9499318dca3ce9e0a87a9fa98096fd3e54abb555cb03fef94333f105e608d809",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v1/wan-2.7/02.run.json",
        "run_sha256": "e5d8d831301d1b968fd2f526ed2488e9e6fbbf6d4a433d17e832e6c86d8367f0",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "6224de70ff6c1a649c8d15799d598af05ebbd734699834a6399777640b7b2a6e"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-v2-wan-2.2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-v2",
        "label": "Classic · portrait-permissive-v2"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "5aaefa855d814895a223d35b436d8c83",
        "request_sha256": "967b1edc50e7d360cb5b5083e51abe2ada93252a7246f6851aed4a792981defa",
        "submitted_at": "2026-07-21T15:48:16Z",
        "completed_at": "2026-07-21T15:49:19Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-v2-wan-2.2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.2/02.mp4",
        "sha256": "4aa5f55be9e7c32535892f1454603237f94c80fe28aa15521c96fa423f2329b2",
        "bytes": 435714,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a lively photorealistic continuation of this exact first frame. In one continuous shot, let the woman move freely and expressively in whatever way naturally follows from her visible pose. Her face, mouth, head, shoulders, and raised hands may all move; leave the exact performance to the model instead of holding the initial pose. Motion starts immediately at normal real-time speed. Preserve the same person, striped clothing, setting, lighting, and framing. Keep the camera locked.",
        "negative": "identity replacement, extra limbs or fingers, severe face or hand anatomy failure, abrupt cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": {
        "id": "portrait-permissive-v2",
        "objective": "Compare useful model improvisation from the same neutral permissive portrait prompt without prescribing an emotion, gesture, blink, mouth action, or final pose.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.2/02.prompt.json",
        "prompt_sha256": "b2c92a88733178c92de7174a101982fedbf1c4bd1d52e4b9f81dc13d2a5732b2",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.2/02.run.json",
        "run_sha256": "d07c05f79424ea325f8621ac62f2a401f13d4827aeb34b646e6019ca502b13a4",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "72f97161b46122e16306a26117e9ebc866a02527dc7de5370999071a9efc27d5"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-v2-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-v2",
        "label": "Classic · portrait-permissive-v2"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "T5eHOlUBei5HYuFBdEYt",
        "request_sha256": "b1457c6300ed3aedeb8b320a337a469bde2f003639056455bebf932d471e4d38",
        "submitted_at": "2026-07-21T15:48:33Z",
        "completed_at": "2026-07-21T15:49:49Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-v2-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.7/02.mp4",
        "sha256": "cf099ba8d30a25998c9e28a417068ac8113c0e2c84172afed09dabefd79878d4",
        "bytes": 5204989,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a lively photorealistic continuation of this exact first frame. In one continuous shot, let the woman move freely and expressively in whatever way naturally follows from her visible pose. Her face, mouth, head, shoulders, and raised hands may all move; leave the exact performance to the model instead of holding the initial pose. Motion starts immediately at normal real-time speed. Preserve the same person, striped clothing, setting, lighting, and framing. Keep the camera locked.",
        "negative": "identity replacement, extra limbs or fingers, severe face or hand anatomy failure, abrupt cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-permissive-v2",
        "objective": "Compare useful model improvisation from the same neutral permissive portrait prompt without prescribing an emotion, gesture, blink, mouth action, or final pose.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.7/02.prompt.json",
        "prompt_sha256": "153eda4b47283e54da037432b41aa9652492bf8208b879fe274af4fa75b75722",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-v2/wan-2.7/02.run.json",
        "run_sha256": "6585d9fc0c189922b9ed1bf9a690e06aff75b29aff1ba2505fe5cecf62bbce57",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "b080216a76cc728ed89056ddf937ecae9985b7aee959cc57184b4d1690841090"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-wan-2.2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-veo-safe-v1",
        "label": "Classic · portrait-permissive-veo-safe-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "cb9ca9a352844bbaa0773d9a78a2eaf4",
        "request_sha256": "2071f6ca5c8e0d826e1bff1e04a1d19f736b99ed0c2e748855dc96ba36d4cf23",
        "submitted_at": "2026-07-21T16:05:33Z",
        "completed_at": "2026-07-21T16:06:33Z"
      },
      "model": {
        "id": "alibaba/wan-2.2",
        "label": "Wan 2.2"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-wan-2.2",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.2/02.mp4",
        "sha256": "979f4ac511aea196edaa4ebc1dce6dc9258f51af97cbffcc63789e17d00f7fd0",
        "bytes": 434104,
        "duration_seconds": 3.233,
        "width": 1152,
        "height": 768,
        "fps": 30.0,
        "frames": 97,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a photorealistic image-to-video continuation of the provided frame. Start exactly from the source image and let the visible moment develop naturally with expressive, coherent motion. Preserve the same person, clothing, setting, lighting, framing, and visual continuity. Keep the camera fixed. Use natural timing and realistic motion.",
        "negative": "identity change, severe anatomy failure, cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "wan-demo",
        "prompt_expansion": {
          "mode": "not_recorded",
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 3.2,
          "resolution": "720p",
          "generate_audio": false,
          "frames": 97,
          "fps": 30
        }
      },
      "experiment": {
        "id": "portrait-permissive-veo-safe-v1",
        "objective": "Test the most neutral permissive Veo wording after the shared v1 and v2 prompts produced filtered outputs.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.2/02.prompt.json",
        "prompt_sha256": "7d4536db73d2e2af13b1ee6f308bbd79e4283693597eb789e4e16ac0a364f056",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.2/02.run.json",
        "run_sha256": "17890d8688e7a558a3aba5684e3a994b61b76cc52378432e0e793dc1d7cf8e4b",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "bfdd185a9edde092942375cc7bf98ac77d61a4b11c154e6aa011024557554a50"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-wan-2.7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-veo-safe-v1",
        "label": "Classic · portrait-permissive-veo-safe-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "l2X2fbpQfOWlADIilJDq",
        "request_sha256": "9378da1cd586cd16c1014fa39dabc0b48b1099d1c1051b063d9381b333261a52",
        "submitted_at": "2026-07-21T16:07:06Z",
        "completed_at": "2026-07-21T16:08:59Z"
      },
      "model": {
        "id": "alibaba/wan-2.7",
        "label": "Wan 2.7"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-wan-2.7",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.7/02.mp4",
        "sha256": "b90f08bd33c2636a8d5a273ac93c0c0d606fb22dbf23a4dc00b05729fb5b6f3c",
        "bytes": 5600203,
        "duration_seconds": 5.0,
        "width": 1764,
        "height": 1176,
        "fps": 30.0,
        "frames": 150,
        "has_audio": true
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a photorealistic image-to-video continuation of the provided frame. Start exactly from the source image and let the visible moment develop naturally with expressive, coherent motion. Preserve the same person, clothing, setting, lighting, framing, and visual continuity. Keep the camera fixed. Use natural timing and realistic motion.",
        "negative": "identity change, severe anatomy failure, cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "disabled",
          "parameter": "prompt_extend",
          "value": false,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": false,
        "warnings": [
          "provider returned has_audio=True despite generate_audio=False"
        ],
        "requested": {
          "duration_seconds": 5,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-permissive-veo-safe-v1",
        "objective": "Test the most neutral permissive Veo wording after the shared v1 and v2 prompts produced filtered outputs.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.7/02.prompt.json",
        "prompt_sha256": "cbb7c6164923ee7c7a6833f47e760ace177434ee926f14ca4ee3d7e48ff26f6a",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/wan-2.7/02.run.json",
        "run_sha256": "8c33f46452cb44f89dfe7343a3fdc6a5f19122ae42fb598998a28a3964d57219",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "5b8ce52be99d37a48118f665fffe08ca1f029649533722177a500aedf257a0c3"
    },
    {
      "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-veo-3.1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
      },
      "review_group": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3
      },
      "approach": {
        "id": "clipmaker-classic-portrait-permissive-veo-safe-v1",
        "label": "Classic · portrait-permissive-veo-safe-v1"
      },
      "prompt_author": {
        "id": "clipmaker-classic",
        "label": "Clipmaker Classic",
        "contract_version": null,
        "attribution_basis": "legacy_generator_field",
        "provenance_verified": false
      },
      "agent": {
        "id": "clipmaker-classic",
        "contract_version": null,
        "planning_run_id": null,
        "author_thread_id": null,
        "batch_id": null,
        "provenance_verified": false
      },
      "generation": {
        "job_id": "3imyNsUEPfC7ljTTEiIN",
        "request_sha256": "39a8e5a4adcb6f017f13f76cdc7ea4cb8bb1e5a22712302b418dbc75c16bbf27",
        "submitted_at": "2026-07-21T15:56:15Z",
        "completed_at": "2026-07-21T15:58:03Z"
      },
      "model": {
        "id": "google/veo-3.1-lite",
        "label": "Veo 3.1 Lite"
      },
      "video": {
        "id": "promopages-9856-classic-portrait-permissive-veo-safe-v1-veo-3.1-lite",
        "path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/veo-3.1-lite/02.mp4",
        "sha256": "c36c6a340ef0094d1ecccb34101cfc8e698dee92296476a6e6e4d6146e9e778f",
        "bytes": 4219700,
        "duration_seconds": 4.0,
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "frames": 96,
        "has_audio": false
      },
      "context": null,
      "context_status": {
        "availability": "not_available_in_artifacts",
        "reason": "Фрагмент статьи не записан в артефактах этого прогона."
      },
      "prompt": {
        "positive": "Create a photorealistic image-to-video continuation of the provided frame. Start exactly from the source image and let the visible moment develop naturally with expressive, coherent motion. Preserve the same person, clothing, setting, lighting, framing, and visual continuity. Keep the camera fixed. Use natural timing and realistic motion.",
        "negative": "identity change, severe anatomy failure, cuts, scene changes, flicker, morphing, cartoon or CGI look",
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        },
        "source_model_id": null,
        "native_for_generation_model": true,
        "negative_transport": "embedded_in_positive"
      },
      "provider_contract": {
        "recorded_status": "succeeded",
        "review_status": "succeeded",
        "conforms": true,
        "warnings": [],
        "requested": {
          "duration_seconds": 4,
          "resolution": "1080p",
          "generate_audio": false,
          "frames": null,
          "fps": null
        }
      },
      "experiment": {
        "id": "portrait-permissive-veo-safe-v1",
        "objective": "Test the most neutral permissive Veo wording after the shared v1 and v2 prompts produced filtered outputs.",
        "prompt_strategy": null,
        "source_catalog": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/experiment.json"
      },
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/veo-3.1-lite/02.prompt.json",
        "prompt_sha256": "f449ebf3e8a03e6a9e0ae9ebe87be587edaaf0572b23c0cdf0640dffa5965a86",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments/portrait-permissive-veo-safe-v1/veo-3.1-lite/02.run.json",
        "run_sha256": "4b50995424023086f5600362d49cc28a36ffbff20bb81127635cbe3f2013969f",
        "lite_result_path": null,
        "lite_result_sha256": null
      },
      "review_basis_sha256": "6db4ae91ecc7a7a0827848cef82d33690821cbd39185ab645106be9888c18ba5"
    }
  ]
};
