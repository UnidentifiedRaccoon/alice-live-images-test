window.qualityReviewDataset = {
  "schema_version": 1,
  "dataset_id": "promopages-9891-lite3-20260723@f6fdff5dba9a",
  "review_ticket": "PROMOPAGES-9897",
  "source": {
    "ticket": "PROMOPAGES-9891",
    "batch_id": "promopages-9891-lite3-20260723",
    "manifest_path": "PROMOPAGES-9857/clipmaker-lite-runs/promopages-9891-lite3-20260723/manifest.json",
    "manifest_sha256": "0cfc4a045882e3ef6a54e29c85e869f6b56f4389fa3ce10ff379776d001d0e19",
    "data_sha256": "f6fdff5dba9afd15348e337e8b590ca89df6b3772fafd099b29a7d23a8b4b70b",
    "manifest_updated_at": "2026-07-23T08:11:12Z"
  },
  "items": [
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
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
      "prompt": {
        "positive": "Fixed close-up. The woman’s raised fingers slowly curl tighter as her jaw clenches and her eyebrows lift with mounting tension; a brief natural blink follows, then her hands and jaw loosen slightly while she keeps looking straight ahead.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/02.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/02.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-wan-2-2/result.json",
        "lite_result_sha256": "33b85dcaa5d1868b06184d5967eda77dd469089570f245acdd59d2662aaaf530"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
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
      "prompt": {
        "positive": "Her anxious tension builds continuously: both hands tremble slightly near her cheeks as the curled fingers tighten inward, her brows lift and facial muscles tense, then one eyelid gives two brief involuntary twitches near the end. Keep the camera fixed in the close frontal framing, ending on her strained, alarmed expression.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/02.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/02.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-wan-2-7/result.json",
        "lite_result_sha256": "1212bf063c9841c3256376d967e952c025c7637bc4a824ae11ebd9f36a341a15"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite",
      "sample_id": "01-portrait-hands",
      "article": {
        "slug": "01-pharmocean-magiia-magniia",
        "label": "Pharmocean — Магия магния",
        "url": "https://pharmocean.promo.page/media/magiia-magniia-68f5ff4f55f9e8662bdfb1d4_0_0"
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
      "prompt": {
        "positive": "Fixed camera, single continuous shot. The woman’s lower eyelid begins to twitch subtly as her eyes stay wide; tension builds through her clenched jaw, raised shoulders, and fingers curling tighter beside her face. She then releases a short controlled breath, her fingers loosen slightly and her shoulders drop a little, ending still visibly strained.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/02.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/02.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-01-portrait-hands-veo-3-1-lite/result.json",
        "lite_result_sha256": "64c36abef90e3c5b00677b9e8ad883442ff726a7304599b29a8582b4858c449a"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-2",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
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
      "prompt": {
        "positive": "Fixed camera. The clear serum droplet at the pipette tip slowly elongates under gravity, narrows into a glossy thread, then detaches and falls straight down, leaving a tiny fresh bead forming at the tip by the end. The pipette and product arrangement stay still; subtle highlights glide through the viscous liquid.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/05.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/05.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-wan-2-2/result.json",
        "lite_result_sha256": "ad291e9717a1e8b6d1a03c4df38155a96b2988ebc08a8e6d448578a812785f0e"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-wan-2-7",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
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
      "prompt": {
        "positive": "Keep the camera fixed. Clear serum slowly gathers at the pipette tip, elongates under gravity, then detaches and falls toward the truffles near the end; a new tiny bead begins forming on the tip. Preserve the calm product-display composition.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/05.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/05.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-wan-2-7/result.json",
        "lite_result_sha256": "91ab21853c08d7c45019147d3366b45a847aea9bf81cb8d36d1c87002aa110d0"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite",
      "sample_id": "02-product-dropper",
      "article": {
        "slug": "04-graceface-antivozrastnaia-syvorotka",
        "label": "Graceface — Антивозрастная сыворотка",
        "url": "https://graceface.promo.page/media/nashla-luchshuiu-antivozrastnuiu-syvorotku-za-smeshnye-dengi-682b55d20cfd5f4e6d52b586_0_0"
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
      "prompt": {
        "positive": "Slow, subtle camera push-in. The clear serum at the pipette tip gradually swells and stretches, then detaches near the end and falls onto the white surface, settling into a small glossy bead. Keep the bottle, dropper, and truffles otherwise still in one continuous product shot.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/05.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/05.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-02-product-dropper-veo-3-1-lite/result.json",
        "lite_result_sha256": "7e01189ab684d7cc71dc4f0400fdedd56fc1f71a87804fa42579db748f727dba"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-2",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
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
      "prompt": {
        "positive": "The cat calmly steps out of the litter box to the right, placing its lowered front paw on the floor and smoothly shifting its weight forward. Its other front paw follows over the rim as the head tracks the movement, ending balanced in a natural walking stance. Fixed camera.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/03.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/03.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-wan-2-2/result.json",
        "lite_result_sha256": "97e93335576bf43616a8f790832d89fc139527d8d382da64c5cc1f7cd8e61fb0"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-wan-2-7",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
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
      "prompt": {
        "positive": "The cat calmly steps down from the litter box, places the extended front paw on the floor, shifts its weight forward, then brings the other paws down and walks one measured step toward the right. Its head stays low and alert, with subtle ear, whisker, and tail movement. Fixed camera.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/03.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/03.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-wan-2-7/result.json",
        "lite_result_sha256": "b91b3286fb348b17ae46cd0df8399ff5501ff885c08601c4fcc4ac5d5fe13878"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite",
      "sample_id": "03-animal-step",
      "article": {
        "slug": "06-4lapy-koshachii-napolnitel",
        "label": "Четыре лапы — Наполнитель для кошачьего туалета",
        "url": "https://4lapy.promo.page/media/kak-ubrat-zapah-koshachego-tualeta-vybiraem-napolnitel-6718c349d809026a62687d57_0_0"
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
      "prompt": {
        "positive": "Fixed camera. The cat calmly steps out of the litter tray toward the right, places the extended front paw on the floor, brings the other front paw over the rim, and shifts its weight forward in one smooth, confident motion. Its head tracks slightly ahead while the ears, whiskers, and tail move subtly with the step, ending naturally mid-walk beside the tray.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/03.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/03.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-03-animal-step-veo-3-1-lite/result.json",
        "lite_result_sha256": "69207c46033a9ae11e3a4e09dd1ffb873810fce6051e0b56b3484a18e5e76e57"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-2",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
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
      "prompt": {
        "positive": "The camera remains fixed as the narrow waterfall streams flow steadily into the pool. Soft ripples spread outward across the turquoise water, gently shifting the underwater light reflections; nearby leaves tremble almost imperceptibly from the moving air. The ripples settle into a calm, continuous shimmer by the end.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/09.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/09.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-wan-2-2/result.json",
        "lite_result_sha256": "cb964d5399535af12b23c709f993cb58dc6cb21726fca381855959124b747aeb"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-wan-2-7",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
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
      "prompt": {
        "positive": "Keep the camera fixed. The narrow waterfall pours steadily into the pool for the full shot, sending overlapping ripples across the turquoise water. Underwater light shimmers and refracts over the tiled walls while the nearest leaves sway faintly in the humid air; the ripples gradually soften toward the end.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/09.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/09.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-wan-2-7/result.json",
        "lite_result_sha256": "abe27aa81f462b7f52b1a6cfe34870209ebab12f20599d353948d81144d9eba6"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite",
      "sample_id": "04-interior-water",
      "article": {
        "slug": "13-ilinka-elitnyi-zhk",
        "label": "ЖК «Ильинка 3/8» — Элитный ЖК напротив Кремля",
        "url": "https://r1864.promo.page/media/pokazyvaem-chto-za-elitnyi-jk-stroiat-naprotiv-kremlia-648b2ca27e930436a8c7d0ff_6_4"
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
      "prompt": {
        "positive": "A very slow camera push toward the pool. The narrow waterfall streams steadily down the wall, creating expanding ripples across the water while the underwater light reflections shimmer gently. Keep the motion calm and continuous, with the ripples naturally spreading through the foreground by the end.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/09.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/09.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-04-interior-water-veo-3-1-lite/result.json",
        "lite_result_sha256": "718f0387354a253d442de89372e044c61048f81bb16ac167b2da384c63d5c4c5"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-2",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
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
      "prompt": {
        "positive": "A single fixed shot of the financial dashboard. A soft blue highlight travels clockwise along the existing blue arc of the circular chart at a steady pace, then the arc gives one subtle confirmation pulse while the displayed loan amount and monthly payment briefly brighten and settle. Keep all numbers, labels, cards, checkboxes, and layout unchanged.",
        "negative": null,
        "provider": "wan-streamlit",
        "prompt_expansion": {
          "mode": "not_exposed",
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/04.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.2/04.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-wan-2-2/result.json",
        "lite_result_sha256": "b25a38f82c600719c7843ed1f173fa63c07ded165f45da14af530fd58259a2cc"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-wan-2-7",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
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
      "prompt": {
        "positive": "Keep the camera fixed. The purple load arc gently advances a few degrees while the two checked card rows receive a soft sequential highlight; the loan amount and monthly payment subtly count into their displayed values, then settle as the arc stops. Preserve the clean, readable interface.",
        "negative": null,
        "provider": "atlas-cloud",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "prompt_extend",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/04.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/wan-2.7/04.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-wan-2-7/result.json",
        "lite_result_sha256": "79d245b25379a9c39a152854f85ccd63a6140a288b23b0543bd62c0c38312a57"
      }
    },
    {
      "id": "promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite",
      "sample_id": "05-finance-ui",
      "article": {
        "slug": "20-sravni-kreditnyi-reiting",
        "label": "Сравни — Как повысить кредитный рейтинг",
        "url": "https://sravni.promo.page/media/kak-povysit-kreditnyi-reiting-uznaite-na-sravni-65f160d13bba425fc5fa82cc_0_0"
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
      "prompt": {
        "positive": "Keep the camera fixed on the interface. The lower credit card checkbox smoothly switches off; in the same continuous response, the purple gauge arc retracts clockwise and the available credit amount counts upward, easing into its updated value near the end. All other UI elements remain still.",
        "negative": null,
        "provider": "google-vertex",
        "prompt_expansion": {
          "mode": "enabled",
          "parameter": "enhancePrompt",
          "value": true,
          "expanded_text_available": false
        }
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
      "source_refs": {
        "prompt_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/04.prompt.json",
        "run_path": "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/clipmaker-lite/runs/promopages-9891-lite3-20260723/veo-3.1-lite/04.run.json",
        "lite_result_path": "artifacts/clipmaker-lite/v1/promopages-9891-lite3-20260723-05-finance-ui-veo-3-1-lite/result.json",
        "lite_result_sha256": "2e4fbb460d3590623e129f5b17922d24b2455f3b1fb035078064b35a1a807796"
      }
    }
  ]
};
