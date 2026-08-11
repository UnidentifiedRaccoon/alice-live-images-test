# Alibaba Wan 2.2 — Clipmaker Lite

Checked: **2026-08-05**.

## Project profile

| Setting | Lite v1 value |
| --- | --- |
| Model ID | `alibaba/wan-2.2` |
| Input | Public source image URL as `first_frame` |
| Planning duration | `5 s` |
| Observed output | `150` frames at `30 fps` |
| Resolution | `720p` |
| Aspect ratio | Preserve source ratio within provider quantization |
| Audio | `generate_audio: false` |
| Gateway | `eliza` |
| Provider | `segmind` |
| Provider model | `segmind/wan-2.2-i2v-flash` |
| Adapter | `eliza-segmind` |
| Prompt expansion | `prompt_extend: false` |

Это канонический внутренний маршрут Lite для Wan 2.2. Он выполняет один
синхронный запрос к Eliza/Segmind и возвращает binary MP4. Маршрут не использует
DOD, асинхронный `/videos`, Gradio, live discovery или fallback на другую модель.
Публичный source URL перед submit перечитывается и сравнивается с frozen
SHA-256 исходника. Сразу после успешного preflight и до единственного
неидемпотентного POST pipeline сохраняет durable `submitting` guard. Ошибка после
этого guard получает статус `submit-unknown` и никогда не повторяется
автоматически.

## Планирование сцены

- Создай самостоятельный план именно для пятисекундного ролика. Не используй
  prompt, scene plan или хореографию Wan 2.7 как источник.
- Один ролик содержит один continuous shot и одно причинно связанное действие.
  Multi-shot, cuts и второй сюжетный beat не используются.
- Движение начинается без долгой задержки, развивается в естественном темпе и
  достигает наблюдаемого финала к последним кадрам. После финала допустим только
  короткий спокойный hold или остаточное движение, но не новый beat.
- Выбирай умеренную амплитуду, которую можно естественно завершить за пять
  секунд. Избегай повторных быстрых жестов, искусственного slow motion и резких
  ускорений.
- Камера остаётся fixed либо выполняет одно минимальное пространственно
  оправданное движение с названным focal target. Выбери один camera state на
  весь shot; не складывай pan, zoom, orbit и handheld motion.
- Prompt должен быть коротким и самодостаточным: `prompt_extend` принудительно
  выключен. Используй одно-два коротких motion-first предложения. Ясно укажи
  действие, скорость, направление и конечное состояние, когда без них движение
  двусмысленно.
- Сохраняй image-grounded действие и один `geometry_invariant` из анализа
  изображения. Если endpoint уже виден в first frame, используй только
  low-amplitude residual continuation или естественное затухание, без нового
  цикла и выхода из endpoint.
- Не включай в prompt `150 frames`, `30 fps`, resolution, codec, watermark или
  seed. Это machine-owned runtime.

## Terminal state и смысловая целостность

- Назови наблюдаемый endpoint прямо в positive prompt и достигни его к
  последним кадрам. Не ограничивайся перечислением движений и не добавляй после
  endpoint второй beat.
- Сохраняй `semantic_invariant` до последнего кадра. Например, заданная тревога
  остаётся тревогой даже когда движение рук затихает.
- Сохраняй `geometry_invariant` до последнего кадра: видимая связь ключевых
  частей не разрывается и не перестраивается в физически другую сцену.
- Ключевой объект, которым выполняется или подтверждается действие, остаётся
  непрерывно видимым и узнаваемым. Не планируй выход пипетки, капли, водопада или
  другого смыслового объекта из кадра.

## UI и people risks

- Для UI используй fixed camera и максимум один мягкий блик, pulse или optical
  accent уже существующего элемента. Текст, числа, даты, glyphs, layout, chart
  state, значения, checkbox и другие controls не меняются.
- Для people исключи контакт рук с лицом, сложное взаимодействие частей тела,
  речь и lip-sync вместе с быстрыми повторными жестами. Используй одно простое
  движение умеренной амплитуды и удерживай заданную эмоцию до финала.

## Negative prompt

Authored `negative_prompt` всегда и буквально равен `null`; model-specific
negative-prompt repair не используется. `positive_prompt` остаётся
самодостаточным и занимает не больше двух коротких motion-first предложений.

На generation transport positive и negative остаются раздельными полями.
Segmind получает строковый параметр `negative_prompt`; authored `null`
детерминированно сериализуется как пустая строка `""`, а не как JSON `null`.

## Runtime fragment

```json
{
  "model": "alibaba/wan-2.2",
  "duration_seconds": 5,
  "resolution": "720p",
  "aspect_ratios": ["source"],
  "generate_audio": false,
  "frame_inputs": ["first_frame"],
  "gateway": "eliza",
  "provider": "segmind",
  "provider_model_id": "segmind/wan-2.2-i2v-flash",
  "adapter": "eliza-segmind",
  "synchronous": true,
  "automatic_retry": false,
  "frames": 150,
  "fps": 30,
  "seed": 220214,
  "watermark": false,
  "prompt_expansion": {
    "parameter": "prompt_extend",
    "value": false
  },
  "negative_prompt_transport": {
    "mode": "separate_field",
    "parameter": "negative_prompt",
    "null_serialization": "empty_string"
  }
}
```

## Route boundary

Результат считается Wan 2.2 Lite prompt только если exact model ID выбран до
анализа, bundle содержал эту spec, а model-level fingerprint относится к ней.
Отсутствующая или невалидная spec завершает run ошибкой; fallback на Wan 2.7 и
межмодельный replay запрещены.

Routine generation разрешён только через frozen registry endpoint
`/segmind/v1/wan-2.2-i2v-flash`. Pipeline не запрашивает каталоги моделей,
`/videos/models`, `/gradio_api/info` или `/config`. Один route pool имеет
консервативную capacity `1`.

## Sources

- Локально подтверждённый request/response receipt:
  `PROMOPAGES-9935/14-miuz-modnye-sergi/01.run.json`.
- Воспроизводимый synchronous transport:
  `scripts/segmind_wan22_case14.py`.
