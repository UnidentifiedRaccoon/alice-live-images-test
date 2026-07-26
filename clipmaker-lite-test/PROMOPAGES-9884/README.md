# PROMOPAGES-9884 — текст 20 статей с позициями изображений

Набор дополняет выгрузку изображений из `PROMOPAGES-9857` контекстом статей.
Для каждой из 20 статей создан UTF-8-файл `content.json`, где текстовые блоки и
125 появлений изображений сохранены в исходном порядке.

## Состав

- 20 статей и 20 файлов `content.json`;
- 675 упорядоченных блоков: 550 текстовых и 125 `image`;
- 125 `image`-блоков соответствуют 125 строкам исходного `manifest.csv`;
- 76 inline-ссылок и 3 CTA с авторским текстом;
- 1 явное исключение: у статьи 12 исходное поле `preview.snippet` пусто;
- статус независимой проверки — `PASS`.

```text
PROMOPAGES-9884/
  README.md
  exceptions.json
  verification-report.json
  articles/
    01-pharmocean-magiia-magniia/content.json
    ...
    20-sravni-kreditnyi-reiting/content.json
```

Идентификаторы папок полностью совпадают с
`PROMOPAGES-9857/articles/`. Изображения не копируются повторно: поле `file`
указывает имя файла в соответствующей папке исходного набора, а
`manifest_file_path` — его точный путь относительно `PROMOPAGES-9857/`.

## Источник и порядок блоков

Публичная HTML-страница PromoPages содержит SSR-состояние редактора в
`w._data`. Выгрузка использует только структурированные поля этого объекта:

1. `publication.content.preview.title` → `title`;
2. `publication.content.preview.snippet` → `lead` без fallback;
3. `publication.headImage` → обложка перед первым блоком body;
4. `publication.content.articleContent.contentState.draftJsState` → текст и
   изображения тела статьи;
5. `publication.swipeToSite.callToAction` → финальный `cta`, только если
   собственный текст CTA непустой.

Обложка расположена перед DraftJS-body. Дальше блоки идут строго по
`source_block_index`. Галерея раскрывается в несколько последовательных
`image`-блоков по `data.images[]`; порядок внутри неё задаёт `gallery_index`.
Значения `source_block_index = 0` и `gallery_index = 0` являются валидными
позициями, а не отсутствующими значениями.

Заголовок и `lead` хранятся как метаданные и не добавляются повторно в
`blocks`. `preview.snippet` у старых публикаций может быть длинным, пересекаться
с body или отсутствовать; он сохранён буквально и не используется вместо
первого текстового блока.

## Схема `content.json`

Все файлы используют `schema_version = "1.0"` и одинаковый верхний уровень:

```json
{
  "schema_version": "1.0",
  "article_number": 1,
  "article_key": "01",
  "article_id": "01-pharmocean-magiia-magniia",
  "url": "https://…",
  "final_url": "https://…",
  "canonical_url": "https://…",
  "publication_id": "…",
  "publication_version": 42,
  "title": "…",
  "lead": "…",
  "cta": {
    "text": "…",
    "link_to_open": "https://…",
    "link_to_show": "…",
    "included_in_blocks": true
  },
  "blocks": []
}
```

`url` — URL из постановки и image-manifest, `final_url` — effective URL HTTP,
`canonical_url` и publication-поля — значения embedded source. Они разделены,
потому что статьи 08, 12, 13 и 14 отвечают без HTTP-редиректа, но с другим
canonical/publication ID.

### Текстовые блоки

| `type` | Источник DraftJS | Дополнительные поля |
| --- | --- | --- |
| `paragraph` | `unstyled` | — |
| `heading` | `header-two`, `header-three` | `level` |
| `quote` | `blockquote` | — |
| `list_item` | `unordered-list-item` | `list_style`, `depth` |
| `legal` | `legal` | — |
| `cta` | `swipeToSite.callToAction` | `url`, `source_block_index: null` |

Каждый DraftJS-текстовый блок содержит `source_block_index`, `text`,
`inline_styles` и `links`. Абзацы не склеиваются; переводы строк, NBSP и другие
символы source text не нормализуются. Смещения inline styles и ссылок сохранены
в единицах UTF-16, как в DraftJS.

### Блок изображения

```json
{
  "type": "image",
  "image_id": "03",
  "file": "03.png",
  "manifest_file_path": "articles/12-mars-podarki-na-8-marta/03.png",
  "role": "gallery_image",
  "source_image_id": "…",
  "source_block_index": 17,
  "gallery_index": 0,
  "alt": "",
  "caption": "…",
  "duplicate_of": null
}
```

- `image_id` — двухзначный `image_number` из
  `PROMOPAGES-9857/articles/manifest.csv`; он совпадает с именем файла;
- `source_image_id` — исходный MDS/editor ID для контрольного join;
- `role` — `cover`, `article_image` или `gallery_image`;
- `duplicate_of` сохраняет намеренные повторные появления из manifest;
- у обложки оба индекса равны `null`, у одиночного изображения
  `gallery_index = null`;
- caption одиночного изображения и первого элемента галереи берётся из
  `block.text`, остальных элементов галереи — из `block.data.contents[id]`;
- авторского `alt` в editor state и image catalogue нет, поэтому `alt` оставлен
  пустым. Автоматический DOM-alt из заголовка/caption не выдаётся за source.

## Что исключено

В набор не попадают навигация, логотипы, аватары, рекомендации, feedback,
системные кнопки, футер, рекламные и аналитические элементы. Это гарантируется
тем, что body читается из editor state, а не из DOM. CTA без собственного
`callToAction` не получает сгенерированный текст. Фоновый asset CTA не считается
контентным изображением и не добавляется в image sequence.

`exceptions.json` содержит все unresolved-поля и ограничения источника. В
текущем наборе единственное unresolved-поле — пустой `lead` статьи 12; SEO
description и первый абзац намеренно не использованы как подстановка.

## Воспроизведение и проверка

Из корня репозитория:

```bash
python3 scripts/collect_promo_article_content.py
python3 -m unittest scripts/test_collect_promo_article_content.py
python3 scripts/verify_promo_article_content.py
```

Сборщик делает сетевой read-only-запрос к 20 публичным статьям. Verifier сети не
использует: он повторно читает каждый JSON, проверяет UTF-8 и единую схему,
сверяет все 125 image occurrences с manifest и сравнивает расчётный итог с
`verification-report.json`.
