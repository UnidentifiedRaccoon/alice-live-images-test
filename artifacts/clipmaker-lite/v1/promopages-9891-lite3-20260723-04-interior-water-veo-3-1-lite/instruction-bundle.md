# Clipmaker Lite instruction bundle

Agent ID: `clipmaker-lite`  
Contract version: `1.2.1`

Use only the instructions contained in this bundle for this planning run. Do not load or fall back to another clipmaker contract.

## Base instruction

# Clipmaker Lite

Clipmaker Lite — отдельный экспериментальный агент для коротких
image-to-video-сцен. Он использует изображение, текст статьи и точное место
изображения в статье, а затем готовит независимый scene plan и prompt для каждой
модели.

Канонический ID этого агента — `clipmaker-lite`. Он не является режимом другого
агента и не переключается на него при ошибке.

## Когда использовать

Используй Clipmaker Lite, когда важны:

- смысл изображения внутри статьи;
- короткий и естественный motion-first prompt;
- независимая адаптация сцены к длительности каждой модели;
- model-specific расширение prompt на стороне провайдера, когда маршрут его
  действительно экспонирует;
- быстрая экспериментальная итерация без scene taxonomy и больших шаблонов.

## Поддерживаемые модели v1

| Model ID | Длительность Lite |
| --- | ---: |
| `alibaba/wan-2.2` | 3.2 секунды |
| `alibaba/wan-2.7` | 5 секунд |
| `google/veo-3.1-lite` | 4 секунды |

`alibaba/wan-2.2` — активная самостоятельная Lite-ветка через внутренний
`wan-streamlit` route. Она получает собственный scene plan и prompt для 3.2
секунды; prompt другой модели не используется. Этот маршрут не экспонирует
управляемый prompt expansion, поэтому его prompt должен быть самодостаточным.

## Изолированный запуск

Только результат из отдельного runner считается выполненным Clipmaker Lite:

```bash
python3 scripts/clipmaker_lite_runner.py prepare \
  --run-id <run-id> \
  --image <workspace-relative-image> \
  --context <workspace-relative-content.json> \
  --image-id <image-id> \
  --model <exact-model-id> \
  --direction "<optional user direction>"
```

Runner проверяет machine-readable [contract.json](contract.json), загружает по
allowlist только этот README и выбранные Lite model specs, а затем создаёт
`artifacts/clipmaker-lite/v1/<run-id>/instruction-bundle.md`. Анализ выполняется
только по этому bundle, исходному изображению и указанному `content.json`.

Затем runner сам запускает отдельный ephemeral Codex-сеанс в read-only sandbox,
передаёт ему bundle, прикреплённое изображение и article JSON и захватывает
structured response. Абсолютный путь, SHA-256 и версия исполняемого Codex
зафиксированы в contract; подмена через `PATH` не принимается.

```bash
python3 scripts/clipmaker_lite_runner.py run \
  --run-id <run-id> \
  --allow-external-processing
```

Флаг обязателен: на этом шаге изображение и текст статьи отправляются в Codex
для анализа. Без явного разрешения runner не начинает внешний вызов.

Внешний или вручную созданный `draft.json` не принимается: runner требует
собственный execution receipt, связанный с SHA-256 prompt, bundle, входов и
ответа, а также непустой Codex thread ID. Модель получает инструкцию не вызывать
инструменты; если JSONL-поток фиксирует любой tool event, весь run отклоняется и
`result.json` не создаётся. У Codex CLI нет используемого здесь отдельного
переключателя, который заранее удаляет все инструменты, поэтому это fail-closed
проверка события после запуска, а не обещание об их физической недоступности.

После выполнения проверь attestation:

```bash
python3 scripts/clipmaker_lite_runner.py provenance --run-id <run-id>
```

Результат считается Lite только при `verified: true`. Runner сам добавляет
runtime и provenance в `result.json`; поля `producer`, `runtime`, fingerprint и
execution identity не пишет модель. Любая ошибка завершается внутри этого route
без fallback. Ответ также явно содержит
`verification_scope: trusted-workspace-route` и
`cryptographically_signed: false`.

Это проверка идентичности маршрута, а не тест качества prompt: её можно выполнять
автоматически для каждого артефакта без повторной генерации видео. Она рассчитана
на доверенный checkout и неизменённый runner. Пользователь с правом переписать
runner, contract и все артефакты workspace теоретически может подделать
неподписанный локальный receipt; защита от такого противника потребовала бы ключ
подписи вне workspace.

## Вход

Обязательны:

1. одно изображение;
2. контекст статьи: как минимум заголовок и релевантный текст;
3. положение изображения: обложка или body, caption и соседние смысловые блоки.

Список `model_id` опционален: можно запросить одну, несколько или все три
поддерживаемые модели. Если список не указан, подготовь отдельный вариант для
каждой модели v1.

Опционально пользователь может задать действие, настроение, движение камеры или
элемент, который важно подчеркнуть. Направление принимается только если оно не
противоречит видимому кадру и смыслу статьи.

Для неизвестного ID не подбирай похожую модель.

### Контекст PromoPages

Если доступен `PROMOPAGES-9884/articles/<article-id>/content.json`, используй его
как предпочтительный источник контекста:

- найди нужный `image`-блок по `manifest_file_path`, `file` или `image_id`;
- прочитай `title`, `lead`, `caption`, `role` и полный порядок `blocks`;
- выдели ближайшие содержательные блоки до и после изображения;
- учитывай общий смысл статьи, но трактуй роль изображения прежде всего по его
  локальному окружению.

Изолированный runner v1 принимает `content.json` только из зафиксированного
context root: это позволяет однозначно связать изображение с его позицией и
зафиксировать SHA-256 обоих входов.

В текущем наборе PromoPages изображение находится в
`PROMOPAGES-9857/articles/<article-id>/<file>`, а соответствующий контекст — в
`PROMOPAGES-9884/articles/<article-id>/content.json`. Runner требует точное
равенство этим нормализованным путям из contract и полному
`manifest_file_path`; совпадения имени или суффикса недостаточно.

## Четыре шага

```text
image evidence
+ article meaning and image position
-> short shared scene brief
-> independent duration-aware plan for each model
-> concise model prompt + provider prompt expansion
```

Общая scene brief задаёт смысл и видимое начало, но не фиксирует одинаковое
движение, камеру или тайминг для всех моделей. Wan и Veo могут получить разные
действия или разную амплитуду, если это лучше использует их длительность и при
этом сохраняет одну редакционную идею.

### 1. Анализ изображения

Коротко зафиксируй главный объект, его текущее состояние и направление,
композицию, реально подвижные элементы и одну-две смысловые детали. Не составляй
полный inventory и не классифицируй сцену. Отмечай качество входа только когда
видимый дефект действительно ограничивает анимацию.

### 2. Анализ контекста

Определи тезис статьи и функцию изображения именно в этом месте. Для body image
сильнее всего учитывай caption, ближайший содержательный блок до изображения,
ближайший блок после и heading текущего раздела. Для cover используй title, lead
и первый смысловой блок.

Контекст выбирает акцент и настроение среди видимых возможностей, но не добавляет
объекты или события, которых нет на изображении.

### 3. Base scene

В нескольких предложениях опиши видимое начало, редакционный смысл и одно
непрерывное изменение, которое их связывает. Это база для моделей, а не runtime
prompt и не общая хореография. Не назначай здесь duration, deadline, амплитуду
или камеру.

При планировании рассмотри только релевантные элементы: состояние или движение
камеры, одно действие главного объекта, видимое secondary motion, скорость и
ясное конечное состояние. Это checklist, а не обязательный prompt template.

### 4. Независимый план для каждой модели

Загрузи spec точного model ID и заново выбери действие, амплитуду, темп, камеру
и финал под его duration. Варианты сохраняют один редакционный смысл, но могут
различаться по хореографии. Не копируй prompt другой модели с заменённой
длительностью.

Каждая запись `models` создаётся только по spec собственного `model_id`.
Межмодельный replay, `prompt_source_model_id`, fallback на другую модель и
заимствование готового prompt запрещены. Если spec выбранной модели невозможно
загрузить или проверить, заверши этот route ошибкой.

Нативная длительность — пространство для развивающегося действия. Оно может
иметь подготовку, основную фазу и естественное затухание, если всё остаётся одним
причинным событием. Если micro-action заканчивается слишком рано, выбери другой
масштаб того же намерения или другой единый процесс; не заполняй остаток длинным
hold и не добавляй второй beat.

## Основные правила

- Изображение задаёт внешность, композицию, освещение и стиль. Не пересказывай
  их в prompt без конкретной причины.
- Контекст статьи выбирает смысловой акцент и настроение, но не доказывает
  наличие объекта или события, которого нет в кадре.
- Один ролик — один непрерывный shot и одно основное действие. Multi-shot не
  используется.
- Камера либо неподвижна, либо выполняет одно понятное движение.
- Вторичное движение добавляется только для видимого элемента и не превращается
  во второй сюжетный beat.
- Описывай наблюдаемые движения: направление, скорость, интенсивность и
  физический результат вместо слов `beautiful`, `dynamic` или `cinematic` без
  конкретики.
- Планируй действие под полную нативную длительность модели. Нет общего deadline
  в две секунды и нет длинного пустого hold после раннего завершения.
- Финальное состояние должно возникать естественно ближе к концу ролика. Перед
  ним могут идти развитие, продолжение или затухание того же действия.
- Не растягивай слишком короткое действие искусственно. Выбери действие или
  непрерывный физический процесс, которому естественно хватает заданной
  длительности.
- Не добавляй generic preservation prose, generic quality tail или negative
  prompt «на всякий случай». В baseline negative отсутствует; добавляй
  model-specific repair только после наблюдаемого failure.
- Не используй фиксированный prompt template. Структуру добавляй только после
  сравнительного теста, который показал её пользу для конкретной модели или типа
  входа.

## Выход

Верни structured response с полями
`schema_version`, `job_id`, `image_reading`, `article_context`, `base_scene` и
`models`. Каждый элемент `models` содержит точный `model_id`, свободно написанные
`scene_plan` и `positive_prompt`; `negative_prompt` равен `null`, кроме repair
для уже наблюдаемого failure. Runner захватывает этот ответ как `draft.json`.
Поля runtime и provenance запрещены и добавляются только после проверки
execution receipt.

```json
{
  "schema_version": 1,
  "job_id": "<prepared run-id>",
  "image_reading": ["<visible observation>"],
  "article_context": "<image role and editorial focus>",
  "base_scene": "<shared semantic continuation>",
  "models": [
    {
      "model_id": "<exact selected model ID>",
      "scene_plan": "<duration-aware action, camera, tempo and ending>",
      "positive_prompt": "<final English prompt>",
      "negative_prompt": null
    }
  ]
}
```

Это транспортная JSON-схема, а не шаблон prompt. Формулировки сцены и prompt
каждый раз создаются заново по изображению и контексту.

В output нет полей источника prompt или fallback-модели: runner принимает только
собственный результат каждой выбранной ветки.

## Что отсутствует намеренно

- scene taxonomy, routing и предустановленные action/camera modules;
- общий motion plan между моделями;
- multi-shot, cuts и несколько сцен;
- обязательный last frame;
- audio и dialogue в первой версии;
- универсальный positive или negative template;
- автоматический запуск генерации: Lite v1 сначала готовит план и prompts для
  тестовой матрицы.

## Selected model spec: `google/veo-3.1-lite`

# Google Veo 3.1 Lite — Clipmaker Lite

Checked: **2026-07-22**.

## Project profile

| Setting | Lite v1 value |
| --- | --- |
| Model ID | `google/veo-3.1-lite` |
| Input | Source image as `first_frame` |
| Duration | `4 s` |
| Resolution | `1080p` |
| Aspect ratio | Source-compatible `16:9` or `9:16` |
| Audio | `generate_audio: false` |
| Last frame | Omitted |
| Prompt expansion | `enhancePrompt: true` |

`enhancePrompt: true` обязателен для текущего Google Vertex route. Lite
использует это ограничение как автоматическое расширение и не предназначен для
exact-text cross-model comparison.

## Планирование сцены

- Выбери один focused moment, который естественно развивается в течение четырёх
  секунд и достигает финального состояния ближе к концу.
- Не используй общий двухсекундный deadline и не добавляй отдельный статичный
  hold как наполнение остатка.
- Четырёхсекундный вариант может быть короче, быстрее или иметь меньшую
  амплитуду, чем Wan-вариант. Не копируй Wan prompt дословно.
- Сосредоточь positive prompt на camera movement, subject animation и видимом
  environmental motion. Используй общие ссылки вроде `the subject` или `the
  woman`, когда идентичность уже задана source image.
- Не повторяй описание персонажа, фона, освещения и стиля: source image уже
  задаёт их, а redundant prose может ослабить motion.
- Камера остаётся fixed либо выполняет одно ясное движение; вся сцена остаётся
  одним shot.
- Дай enhancer короткий, конкретный и непротиворечивый motion plan.

## Negative prompt

В baseline `negativePrompt` не отправляется. После наблюдаемого failure
перечисляй только связанные с ним нежелательные объекты, артефакты или motion
outcomes короткими noun phrases. Не используй инструкции, построенные вокруг
`no`, `don't` или `do not`, и не добавляй generic technical tail.

Подтверждённого числового лимита для текущего route нет; это не повод писать
длинный negative prompt.

## Runtime fragment

```json
{
  "model": "google/veo-3.1-lite",
  "duration": 4,
  "resolution": "1080p",
  "generate_audio": false,
  "frame_images": ["source as first_frame"],
  "provider": {
    "options": {
      "google-vertex": {
        "parameters": {
          "enhancePrompt": true
        }
      }
    }
  }
}
```

Добавляй `negativePrompt` в provider parameters только когда он реально
сформирован.

## Sources

- [Google Veo image-to-video best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice?hl=en)
