# PROMOPAGES-9897 — ручная разметка видеогенераций

Режим разметки доступен на `manual-review/`. Он работает как самостоятельная
статическая страница медиадемки и не меняет prompt, run или generation
manifests.

## Источник данных

Канонический набор — свежая матрица 5×3:

`PROMOPAGES-9857/clipmaker-lite-runs/promopages-9891-lite3-20260723/manifest.json`

В разметку включены все 15 декодируемых MP4. Пять Wan 2.7 файлов имеют
provider contract deviations (аудио и, для четырёх роликов, геометрия). Эти
отклонения показаны как отдельная техническая пометка и не скрываются.

`manual-review/review-data.js` — проверяемый browser allowlist. Он содержит
только поля, необходимые для оценки: видео и SHA-256, точные соседние фрагменты
текста, финальный prompt, provider prompt-expansion, идентификаторы агента,
модели, planning run и provider job. Исходные изображения в страницу не
включаются.

Clipmaker Lite получал полную статью `content.json`. Соседние абзацы в
интерфейсе — точный локальный снимок вокруг позиции изображения, а не весь
input агента. Если у позиции есть заголовок раздела или подпись, они тоже
показаны разметчику и попадают в snapshot. Расширенный провайдером текст не
сохранялся: интерфейс показывает наличие `prompt_extend`/`enhancePrompt`, но не
выдумывает итоговый provider prompt.

Пересобрать и проверить allowlist:

```bash
python3 scripts/build_quality_review_data.py
python3 scripts/build_quality_review_data.py --check
```

## Хранение и экспорт

Черновики и завершённые оценки автоматически сохраняются в `localStorage`
текущего браузера и привязаны к SHA-256 видео, prompt и показанного контекста.
Это локальное, а не командное хранилище. Переносимым
артефактом считается JSON, скачанный кнопкой «Экспортировать JSON».

Экспорт соответствует `annotation-schema.json` и содержит:

- идентификатор и SHA-256 исходной batch-матрицы;
- время начала сессии и экспорта;
- завершённые `annotations` и незавершённые `drafts`;
- для каждой записи — video/context/prompt snapshots, rating, feedback,
  `agent_id`, `model_id`, `run_id`, `completed_at` и `updated_at`.

Оценка обязательна. Для `1 — Плохо` и `2 — Нормально` feedback обязателен;
для `3 — Хорошо` он не блокирует завершение.

Состояние разных вкладок объединяется по отдельным записям и их `updatedAt`,
поэтому параллельные черновики не сводятся к общему last-write-wins. Видео не
запускаются автоматически и не выключают звук принудительно: у пяти Wan 2.7
роликов добавленная провайдером аудиодорожка доступна для проверки.

Проверить workflow и данные:

```bash
node --test scripts/test_manual_review_core.js
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/clipmaker_lite_batch_pipeline.py verify --allow-contract-warnings
```

## Локальный просмотр

Из корня репозитория:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Затем открыть `http://127.0.0.1:4173/manual-review/`.

## Browser evidence

- `evidence/manual-review-desktop.jpg` — старт экрана при 1280×720;
- `evidence/manual-review-feedback.jpg` — закреплённое видео рядом с полем отзыва;
- `evidence/manual-review-context.jpg` — показ раздела статьи и подписи у изображения;
- `evidence/manual-review-mobile.jpg` — верх экрана при 390×844;
- `evidence/manual-review-mobile-form.jpg` — переход от видео к форме на мобильном.
