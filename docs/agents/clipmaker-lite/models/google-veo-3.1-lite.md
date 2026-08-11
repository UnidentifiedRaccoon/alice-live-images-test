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
- Сохраняй image-grounded действие и один `geometry_invariant` из анализа
  изображения. Если endpoint уже виден в first frame, используй только
  low-amplitude residual continuation или естественное затухание, без нового
  цикла и выхода из endpoint.

### Visibility floor для движения камеры

- Когда camera move является `primary_action`, он должен давать сдержанный, но
  ясно наблюдаемый параллакс уже при обычной скорости воспроизведения. Не
  складывай в одном четырёхсекундном плане `starts still`, `tiny distance`,
  `extremely slow` и раннее `settles to rest`: такая комбинация опускает
  движение ниже perceptual threshold Veo.
- Камера начинает двигаться сразу, сохраняет спокойную равномерную скорость
  большую часть четырёх секунд и замедляется только в короткой финальной фазе.
  `Softer` означает отсутствие рывка и speed ramp, а не near-static output.
- Endpoint называет видимое screen-space изменение относительно focal target:
  foreground reference смещается в кадре и открывает немного больше уже видимого
  соседнего плана. Не ограничивай финал словами `slightly farther` или `small
  parallax change` без наблюдаемого композиционного результата.
- Для `softer`-repair от удачного reference move предпочитай continuous even
  travel без стартовой паузы и рывков. `At normal real-time speed` допустим и
  полезен, если пользователь просит более плавное движение, но не просит
  уменьшить амплитуду. Не превращай `softer` в обязательный composition ceiling:
  верхнюю границу travel добавляй только при явном запросе сохранить framing,
  доли смысловых зон или меньший сдвиг. Pixel-difference и first-to-last SSIM —
  диагностические сигналы, а не художественный вердикт; human review имеет
  приоритет при выборе эталона.
- Разделяй world-space preservation и image-space motion. Шторы или другие
  вторичные элементы могут не анимироваться самостоятельно, но жёсткая мебель и
  архитектура меняют экранное положение вследствие параллакса. Не пиши, что
  `every physical element stays motionless` или `everything remains perfectly
  still` одновременно с camera move; вместо этого сохраняй rigid geometry и
  запрещай только независимую деформацию.
- При `enhancePrompt: true` используй одну положительную camera instruction и
  короткий source-grounded endpoint. Не дублируй preservation полным перечнем
  объектов: enhancer может превратить такой перечень в приоритет заморозки.

### Архитектурный exterior с читаемой глубиной

- Когда source image надёжно показывает крупную статичную архитектуру,
  foreground и несколько планов глубины, используй один небольшой camera move
  как основной источник динамики вместо fixed camera или сильного движения
  окружения. Выбери только одну траекторию: slow push-in, gentle lateral track
  или subtle rising reveal к названному фасаду, башням либо оси двора.
- Растяни траекторию ровно и непрерывно на четыре секунды и дословно укажи
  `at normal real-time speed`. Не используй speed ramp, time-lapse pacing или
  резкое ускорение к endpoint.
- `enhancePrompt: true` может усиливать расплывчатую динамику, поэтому не
  используй `wind wave`, `sweeps across`, `gust`, `rapid` или немотивированное
  `cinematic movement`. Называй малую амплитуду, одну геометрическую траекторию
  и конкретный focal target.
- Если в кадре уже видны деревья или кустарники, они только gently sway in place
  in a light breeze; стволы и точки роста остаются закреплены. Не поручай ветру
  создавать основное действие и не описывай движение через весь кадр.
- Camera move раскрывает только source-grounded параллакс между уже видимыми
  планами. Обе башни, фасады, двор и существующая растительность сохраняют
  идентичность и взаимное расположение до последнего кадра.

## Terminal state и смысловая целостность

- Positive prompt явно формулирует наблюдаемый endpoint последнего кадра, а не
  только развитие движения. После endpoint не начинается второй сюжетный beat.
- `semantic_invariant` удерживается до последнего кадра: естественная динамика
  мимики или позы не разворачивает заданную эмоцию и редакционный смысл.
- `geometry_invariant` сохраняется до последнего кадра: ключевые части остаются
  в той же видимой физической связи.
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

Authored `negative_prompt` всегда и буквально равен `null`; `negativePrompt`
провайдеру не отправляется. Repair и generic tail не используются для negative
prompt. `positive_prompt` занимает не больше двух коротких motion-first
предложений; дальнейшее расширение выполняет `enhancePrompt: true`.

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

`negativePrompt` в provider parameters не отправляется.

## Sources

- [Google Veo image-to-video best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice?hl=en)
