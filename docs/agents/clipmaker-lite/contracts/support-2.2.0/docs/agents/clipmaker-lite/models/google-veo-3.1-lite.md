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
- Сохраняй image-grounded `geometry_invariant` и `identity_invariant`. Если
  endpoint уже виден в first frame, используй residual continuation, затухание
  или camera-only — без полного цикла, реверса и новых props.

### Visibility floor и source-grounded camera

- Когда камера — `motion_owner`, она начинает двигаться сразу, сохраняет
  спокойную равномерную скорость большую часть четырёх секунд и замедляется
  только у финала. Не складывай `starts still`, `tiny distance`, `extremely
  slow` и ранний stop: Veo опустит движение ниже perceptual threshold. `At
  normal real-time speed` допустим, когда помогает удержать непрерывное
  движение без паузы и speed ramp.
- Endpoint называет screen-space результат относительно уже видимого focal
  target: без референсного travel foreground reference смещается примерно от
  5% ширины кадра и открывает немного больше уже видимого соседнего плана.
  Ceiling около 10% добавляй только когда image risk или явная direction требуют
  сохранить framing; не выводи его из слова `softer`.
- Для `softer`-repair от удачного camera move сохрани trajectory, focal target,
  полный travel и непрерывный ровный темп, если direction явно не просит меньшую
  амплитуду. `Softer` означает отсутствие jerk и резкого speed ramp, а не
  near-static output. Pixel-difference и first-to-last SSIM остаются
  диагностикой; художественный выбор подтверждает human review.
- Разделяй world-space preservation и image-space motion. Архитектура, мебель,
  продукты и другие жёсткие объекты не деформируются, но меняют экранное
  положение из-за source-grounded parallax. Не пиши `everything remains
  perfectly still` вместе с camera move.
- `enhancePrompt: true` может расширять сцену. Не используй `wind wave`,
  `sweeps across`, `cinematic movement`, полное перечисление preservation или
  новый reveal за границами исходника. Камера показывает только уже видимую
  глубину; существующая растительность слегка sway in place, roots и count
  остаются фиксированными.
- У camera-primary вторичные fabric, hair, foliage и water остаются явно слабее
  camera motion. Layered curtains source-locked; enhancer не получает billowing
  или opening action.

## Terminal state и смысловая целостность

- Positive prompt явно формулирует наблюдаемый endpoint последнего кадра, а не
  только развитие движения. После endpoint не начинается второй сюжетный beat.
- `semantic_invariant` удерживается до последнего кадра: естественная динамика
  мимики или позы не разворачивает заданную эмоцию и редакционный смысл.
- `geometry_invariant` сохраняет контакт, крепление и жёсткую форму;
  `identity_invariant` удерживает точное число сущностей, конечностей, props,
  labels и деталей.
- Ключевой объект остаётся непрерывно видимым и узнаваемым; камера и действие не
  должны заслонять, уводить из кадра или подменять его.

## UI и people risks

- Для точного текста, UI, chart, table, diagram и screenshot выбери
  `deterministic-compositor`: `execution_mode` равен
  `deterministic-compositor`, а `positive_prompt` равен `null`.
- Для людей сохраняй точное число, конечности и props. Не добавляй контакт с
  лицом, новый предмет, сложное взаимодействие или gait, направление которого
  не доказано source image. При неоднозначности выбери camera-only.
- Articulated ride не выполняет полный arc/rotation; tool не действует без
  видимой руки/контакта. `enhancePrompt` не получает expansive action.

## Negative prompt

Authored `negative_prompt` всегда и буквально равен `null`;
`negativePrompt` не отправляется. Repair и generic tail не используются:
failure преобразуется в positive anchor, visibility floor/composition ceiling
или более безопасную rendering strategy.

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
