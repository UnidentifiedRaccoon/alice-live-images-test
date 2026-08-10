# Femibion: forensic report по отсутствующим Veo 3.1 Lite

Дата фиксации: 2026-08-10. Скоуп: `08-femibion-grudnoe-vskarmlivanie / 05` и `07-femibion-gotovites-k-beremennosti / 06`, только маршрут `clipmaker-lite` → `google/veo-3.1-lite`.

## Вывод

Исходные видео отсутствовали не из-за сборки демо: provider jobs завершились без выходного файла. В run receipts записан статус `provider-failed` и текст `Video generation completed with no output (content may have been filtered)`; итоговый [all-attempts selection](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v7/all-attempts-selection-manifest.json) нормализует эти случаи как `provider-filtered`. Ответ провайдера не раскрывает точную policy category, поэтому ниже она не предполагается.

Для `08/05` помогла замена prompt при неизменных source, seed и route. Для `07/06` не помогли повтор запроса, несколько prompt-вариантов, seed-only вариант, обычный crop и framed source с человеком. Первый provider success получен в V7 на source без человека — background patch; затем patch детерминированно наложен на исходную композицию.

Во всех попытках route оставался тем же: `eliza-openrouter` / `eliza-video-jobs`, provider key `google-vertex`, 4 s, 1080p, 16:9, без аудио, без fallback и discovery. Во всех запросах было `enhancePrompt=true`.

## Хронология `08-femibion-grudnoe-vskarmlivanie / 05`

| Попытка | Provider job ID | Материальная дельта | Результат и evidence |
|---|---|---|---|
| Original | `6QIWOmo7PJgVMK4qECeg` | Baseline prompt про `stop gesture` и явно отклонённую pizza; source SHA `e29ddb18…06a`, seed `9681` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/videos/08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.run.json) |
| Retry | `tpePxKfkVlYvoc1nVeS0` | Без дельты: тот же request SHA `30df775a…955` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/terminal-provider-retries-v1/0cc5261325a58f1785ee/videos/veo-3.1-lite/05.run.json) |
| V1 | `8FDZycf6v5wTtzPmNYwF` | Изменён только смысл движения в prompt: небольшое опускание уже поднятой руки и перевод взгляда к еде; source и seed прежние | **Succeeded**, MP4 4 s / 1080p; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v1/videos/08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.run.json) |

V2–V7 для `08/05` не отправлялись: V1 уже дал принятый output.

## Хронология `07-femibion-gotovites-k-beremennosti / 06`

| Попытка | Provider job ID | Материальная дельта | Результат и evidence |
|---|---|---|---|
| Original | `Hfvx2OaGO9vsyrcs6AMf` | Baseline prompt: tap по smartphone; original source SHA `35c6fd00…ad12`, seed `9681` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| Retry | `dqjE7PrI5frFAFW7Y2Aa` | Без дельты: тот же request SHA `f7f0c0c2…7a01` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/videos/veo-3.1-lite/06.run.json) |
| V1 | `SwdH1eVdnIzgLHeXaTIg` | Prompt: tap → короткий медленный swipe; source и seed прежние | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v1/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V2 | `axgyuIecP85mwRLo7d13` | Нейтральный минимальный prompt: только blink/breathing, без предметного действия; original source, seed `9681` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v2/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V3 | `5UTHzBnYIH5XkaGt7kJj` | От V2 изменён только seed: `9681` → `27183` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v3/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V4 | `ph4kAnk1VL2vETZwBiSo` | Source-only control относительно V2: deterministic crop `2400×1600` → `1920×1080`, `x=240`, `y=100`; prompt V2, seed `9681` | No output; [transform receipt](recovery-inputs/07-femibion-gotovites-k-beremennosti/v4-transform.json), [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v4/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V5 | `c2wwhmzoBtXaxBRuDKl3` | Original source; prompt заменён на едва заметное изменение daylight, seed `9681` | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v5/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V6 | `rxIfCOzWeIJTt0yhb7wB` | От V5 изменён source: reversible framed `1920×1080`, человек и smartphone сохранены; daylight prompt и seed прежние | No output; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v6/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |
| V7 | `c4pO6Fw8YaEz0vPon3wH` | От V6 изменён source: `1920×1080` background-only patch без человека, SHA `31672c58…b88e`; daylight prompt и seed прежние | **Succeeded**, raw provider MP4; [run receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v7/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json) |

## Факты и гипотезы

Факты:

- Original и retry у обеих картинок повторили одинаковые request fingerprints и оба раза вернули no output.
- У `08/05` исход с no output сменился на success после prompt rewrite при том же source, seed `9681` и route.
- У `07/06` смена action prompt, нейтральный prompt, seed-only вариант и три source-варианта с человеком не дали output. V7 с тем же daylight prompt, seed и route, но с background-only source, дал output.
- `enhancePrompt=true` означает, что провайдер мог скрыто расширить переданный prompt. Текст внутреннего expanded prompt в receipts отсутствует.
- Immutable V5 prompt receipt содержит ошибку в dimensions: pinned source SHA `35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12` — это фактический local JPEG `2400×1600`, тогда как receipt записал `1920×1080`. Provider payload содержал URL без dimensions, поэтому ошибка metadata не повлияла на submit payload или request SHA. Final selection сохраняет recorded и actual значения раздельно и ставит `receipt_dimensions_match_file=false`; ошибочный размер не используется как доказательство изолированного фактора.

Интерпретации, а не доказанные policy-причины:

- `08/05` вероятнее prompt-sensitive: это самый чистый наблюдаемый outcome flip при неизменных source/seed/route. Нельзя установить, сработало конкретное слово, смысл prompt или скрытое prompt expansion.
- `07/06` сильнее source/person/image-sensitive именно внутри зафиксированного Veo route: prompt-only и seed-only варианты не помогли, а success появился после удаления человека из provider source. При этом V7 меняет несколько пиксельных свойств source одновременно, поэтому отдельно доказать влияние лица, позы, smartphone или кадрирования нельзя.

## Workaround и итоговый выбор

Raw V7 — provider output только для background patch. Финальный `07/06` — **не новый provider output**, а воспроизводимый deterministic composite: raw patch масштабируется до `800×450`, мягко маскируется и накладывается в `x=1120`, `y=250` на V4 base JPEG. Полная геометрия, ffmpeg recipe, hashes и ffprobe invariants закреплены в [composite receipt](../clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v7/composite/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.receipt.json); воспроизведение выполняет [fail-closed helper](../scripts/clipmaker_lite_promopages_10060_femibion_veo_v7_composite.py).

Итоговый selection выбирает V1 provider MP4 для `08/05` и V7-derived composite для `07/06`; `ready_for_merge=true`, `accepted_output_count=2`. Composite SHA-256: `d058fe8556e2f3badaa436745b1aa6e30ff0e726ef1648134225508e5917e13c`, размер `552368` bytes.

## Accounting

- Текущее frozen accounting: **289 paid submissions / $101.15 aggregate reserved**.
- Recovery V1–V7: 8 submissions × $0.35 = $2.80 поверх baseline `281 / $98.35`.
- Авторизованный дополнительный бюджет для V4–V7: $5.00; использовано **$1.40** (4 × $0.35), осталось **$3.60** до hard cap `$104.75`.

Это conservative reserved accounting из immutable manifests, а не сверка с provider invoice.
