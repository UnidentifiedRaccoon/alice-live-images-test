# Alibaba Wan 2.2 — Clipmaker Lite

Checked: **2026-07-23**.

## Project profile

| Setting | Lite v1 value |
| --- | --- |
| Model ID | `alibaba/wan-2.2` |
| Input | Source image as `first_frame` |
| Planning duration | `3.2 s` |
| Adapter runtime | `97` frames at `30 fps` (`3.233... s`) |
| Resolution | `720p` |
| Aspect ratio | Preserve source ratio within adapter quantization |
| Audio | `generate_audio: false` |
| Last frame | Omitted |
| Provider route | `wan-streamlit` |
| Adapter | `wan-demo` |
| Prompt expansion | Not exposed by this route |

Это активный внутренний маршрут проекта. Он не является OpenRouter-моделью и
не использует пятисекундный runtime публичного Alibaba Wan 2.2 API. Не переноси
в него параметры, лимиты или prompt expansion другого endpoint.

## Планирование сцены

- Создай самостоятельный план именно для 3.2-секундного ролика. Не используй
  prompt, scene plan или хореографию Wan 2.7 как источник.
- Один ролик содержит один continuous shot и одно причинно связанное действие.
  Multi-shot, cuts и второй сюжетный beat не используются.
- Движение начинается без длинной задержки, развивается в естественном темпе и
  приходит к ясному состоянию ближе к финалу. Общего двухсекундного deadline и
  длинного пустого hold нет.
- Выбирай амплитуду, которую можно завершить за 3.2 секунды без ускоренного
  рывка или искусственного slow motion. Для короткого route часто подходит
  одно простое действие небольшой или умеренной амплитуды либо один компактный
  физический процесс. Движение начинается сразу и идёт ровно, без повторных
  жестов.
- Камера остаётся fixed либо выполняет одно минимальное, пространственно
  оправданное движение с названным focal target. Выбери один camera state на
  весь shot; не складывай pan, zoom, orbit и handheld motion.
- Prompt должен быть коротким, но самодостаточным: provider expansion в этом
  route не экспонирован. Ясно укажи действие, скорость, направление и конечное
  состояние, когда без них движение двусмысленно.
- Не включай в prompt runtime-параметры `97 frames`, `30 fps`, codec или seed.
  Они принадлежат machine-owned contract.

## Terminal state и смысловая целостность

- Назови наблюдаемый endpoint прямо в positive prompt и достижи его к последним
  кадрам. Не ограничивайся последовательностью движений и не добавляй после
  endpoint второй beat.
- Сохраняй `semantic_invariant` до последнего кадра. Например, заданная тревога
  остаётся тревогой даже когда движение рук затихает.
- Ключевой объект, которым выполняется или подтверждается действие, остаётся
  непрерывно видимым и узнаваемым. Не планируй выход пипетки, капли, водопада или
  другого смыслового объекта из кадра.

## UI и people risks

- Для UI используй fixed camera и максимум один мягкий блик, pulse или optical
  accent уже существующего элемента. Текст, числа, даты, glyphs, layout, chart
  state, значения, checkbox и другие controls не меняются.
- Для людей исключи контакт рук с лицом, сложное взаимодействие частей тела,
  речь и lip-sync вместе с быстрыми повторными жестами. Используй одно простое
  движение умеренной амплитуды и удерживай заданную эмоцию до финала.

## Negative prompt

В baseline и в матрице PROMOPAGES-9909 `negative_prompt` равен `null`. После
отдельно наблюдаемого failure в будущей итерации можно добавить только короткий
model-specific repair. Не применяй лимит 500 символов из другого Alibaba
endpoint: для внутреннего route он не подтверждён.

Adapter принимает один текст. Если repair существует, generation transport
объединяет его с positive prompt через `\n\nAvoid: `; при `null` отправляется
только positive prompt. Сам Lite возвращает positive и negative раздельно.

## Runtime fragment

```json
{
  "model": "alibaba/wan-2.2",
  "duration_seconds": 3.2,
  "resolution": "720p",
  "aspect_ratios": ["source"],
  "generate_audio": false,
  "frame_inputs": ["first_frame"],
  "provider": "wan-streamlit",
  "adapter": "wan-demo",
  "frames": 97,
  "fps": 30,
  "seed": 1,
  "loop": false,
  "last_frame": null,
  "prompt_expansion": {
    "mode": "not_exposed"
  },
  "negative_prompt_transport": {
    "mode": "combined_prompt",
    "separator": "\n\nAvoid: "
  }
}
```

## Route boundary

Результат считается Wan 2.2 Lite prompt только если этот exact model ID был
выбран до анализа, bundle содержал эту spec, а model-level fingerprint относится
к ней. Отсутствующая или невалидная spec завершает run ошибкой. Fallback на Wan
2.7 и межмодельный replay запрещены.

## Sources

- [Alibaba image-to-video prompt guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt)
- Active project `wan-streamlit` runtime contract: `97` frames, `30 fps`, `720p`.
