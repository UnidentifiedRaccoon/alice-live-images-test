# Alibaba Wan 2.7 — Clipmaker Lite

Checked: **2026-07-23**.

## Project profile

| Setting | Lite v1 value |
| --- | --- |
| Model ID | `alibaba/wan-2.7` |
| Input | Source image as `first_frame` |
| Duration | `5 s` |
| Resolution | `1080p` |
| Aspect ratio | Source-compatible supported ratio |
| Audio | `generate_audio: false` |
| Last frame | Omitted |
| Prompt expansion | `prompt_extend: true` |

Пять секунд — целевая длительность эксперимента Lite, а не утверждение, что она
лучше других поддерживаемых длительностей. Этот профиль оценивает качество
сцены с включённым provider expansion; он не предназначен для exact-text
cross-model comparison.

## Планирование сцены

- Используй один continuous shot. Не добавляй специальный single-shot marker в
  baseline; официальный `Generate single shot.` становится model-specific repair
  только если тесты показывают cuts или смену сцены.
- Выбери одно действие или физический процесс, который естественно развивается
  почти всю пятисекундную сцену и приходит к читаемому результату ближе к концу.
- Не завершай действие принудительно к двум секундам и не оставляй длинный
  статичный hold.
- Не растягивай мгновенный micro-action в slow motion только ради длительности.
  Лучше выбери более подходящий масштаб того же намерения: непрерывный поворот,
  перенос веса, движение камеры, течение, ветер или постепенную реакцию.
- Используй умеренную амплитуду и ровный темп: действие начинается без длинной
  подготовки, развивается большую часть пяти секунд и приходит к endpoint без
  ускоренного рывка.
- Камера остаётся fixed либо выполняет одно простое мотивированное движение с
  названным focal target. Выбери один camera state на весь shot.
- Prompt описывает motion и camera. Не пересказывай внешность, сцену, свет и
  стиль, уже заданные изображением.
- Пиши коротко и конкретно: provider получает `prompt_extend: true` и может
  расширить формулировку.
- Используй одно-два motion-first предложения и сохраняй image-grounded
  `attention_anchor`, `motion_boundary`, `geometry_invariant` и
  `identity_invariant`. Если endpoint уже виден в first frame, используй
  residual continuation, затухание или camera-only — без нового цикла и
  реверса.
- `prompt_extend: true` может усиливать travel, plume, glare и вторичное
  движение. Задавай source-relative composition ceiling: camera reference
  смещается не больше собственной ширины или примерно 5–10% кадра; mist
  остаётся одним коротким узким cone у видимого nozzle; optical effect остаётся
  внутри target-boundary. Избегай expansive verbs `sweeps across the scene`,
  `billows`, `fills`, `full rotation` и `wide arc`.
- Provider expansion не получает `reveal`, `complete` или `extend` для
  невидимой геометрии. Camera route удерживает `attention_anchor`, не уходит на
  соседнюю дверцу или пустой фон и не создаёт новые фасады, ряды механизма,
  части пола или объекты за source boundary.

## Terminal state и смысловая целостность

- Positive prompt явно называет наблюдаемый финал, который сохраняется в
  последнем кадре. Не завершай текст лишь глаголом процесса и не добавляй второй
  независимый beat.
- `semantic_invariant` не меняется при естественном затухании движения. Эмоция,
  напряжение или редакционный смысл не переходят в противоположное состояние.
- `geometry_invariant` сохраняет контакт, крепление и жёсткую форму;
  `identity_invariant` удерживает точное число сущностей, конечностей, props и
  деталей.
- Ключевой объект остаётся непрерывно видимым, геометрически узнаваемым и связан
  с тем же действием от первого до последнего кадра.

## UI и people risks

- Каждый result имеет `execution_mode: i2v` и непустой `positive_prompt`. Для
  точного текста, UI, chart, table, diagram и screenshot выбери `camera-only`:
  экран или печатная графика остаётся одной жёсткой плоскостью, labels, числа,
  glyphs и controls входят в `motion_boundary`, camera move остаётся bounded и
  не открывает unseen space.
- Для людей сохраняй точное число, конечности и props. Не добавляй контакт с
  лицом, новый предмет, сложное взаимодействие или неоднозначный gait. Когда
  сложный жест не доказан, используй дыхание, моргание, малый поворот головы,
  взгляда или корпуса либо camera-only.
- Articulated ride не выполняет полный arc/rotation. Видимая ось и крепления
  допускают одно малое bounded продолжение в выбранном правдоподобном
  направлении; topology, riders и число seats фиксированы, новые секции не
  появляются.
- Tool не действует без видимой руки/контакта; layered fabric не billow. При
  неоднозначной механике выбери camera-only.
- Статичный продуктовый packshot получает центрированный studio push или одно
  restrained изменение света/камеры; весь набор и labels остаются видимыми,
  продукты не двигаются автономно.
- На стройплощадке без доказанного действия используй плавный
  observer/phone-inspection camera move. Пол, плиты, трещины, инструменты и
  обломки остаются жёсткими и не поднимаются сами.

## Negative prompt

Authored `negative_prompt` всегда и буквально равен `null` и не отправляется.
Repair и generic tail не используются: failure преобразуется в positive anchor,
composition ceiling или более безопасную rendering strategy.

## Runtime fragment

```json
{
  "model": "alibaba/wan-2.7",
  "duration": 5,
  "resolution": "1080p",
  "generate_audio": false,
  "frame_images": ["source as first_frame"],
  "provider": {
    "options": {
      "atlas-cloud": {
        "parameters": {
          "prompt_extend": true
        }
      }
    }
  }
}
```

`negative_prompt` в provider parameters не отправляется.

## Sources

- [Alibaba image-to-video prompt guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt)
