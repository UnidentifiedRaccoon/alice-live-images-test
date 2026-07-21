# PROMOPAGES-9857 — исходные изображения 20 статей

Набор собран для Side-by-Side-теста Wan 2.2 (Алиса), Wan 2.7 и Veo 3.1 Lite.
Внутри `articles/` находятся 20 папок в порядке постановки, `manifest.csv`,
`taxonomy.md` и отчёт независимой проверки.

## Состав

- 20 статей;
- 125 появлений изображений;
- 119 уникальных `image_id`;
- 78 JPEG, 46 PNG и 1 WebP;
- 0 случаев недоступного `orig`;
- 0 производных изображений, использованных вместо `orig`.

Файлы нумеруются в порядке показа: сначала обложка, затем блоки статьи. Для
галереи сохраняется внутренний порядок элементов. Если один и тот же исходник
использован как обложка и ещё раз внутри статьи, обе позиции присутствуют как
отдельные файлы с одинаковыми `orig_url` и SHA-256:

- `03/01` = `03/02`;
- `04/01` = `04/02`;
- `07/01` = `07/02`;
- `08/01` = `08/04`;
- `14/01` = `14/04`;
- `20/01` = `20/02`.

Статьи 15–20 добавляют сложные кейсы: баннеры и интерфейсы, пять галерей
Ekonika, планировки и дисклеймер недвижимости, пользовательские отзывы,
тёмные фотографии и travel/finance UI. Все 12 элементов галерей сохранены в
исходном порядке.

## Как определялись изображения

Публичная HTML-страница PromoPages содержит структурированное состояние
редактора и каталог MDS-изображений в `window._data`.

1. Обложка читается из `publication.headImage`.
2. Контент и порядок читаются только из `atomic:image`-блоков DraftJS; логотипы,
   аватары, навигация и прочий chrome в эту последовательность не входят.
3. Для каждого `image_id` URL строится из `namespace`, `groupId` и `imageName`.
4. Скачивается только ресурс с суффиксом `/orig`. При ошибке производный вариант
   не подставляется.
5. Загруженные байты не декодируются для повторного сохранения, не
   перекодируются и не ресайзятся.

## Что подтверждает manifest

`articles/manifest.csv` хранит URL статьи, роль и позицию изображения, URL
производного варианта страницы, точный `orig_url`, путь, формат, заявленные и
фактические размеры, размер файла в байтах, SHA-256, статус и примечание об
исключении. Пути в `file_path` заданы относительно корня этого набора.

Поля `primary_class`, `scene_tags`, `scene_description`, `motion_cues` и
`risk_notes` заполнены для каждого изображения. Для класса
`text_interface_collage` дополнительно заполнены `graphic_kind` — активный
prompt-route — и `graphic_kinds` — все видимые виды графики. Для остальных
классов эти поля пусты. Дубликаты одного `image_id` имеют одинаковую
классификацию. Определения классов, graphic routing и рекомендации по камере
находятся в `articles/taxonomy.md`.

В `classifications.json` `graphic_kinds` хранится JSON-массивом с активным kind
на первом месте; в CSV те же значения сериализованы через `; `.

`articles/verification-report.json` создаётся после повторного чтения каждого
файла и проверки SHA-256, числа байт, формата, размеров, непрерывности нумерации,
полноты классификации, валидности controlled `graphic_kinds`, покрытия taxonomy
и отсутствия лишних файлов.

## Как перепроверить

Сборщик и verifier рассчитаны на Python 3 с установленным Pillow. Из корня
репозитория:

```bash
python3 -m pip install Pillow
python3 scripts/verify_promo_images.py
```

Успешная проверка завершается статусом `PASS`. Флаг `--write-report` дополнительно
перезаписывает `articles/verification-report.json` актуальным результатом.

## Пайплайн видео для PROMOPAGES-9856

Для сравнения моделей выбраны ровно пять изображений из разных статей и разных
визуальных классов:

| Sample | Статья / файл | Проверяемый риск |
| --- | --- | --- |
| `01-portrait-hands` | `01-pharmocean-magiia-magniia/02.jpeg` | лицо, зубы и две кисти |
| `02-product-dropper` | `04-graceface-antivozrastnaia-syvorotka/05.png` | этикетка, стекло и капля |
| `03-animal-step` | `06-4lapy-koshachii-napolnitel/03.jpeg` | один завершённый шаг и лапы |
| `04-interior-water` | `13-ilinka-elitnyi-zhk/09.png` | архитектурная геометрия и вода |
| `05-finance-ui` | `20-sravni-kreditnyi-reiting/04.png` | неизменный UI и читаемый текст |

Исходный отбор зафиксирован в `video-samples.json`, а 15 проверенных prompt-пар
для точной матрицы 5 × 3 — в `video-prompts.json`. Промпты подготовлены через
проектный clipmaker с отдельным model spec для `alibaba/wan-2.2`,
`alibaba/wan-2.7` и `google/veo-3.1-lite`.

CLI валидирует полный декартов набор, SHA-256 исходников и модельные ограничения,
после чего материализует артефакты рядом с каждой статьёй:

```text
articles/<article>/video/<model>/<image>.prompt.json
articles/<article>/video/<model>/<image>.run.json
articles/<article>/video/<model>/<image>.mp4
```

Общий статус всех 15 запусков хранится в `video-generation-manifest.json`.
`run.json` содержит только безопасный request preview, provider job ID, статус,
результат `ffprobe` и явную сверку факта с модельным контрактом;
OAuth-заголовки и временные download URL не записываются. Сырой MP4 провайдера
не ремультиплексируется: если endpoint проигнорировал `generate_audio: false`,
это остаётся видимым в `media.has_audio` и `contract_check.warnings`.
Ручной keyframe-аудит результата и обнаруженные нарушения prompt fidelity
описаны в `video-generation-review.md`.

### Команды

Из корня репозитория:

```bash
# Проверить каталоги и создать 15 prompt/run-пар.
python3 scripts/video_generation_pipeline.py plan

# Проверить точные provider payload без сетевых и платных запросов.
python3 scripts/video_generation_pipeline.py run --dry-run

# Реальная последовательная генерация всей матрицы или выбранной части.
python3 scripts/video_generation_pipeline.py run
python3 scripts/video_generation_pipeline.py run \
  --sample 03-animal-step \
  --model alibaba/wan-2.7

# Повторный запуск продолжает сохранённые асинхронные job и пропускает готовые MP4.
# --force нужен только для сознательной повторной платной генерации.
python3 scripts/video_generation_pipeline.py verify
```

До завершения всей матрицы для проверки структуры можно использовать
`verify --allow-incomplete`.

Wan 2.2 отправляется в внутреннюю Gradio-демку с контрактом 97 кадров / 30 fps /
720p. Wan 2.7 и Veo 3.1 Lite отправляются в raw OpenRouter API через Eliza;
нужен `ELIZA_TOKEN`, либо уже настроенный `ANTHROPIC_AUTH_TOKEN`. По умолчанию
используется `https://api.eliza.yandex.net/raw/openrouter/v1`; адрес можно
переопределить через `ELIZA_OPENROUTER_BASE_URL`. Перед реальным запуском нужно
перепроверить актуальные model endpoint metadata и стоимость: `run` создаёт
внешние асинхронные jobs.

Тесты пайплайна не делают сетевых запросов:

```bash
python3 -m unittest scripts/test_video_generation_pipeline.py
```
