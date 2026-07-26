# Google Veo 3.1 Lite — Clipmaker Lite

Checked: **2026-07-23**.

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
- Используй одно действие умеренной амплитуды: оно начинается без длинной
  задержки, развивается в ровном темпе и достигает читаемого endpoint у конца
  четырёхсекундного shot.
- Сосредоточь positive prompt на camera movement, subject animation и видимом
  environmental motion. Используй общие ссылки вроде `the subject` или `the
  woman`, когда идентичность уже задана source image.
- Не повторяй описание персонажа, фона, освещения и стиля: source image уже
  задаёт их, а redundant prose может ослабить motion.
- Камера остаётся fixed либо выполняет одно ясное мотивированное движение с
  названным focal target; выбери один camera state, вся сцена остаётся одним
  shot.
- Дай enhancer короткий, конкретный и непротиворечивый motion plan.

## Terminal state и смысловая целостность

- Positive prompt явно формулирует наблюдаемый endpoint последнего кадра, а не
  только развитие движения. После endpoint не начинается второй сюжетный beat.
- `semantic_invariant` удерживается до последнего кадра: естественная динамика
  мимики или позы не разворачивает заданную эмоцию и редакционный смысл.
- Ключевой объект остаётся непрерывно видимым и узнаваемым; камера и действие не
  должны заслонять, уводить из кадра или подменять его.

## UI и people risks

- Для UI используй fixed camera и максимум один мягкий блик, pulse или optical
  accent существующего элемента. Текст, числа, даты, glyphs, layout, chart
  state, значения, checkbox и controls остаются исходными.
- Для людей исключи контакт рук с лицом, сложное взаимодействие частей тела и
  быстрые повторные жесты вместе с речью или lip-sync. Используй одно простое
  движение умеренной амплитуды и явно удерживай эмоцию до финала.

## Negative prompt

В baseline и в матрице PROMOPAGES-9909 `negative_prompt` равен `null`, поэтому
`negativePrompt` не отправляется. После отдельно наблюдаемого failure в будущей
итерации перечисляй только связанные с ним нежелательные объекты, артефакты или
motion outcomes короткими noun phrases. Не используй инструкции, построенные
вокруг `no`, `don't` или `do not`, и не добавляй generic technical tail.

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
