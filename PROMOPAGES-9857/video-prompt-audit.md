# PROMOPAGES-9856 — аудит темпа и prompt fidelity

Проверено 21 июля 2026 года по 15 сохранённым prompt/run-артефактам,
медиаметаданным MP4, текущему каталогу Eliza `/videos/models` и документации
провайдеров.

## Почему Wan 2.2 воспринималась динамичнее

Причина не сводится к качеству одной модели. В первой матрице моделям дали
разные motion plans:

- Wan 2.2 для портрета получила конкретный `one small natural blink`, тогда как
  Wan 2.7 — `very small natural settle` и `barely perceptible breathing`, а Veo
  — только shallow breath;
- у кота Wan 2.7 получила буквальное `slowly lowers`, Veo — `gently`,
  `slightly`, `settles calmly`, а Wan 2.2 — более конкретную последовательность
  «лапа опускается → вес переносится → контакт фиксируется»;
- у воды Wan 2.2 prompt явно связывал падение воды с распространяющейся рябью,
  тогда как другие варианты многократно ослабляли движение словами `gentle`,
  `restrained`, `only slightly` и `calm`.

Один микробит также растягивался пропорционально полной длительности. При
старом окне `15–70%` активная фаза занимала примерно 1,76 секунды у Wan 2.2,
2,2 секунды у Veo и 2,75 секунды у Wan 2.7. При одинаковой амплитуде это само
по себе даёт Wan 2.7 около `0.64×` темпа Wan 2.2.

Исходные Wan 2.7 MP4 не были замедлены контейнером: каждый имел 150 кадров,
30 fps и 5,0 секунды. В актуальном normalized API OpenRouter и
passthrough-схеме AtlasCloud нет параметров `speed`, `fps` или `slow_motion`.
Четыре comparison-ролика финальной итерации используют поддерживаемую native
duration 3 секунды и имеют 90 кадров при тех же 30 fps. Портретный exact replay
по отдельному условию снова использует нативные 5 секунд и 150 кадров. Ни один
из этих файлов локально не ускоряется и не обрезается.

Дополнительный confounder: AtlasCloud по умолчанию включает `prompt_extend`, а
Google Vertex — `enhancePrompt`. Поэтому обе Eliza-модели могли переписывать уже
готовый clipmaker prompt, тогда как legacy Wan 2.2 demo получала текст напрямую.
Это не доказанная отдельная причина slow motion, но неконтролируемая переменная.

## Что показал дословный portrait replay

Для контрольного опыта Wan 2.7 и Veo получили не адаптированные model-specific
варианты, а фактический Wan 2.2 runtime prompt побайтно: тот же Positive и тот
же Negative, объединённые через `\n\nAvoid: ` в строку длиной 1793 символа.
Обеим моделям передан только `first_frame`. Wan 2.7 сгенерирована нативно на
5 секунд, Veo — на 4 секунды, без trimming.

Ни одна модель не повторила крик Wan 2.2. Wan 2.7 держит рот стиснутым и кисти
почти неподвижными, но растягивает единственное зажмуривание примерно с `2.1`
до `3.8 s`. Veo тоже не открывает рот: она дважды моргает и медленно сводит
пальцы к щекам без тряски. Wan 2.2, напротив, раскрывает рот уже примерно к
`0.5–1.1 s` и даёт активное движение рук; убедительного полного blink в её 97
кадрах не найдено.

Это опровергает гипотезу, что именно удачная формулировка portrait prompt дала
Wan 2.2 желаемую динамику. Скопированный текст просит сохранить выражение и
положение рук, выполнить один маленький blink, а в `Avoid:` прямо запрещает
открывать рот, двигать руки и трясти кадр. Wan 2.2 импровизировала вопреки
инструкции; Wan 2.7 и Veo следуют ей заметно точнее. Для воспроизводимого крика
и тряски эти действия нужно описать положительно и убрать противоречащие
negative clauses.

Транспорт контролируется не полностью только для Veo: live route требует
`enhancePrompt: true` и может переписать уже принятый текст. Wan 2.7 отправлена
с `prompt_extend: false`. Другие оставшиеся различия — native duration,
aspect ratio и model prior.

## Исправленный контракт

- Для одного изображения сначала фиксируются общий primary beat,
  `motion_plan_id`, финальное состояние, camera state и deadline. Legacy Wan
  2.2 не перегенерируется и считается grandfathered baseline; строгий контракт
  применяется к новым Wan 2.7/Veo prompts.
- Знакомое физическое микродействие начинается сразу, идёт с `normal real-time
  speed` и завершается не позднее двух секунд. Дополнительная длительность
  расширяет финальный hold, а не замедляет action.
- Динамические negative prompts включают `slow motion` / `slow-motion pacing`,
  `time-stretched motion` и `delayed action`.
- `slowly`, `barely perceptible` и многократные `calm/steady` удалены из
  динамических Wan 2.7/Veo prompts. Статичный finance UI остаётся исключением:
  для него правильный motion plan — locked flat-raster hold.
- Wan 2.7 откалибрована на native `duration=3`: в cat A/B это ускорило контакт
  лапы примерно с `3.0` до `1.5 s`, хотя не устранило temporal dilation во всех
  сценах.
- Когда правильный финал должен буквально совпасть с source frame, source
  может повторяться как поддерживаемый `last_frame`, но это не гарантирует
  статичность промежуточных кадров. В текущей матрице anchor оставлен только у
  Veo UI; из exact portrait replay он удалён для совпадения с Wan 2.2 request.
- Product motion упрощён до общего `tiny surface-tension quiver`; сложная
  формулировка `gravity extends + neck narrows + recoil` сама провоцировала
  нить, падение и неверную жидкостную физику.
- Wan 2.7 отправляется с `prompt_extend: false`. Живой Google/Veo route
  принудительно требует `enhancePrompt: true` и отклоняет `false` до inference,
  поэтому provider rewriting для Veo — известное ограничение, а не
  контролируемый флаг.

## Что сравнивается после перегенерации

Wan 2.2 остаётся legacy baseline без повторного платного запуска. Четыре строки
Wan 2.7/Veo используют model-specific motion wording. Портретная строка —
отдельный exact-text replay с нативными 5/4 секундами и без last frame. Для Veo
обязательный Google enhancer остаётся включённым. Поэтому даже exact-text опыт
не является полной изоляцией model weights: seed, aspect ratio, duration и
provider preprocessing различаются.

Качество проверяется не только через `ffprobe`, но и по кадрам около 0,2, 1,0,
2,0 секунды и в финале: основной beat должен быть уже завершён к раннему
deadline, после чего состояние удерживается без второго действия.

Финальный визуальный результат записан в `video-generation-review.md`.
Текстовые фиксы и native duration заметно улучшили fidelity и темп отдельных
сцен, но prompt deadline остаётся проверяемой гипотезой, а не гарантией API.

## Источники контрактов

- [OpenRouter Video Generation](https://openrouter.ai/docs/guides/overview/multimodal/video-generation)
- [OpenRouter provider-specific options](https://openrouter.ai/docs/cookbook/video-generation/provider-specific-video-options)
- [Alibaba Wan prompt guide](https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt)
- [AtlasCloud Wan 2.7 image-to-video](https://www.atlascloud.ai/models/alibaba/wan-2.7/image-to-video)
- [Google Veo API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
- [Google Veo image-to-video best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice)
