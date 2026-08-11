# PROMOPAGES-10060 · image 06 · curtain repair experiment

Дата: 2026-08-11  
Agent: `clipmaker-lite`  
Generation contracts: `2.0.8` для A/B/C; `2.1.0` для A₂; `2.1.2` для A₃; `2.1.3` для A₄  
Current planning contract after human review: `2.1.4`  
Матрица: 4 полные постановки × 3 модели + 2 Veo-only repair = 14 primary outputs

## Проверка и бюджет

- При создании каждый planning-run прошёл `provenance.verified: true` своей
  зафиксированной версией контракта (`2.0.8`–`2.1.3`). Текущий contract `2.1.4`
  намеренно не переаттестует исторические bundles как новые.
- SHA-256 изображения: `6dff114510bc3f61b159431269239343690fcd2f95adc0df9d730138b57a94f8`.
- SHA-256 article context: `eaefa3abb2474e097dcb39f52dc38acf108c3a2f489d033de40141d6c1b96f58`.
- Выполнено ровно 14 primary submit, повторных submit не было. Два сетевых read timeout после Veo submit были продолжены по сохранённому provider job ID без новой отправки.
- Локальный accounting envelope: `$0.35 × 14 = $4.90`, operator cap `$6.00`.
- Segmind вернул подтверждённую стоимость Wan 2.2: `$0.18 × 4 = $0.72`.
- OpenRouter jobs не возвращают billing в receipts, поэтому точная общая сумма недоступна; гарантированный accounting maximum остаётся `$4.90`.
- Media contract: 10 `succeeded`, 4 `verification-failed` — все четыре предупреждения относятся к Wan 2.7 (`audio`, `resolution`).

## Постановки

### A · Camera only

Медленный микро-dolly вправо с небольшим push-in вокруг центральной перегородки. Шторы полностью неподвижны.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Wan 2.2 | 3/5 | Ткань стабильна и геометрия в основном сохраняется, но камера проходит значительно дальше запрошенного micro-move. К финалу перегородка начинает доминировать. Требуется снизить амплитуду примерно в 2–3 раза. |
| Wan 2.7 | 2/5 | `micro-dolly` превращён в выраженный проезд. Перегородка сильно увеличивается и частично перекрывает смысловое сравнение зон. Дополнительно output не соответствует media contract. |
| Veo 3.1 Lite | 5/5 | Лучший общий результат. Небольшой чистый параллакс, обе зоны читаются, штора и архитектура стабильны. Рекомендуемый вариант для Veo. |

- [Wan 2.2 MP4](../videos/a-camera-only/wan-2.2/06.mp4)
- [Wan 2.7 MP4](../videos/a-camera-only/wan-2.7/06.mp4)
- [Veo 3.1 Lite MP4](../videos/a-camera-only/veo-3.1-lite/06.mp4)
- [Contact sheets](contact-sheets/)

### A₂ · Softer camera only

Уточнение победившей постановки A: только очень небольшой боковой dolly вправо, без `push-in`, `zoom`, `pan` и `orbit`; движение начинается из покоя и мягко затухает к финалу. Все ткани неподвижны.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Wan 2.2 | 4.5/5 | Самое заметное улучшение относительно A: большой проезд превратился в спокойный малый сдвиг, перегородка больше не захватывает кадр. Ткань и геометрия стабильны. |
| Wan 2.7 | 3/5 | Значительно мягче исходного A, но camera travel всё ещё сильнее запроса и сильнее двух других моделей. Media contract снова не пройден по аудио и разрешению. |
| Veo 3.1 Lite | 1/5 | Практически статичный кадр. Средняя adjacent-frame YAVG — `0.129` против `1.740` у A; first-to-last SSIM `0.966`. Стек ограничений `starts still` + `tiny distance` + полная неподвижность сцены опустил camera motion ниже perceptual threshold. |

- [Wan 2.2 MP4](../videos/a2-softer-camera/wan-2.2/06.mp4)
- [Wan 2.7 MP4](../videos/a2-softer-camera/wan-2.7/06.mp4)
- [Veo 3.1 Lite MP4](../videos/a2-softer-camera/veo-3.1-lite/06.mp4)
- [A vs A₂ contact sheets](contact-sheets/)

### A₃ · Continuous soft camera · human-selected reference

Veo-only проверка исправления near-static: камера начинает движение сразу и идёт `at normal real-time speed`, а финал задан наблюдаемым сдвигом перегородки.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Veo 3.1 Lite | 5/5 | Выбранный человеком удачный пример. Adjacent-frame YAVG `6.197` отражает большой travel, но не резкость: камера начинает движение сразу, идёт непрерывно и без рывков. `At normal real-time speed` здесь даёт нужную уверенную плавность. Метрика амплитуды не должна подменять художественный вердикт. |

- [Veo 3.1 Lite MP4](../videos/a3-veo-visible-soft-camera/veo-3.1-lite/06.mp4)

### A₄ · Bounded soft camera

Финальный Veo-only repair: камера начинает drift с первых кадров, endpoint ограничен примерно 6% ширины кадра, обе смысловые зоны должны сохранить исходный баланс.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Veo 3.1 Lite | 4/5 | Сдержанная альтернатива A₃. Adjacent-frame YAVG `1.082`, обе зоны дольше сохраняют исходный баланс. Подходит, когда явно требуется меньший travel или жёстче удержать framing; по умолчанию не заменяет более выразительный A₃. Media contract пройден. |

- [Veo 3.1 Lite MP4](../videos/a4-bounded-soft-camera/veo-3.1-lite/06.mp4)
- [A / A₂ / A₃ / A₄ contact sheet](contact-sheets/a-through-a4-veo-3.1-lite.jpg)

### B · Camera + soft sheer

Микро-параллакс камеры; вторично движется только нижний край тюля на несколько сантиметров.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Wan 2.2 | 4/5 | Лучший Wan 2.2. Камера движется умереннее, обе зоны остаются читаемыми, штора не становится главным объектом. Запрошенное микродвижение ткани почти игнорируется, что в этом кадре работает в плюс. |
| Wan 2.7 | 2/5 | Снова слишком большой camera travel; формулировки `tiny` и `very small` не удержали амплитуду. Ткань спокойнее исходной генерации, но композиция к финалу перекашивается в сторону перегородки. Media contract не пройден. |
| Veo 3.1 Lite | 1/5 | Критический spatial hallucination: модель создаёт крупную полупрозрачную штору на переднем плане, которая въезжает слева и закрывает кровать. Вариант непригоден. |

- [Wan 2.2 MP4](../videos/b-camera-soft-sheer/wan-2.2/06.mp4)
- [Wan 2.7 MP4](../videos/b-camera-soft-sheer/wan-2.7/06.mp4)
- [Veo 3.1 Lite MP4](../videos/b-camera-soft-sheer/veo-3.1-lite/06.mp4)
- [Contact sheets](contact-sheets/)

### C · Fixed camera + soft sheer

Камера неподвижна; одно почти незаметное движение ограничено нижней третью тюля.

| Модель | Оценка | Результат |
| --- | --- | --- |
| Wan 2.2 | 3/5 | Самый безопасный результат, но почти статичный. Модель в основном игнорирует micro-action. Может служить low-motion baseline, но плохо демонстрирует оживление изображения. |
| Wan 2.7 | 1.5/5 | Ограничение нижней третью не соблюдено: центральная часть тюля снова образует треугольный парус. Появляется нежелательное тёплое свечение за правым окном. Media contract не пройден. |
| Veo 3.1 Lite | 2/5 | Амплитуда меньше исходной генерации, но движется всё полотно, а не нижняя треть. Тюль открывается и деформирует силуэт. Непригодно. |

- [Wan 2.2 MP4](../videos/c-static-soft-sheer/wan-2.2/06.mp4)
- [Wan 2.7 MP4](../videos/c-static-soft-sheer/wan-2.7/06.mp4)
- [Veo 3.1 Lite MP4](../videos/c-static-soft-sheer/veo-3.1-lite/06.mp4)
- [Contact sheets](contact-sheets/)

## Победители

1. **Veo 3.1 Lite: A₃ / continuous soft camera** — выбранный человеком эталон плавного движения; заменяет статичный A₂.
2. **Wan 2.2: A₂ / softer camera only** — лучший Wan после снижения амплитуды и удаления push-in.
3. **Wan 2.2: C / fixed camera** — безопасный low-motion baseline, если важнее сохранность кадра, чем заметная анимация.

Ни один Wan 2.7 вариант не готов к использованию без новой model-specific итерации и решения media-contract проблемы.

## Что это говорит о clipmaker-lite

1. **Для Veo layered curtains должны стать high-risk motion.** После наблюдаемого billowing failure planner должен выбирать camera-only и не возвращать движение ткани даже как secondary action.
2. **`Softer` описывает темп, а не обязательное уменьшение travel.** A₂ показал near-static из-за стека ограничений; A₃ подтвердил, что заметный continuous travel остаётся плавным при ровной скорости без рывков. В contract `2.1.4` `at normal real-time speed` разрешён для Veo, composition ceiling применяется только по явному запросу, а motion-метрики не заменяют human review.
3. **Для Wan camera amplitude нужно задавать модельно.** `micro-dolly`, `tiny arc` и `very small` не ограничивают Wan 2.7 и слабо ограничивают Wan 2.2. Для них нужен менее сильный camera verb либо отдельный tested repair pattern.
4. **Hybrid direction потеряла иерархию.** В planning-run B `structured_intent.primary_action` стал движением шторы, хотя камера должна была быть основным действием. Planner должен явно сохранять primary/secondary hierarchy из пользовательского repair direction.
5. **Нужен first-class variant experiment mode.** Текущий pipeline рассчитан на фиксированную матрицу изображений, а не на несколько постановок одного кадра с общим budget cap. Эксперимент пришлось оркестрировать отдельным coordinator поверх runner.
6. **Wan 2.7 route стабильно нарушает media contract.** Во всех 4/4 outputs запрос содержал `generate_audio: false` и `1080p`, но provider вернул AAC и `1662×1246`. Нельзя просто ослабить проверку: нужно либо исправить adapter/request mapping, либо добавить явный детерминированный normalization stage с отдельным provenance.
7. **Negative prompt не участвовал.** Во всех вариантах он оставлен `null`, чтобы изолировать влияние постановки camera move.

## Рекомендуемая следующая итерация

- Зафиксировать A₃ как reference pattern для Veo camera-only repair; новой Veo-генерации для этого кадра не требуется.
- Для Wan 2.7 отдельно проверить adapter и media contract; не тратить бюджет на художественные варианты до решения транспорта.
- Не анимировать тюль в этом кадре на Veo и Wan 2.7.
