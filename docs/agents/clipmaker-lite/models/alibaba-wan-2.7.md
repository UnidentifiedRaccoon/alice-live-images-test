# Alibaba Wan 2.7 — Clipmaker Lite

Checked: **2026-07-22**.

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
- Камера остаётся fixed либо выполняет одно простое понятное движение.
- Prompt описывает motion и camera. Не пересказывай внешность, сцену, свет и
  стиль, уже заданные изображением.
- Пиши коротко и конкретно: provider получает `prompt_extend: true` и может
  расширить формулировку.

## Negative prompt

В baseline `negative_prompt` не отправляется. После наблюдаемого failure можно
добавить несколько конкретных нежелательных результатов, направленных именно на
этот дефект. Не используй стандартный technical tail.

Для текущего AtlasCloud route body должен быть не длиннее 500 символов.

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

Добавляй `negative_prompt` в provider parameters только когда он реально
сформирован.

## Sources

- [Alibaba image-to-video prompt guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt)
