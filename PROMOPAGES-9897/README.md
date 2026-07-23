# PROMOPAGES-9897 — ручная разметка видеогенераций

Режим разметки доступен на `manual-review/`. Он работает как самостоятельная
статическая страница медиадемки и не меняет prompt, run или generation
manifests.

## Источники данных

В набор включены 57 декодируемых MP4 из четырёх когорт:

- 15 — Clipmaker Lite, текущая итерация из
  `clipmaker-lite-runs/promopages-9891-lite3-20260723/manifest.json`;
- 15 — Clipmaker Lite, предыдущая итерация из
  `clipmaker-lite-generation-manifest.json`;
- 15 — Clipmaker Classic, основная матрица из
  `video-generation-manifest.json`;
- 12 — успешные Clipmaker Classic portrait experiments.

Два failed Veo experiment без MP4 не включены. Все источники, их manifest
SHA-256 и принадлежность к когорте записываются в `dataset.sources`.

`manual-review/review-data.js` — проверяемый browser allowlist. Он содержит
только поля, необходимые для оценки: видео и SHA-256, точный авторский prompt,
provider prompt-expansion/transport, тег автора, подход, модель, доступную
provenance и технические идентификаторы. Исходные изображения в страницу не
включаются.

Контекст показывается только для текущей Lite-итерации: соседние абзацы — точный
локальный снимок вокруг позиции изображения из привязанного `content.json`, а
не весь input агента. Для предыдущей Lite-итерации snapshot намеренно равен
`null` по политике этой разметки. Исторические result-артефакты технически
содержат привязку к статье, поэтому статус называется
`omitted_by_review_policy`, а не `not_provided`. В Classic-артефактах контекста
статьи нет; их статус — `not_available_in_artifacts`. Интерфейс не показывает
для этих записей заголовок, лид, ссылку или фрагменты и предлагает оценивать
видео относительно промпта.

Пять записей предыдущей Lite-итерации — cross-model control: авторский prompt
для Wan 2.7 повторно использован для генерации Wan 2.2. Они не выдаются за
нативную практику Wan 2.2 и получают отдельный тег и техническую пометку.
В основной Classic-матрице ещё два prompt-артефакта явно указывают Wan 2.2 как
source model при генерации Wan 2.7 и Veo; они тоже помечены как cross-model
transfer, а не как нативные практики целевых моделей.

Clipmaker Classic нормализован к каноническому тегу `clipmaker-classic` по
историческому маршруту `project clipmaker agent`. Это legacy-атрибуция, а не
верифицированная runner provenance; исходный prompt-артефакт остаётся связан с
записью через путь и SHA-256.
Расширенный провайдером текст нигде не сохранялся: интерфейс показывает наличие
`prompt_extend`/`enhancePrompt`, но не выдумывает итоговый provider prompt.

Пересобрать и проверить allowlist:

```bash
python3 scripts/build_quality_review_data.py
python3 scripts/build_quality_review_data.py --check
```

## Хранение и экспорт

Черновики и завершённые оценки автоматически сохраняются в `localStorage`
текущего браузера под стабильным ключом PROMOPAGES-9897 и привязаны к
`review_basis_sha256` — SHA-256 видео, prompt, автора, когорты и политики
контекста. Состояние прежнего 15-item набора мигрируется один раз для тех же
неизменившихся item ID. Это локальное, а не командное хранилище. Переносимым
артефактом считается JSON, скачанный кнопкой «Экспортировать JSON».

Экспорт соответствует `annotation-schema.json` и содержит:

- идентификатор набора и список source manifests с SHA-256;
- время начала сессии и экспорта;
- завершённые `annotations` и незавершённые `drafts`;
- для каждой записи — video/context/prompt snapshots, `context_status`,
  `prompt_author`, `review_group`, `approach`, rating, feedback, доступные run и
  provider IDs, `completed_at` и `updated_at`.

Оценка обязательна. Для `1 — Плохо` и `2 — Нормально` feedback обязателен;
для `3 — Хорошо` он не блокирует завершение.

Состояние разных вкладок объединяется по отдельным записям и их `updatedAt`,
поэтому параллельные черновики не сводятся к общему last-write-wins. Видео не
запускаются автоматически и не выключают звук принудительно. Provider contract
deviations показываются отдельной технической пометкой и не скрываются.

При анализе нельзя сравнивать только среднее Lite против Classic: portrait
представлен заметно чаще из-за Classic experiments. Безопасный срез — как
минимум `sample_id + review_group + model_id`, а для экспериментов ещё и
`approach.id`.

Проверить workflow и данные:

```bash
node --test scripts/test_manual_review_core.js
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/clipmaker_lite_batch_pipeline.py verify --allow-contract-warnings
```

## Результат разметки

- [`analysis/clipmaker-quality-annotations-2026-07-23.json`](analysis/clipmaker-quality-annotations-2026-07-23.json)
  — полный экспорт: 57 завершённых оценок, 0 черновиков;
- [`analysis/clipmaker-review-report-2026-07-23.md`](analysis/clipmaker-review-report-2026-07-23.md)
  — количественный и качественный анализ, ограничения, рекомендации и дизайн
  следующего эксперимента.

SHA-256 исходного экспорта:
`a419d4eaca60a2996d2c8534ed74bfc071085ba5918825fc70074b62ef2c8d34`.

## Локальный просмотр

Из корня репозитория:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Затем открыть `http://127.0.0.1:4173/manual-review/`.

## Browser evidence

- `evidence/manual-review-mixed-desktop.jpg` — предыдущая Lite-итерация с
  author/approach tags и cross-model control при 1280×720;
- `evidence/manual-review-mixed-mobile.jpg` — тот же historical item при
  390×844 без горизонтального overflow;
- `evidence/manual-review-mixed-mobile-form.jpg` — форма без выдуманного
  контекста, с динамической нумерацией и вопросом относительно промпта;
- `evidence/manual-review-desktop.jpg` — старт экрана при 1280×720;
- `evidence/manual-review-feedback.jpg` — закреплённое видео рядом с полем отзыва;
- `evidence/manual-review-context.jpg` — показ раздела статьи и подписи у изображения;
- `evidence/manual-review-mobile.jpg` — верх экрана при 390×844;
- `evidence/manual-review-mobile-form.jpg` — переход от видео к форме на мобильном.
