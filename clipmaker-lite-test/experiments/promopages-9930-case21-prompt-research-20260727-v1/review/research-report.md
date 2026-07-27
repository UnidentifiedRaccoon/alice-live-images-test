# Case 21: исследование prompt-вариантов Clipmaker Lite

Дата: 2026-07-27
Задача: PROMOPAGES-9930
Агент: `clipmaker-lite`
Исходник: `PROMOPAGES-9857/articles/21-maier-doctor-zolotoe-vremia/04.png`
SHA-256 исходника: `c42c39e7fd2243c37abe014acc8d901ea5e8751dedd82273cf409cc4b2591b6b`

## Итог

Ни один из семи доступных роликов не реализовал требуемое монотонное
уменьшение фиолетовой ауры. Все результаты остаются исследовательскими
`fidelity-failed` и не должны считаться принятыми production-артефактами.

Лучший диагностический результат — `erosion-negative / Wan 2.7`: короткий
negative repair заметно уменьшил пространственный bloom по сравнению с
baseline, но не устранил начальное усиление цвета и рост ауры. Последний
`opacity-only / Wan 2.7` показал, что проблема не сводится к слову
`contract`: даже запрет изменения геометрии привёл к самому большому облаку.

Консервативный зарезервированный максимум эксперимента — **$2.70 из $3.00**:
$2.20 для пяти stage-1 provider entries и $0.50 для одного stage-2 entry.
Provider receipts не содержат billing metadata, поэтому это верхняя
операторская оценка, а не утверждение о фактическом списании.

## Проверенные гипотезы

| Вариант | Модель | Результат |
|---|---|---|
| Baseline | Wan 2.2 | Большое bokeh-расширение, затем исчезновение |
| Baseline | Wan 2.7 | Аура сильно растёт и темнеет; меняются батарея, шкала и стрелка |
| Monotonic positive | Wan 2.7 | Появляется большой тёмный круг, затем он сжимается |
| Monotonic positive | Wan 2.2 | Provider session потерян после submit; MP4 не получен |
| Outside-in erosion + negative repair | Wan 2.2 | Молекула вращается и деформируется; меняются элементы схемы |
| Outside-in erosion + negative repair | Wan 2.7 | Наименьший bloom, но сначала растут цветовая масса и площадь |
| Motion-only | Veo 3.1 Lite | Сильный фиолетовый bloom, затем спад; square превращён в pillarboxed 16:9 |
| Opacity-only + negative repair | Wan 2.7 | Самый большой bloom: облако перекрывает значительную часть схемы |

## Воспроизводимые метрики

Анализ выполнен `scripts/analyze_clipmaker_lite_case21_motion.py`: по девять
равномерных кадров, нормализация до square 512 px, фиксированный ROI вокруг
молекулы, эвристическая purple mask и сравнение пикселей вне ROI с первым
кадром ролика. Полный отчёт — `motion-metrics.json`.

| Видео | Нарушения монотонности | Purple area: start → max → end | Chroma: start → max → end | Max changed вне ROI |
|---|---:|---:|---:|---:|
| Erosion-negative / Wan 2.7 | 4 | 0.359 → 0.378 → 0.119 | 0.027 → 0.071 → 0.018 | 9.55% |
| Baseline / Wan 2.7 | 6 | 0.359 → 0.836 → 0.164 | 0.027 → 0.151 → 0.013 | 6.87% |
| Monotonic-positive / Wan 2.7 | 6 | 0.352 → 0.894 → 0.078 | 0.026 → 0.128 → 0.003 | 8.06% |
| Motion-only / Veo | 7 | 0.366 → 0.838 → 0.002 | 0.032 → 0.228 → 0.000 | 3.15% |
| Erosion-negative / Wan 2.2 | 7 | 0.372 → 0.521 → 0.512 | 0.031 → 0.050 → 0.047 | 4.94% |
| Opacity-only / Wan 2.7 | 7 | 0.357 → 0.993 → 0.013 | 0.027 → 0.113 → 0.000 | 32.62% |
| Baseline / Wan 2.2 | 7 | 0.367 → 0.738 → 0.001 | 0.032 → 0.058 → 0.000 | 58.03% |

Метрика — диагностическая, не acceptance oracle. Она не распознаёт текст и
химическую структуру, может пропустить reversal между девятью кадрами и не
видит drift первого generated frame относительно исходника. Поэтому ручная
проверка остаётся обязательной.

## Что именно не работает в текущем Clipmaker Lite

### P0: provenance не является контролем качества

`provenance verified: true` надёжно доказывает, какой агент, контракт,
исходник, контекст и prompt создали request. Он ничего не говорит о том,
выполнила ли видео-модель требуемую траекторию. Сейчас эти два значения легко
перепутать.

### P0: траектория задана только естественным языком

В контракте есть свободные строки `primary_action` и `terminal_state`, но нет
машинного требования «площадь и opacity не увеличиваются ни на одном шаге».
Проверяется финальный смысл, а не путь к нему. Поэтому `grow → peak → fade`
может закончиться нужным последним кадром и остаться незамеченным до ручного
review.

### P0: нет editable ROI и frozen region

`semantic_invariant` описывает смысл, а не пиксельные инварианты. Для плотной
инфографики нужны mask/ROI целевого пятна и замороженная область всего
остального. Иначе модели вращают молекулу, меняют батарею, стрелки и шкалу,
несмотря на `pixel-locked` в prompt.

### P0: repair разрешён в authoring contract, но заблокирован baseline bridge

Lite runner и model specs допускают короткий model-specific negative repair
после наблюдаемого сбоя. Native batch loader при этом безусловно требует
`negative_prompt: null` как наследие baseline PROMOPAGES-9909. В эксперименте
пришлось вводить отдельный проверяющий loader. Нужен штатный режим
`observed-repair`, связанный с SHA предыдущего review и typed failure codes.

### P1: provider prompt expansion непрозрачен

Wan 2.7 всегда получает `prompt_extend: true`, Veo — `enhancePrompt: true`, но
expanded prompt не возвращается в receipt. Поэтому нельзя разделить ошибку
Lite prompt и вмешательство enhancer. При этом Wan 2.2 без expansion тоже
создал bloom: expansion усиливает риск, но не является единственной причиной.

### P1: модельные планы недостаточно изолированы

Один authoring-сеанс может видеть несколько model specs и создать близкие
перефразировки вместо действительно независимых стратегий. Надёжнее сначала
получать нейтральный semantic intent, затем запускать отдельную изолированную
model-scoped сессию на каждую модель и связывать receipts агрегатором.

### P1: route и failure semantics недостаточно точны

- Wan 2.7 трижды вернул 1440×1440 с аудиодорожкой при 1080p/no-audio.
- Square-исходник для Veo молча преобразуется в pillarboxed 16:9.
- Явный HTTP 400/403 после POST классифицируется как `submit-unknown`, хотя
  policy/source rejection без job ID следует считать terminal pre-job error.
- Wan upload не имеет bounded upload-only retry; два первых upload получили
  `Broken pipe` до submit.
- Доступность и SHA provider URL не проверяются автоматически перед платным
  POST.

### P1: бюджет и acceptance — только декларации

Бюджет ограничивает число immutable entries, но не является атомарным ledger
фактических списаний. Кроме того, существующий case-21 finalizer считает любой
доступный MP4 accepted даже при `fidelity-failed`. Доступность результата и
приёмка качества должны быть разными полями.

## Как доработать

1. Ввести структурированную траекторию:

   ```json
   {
     "motion_target": "purple_aura",
     "trajectory": {
       "properties": ["area", "opacity"],
       "direction": "decrease",
       "monotonic": true,
       "start_immediately": true,
       "forbid_reversal": true
     }
   }
   ```

2. Для `infographic/text-heavy` требовать target mask SHA, editable ROI,
   frozen region и проверки OCR/edges/colors. Изменение батареи, стрелки,
   шкалы, текста или молекулы должно автоматически блокировать promotion.

3. Добавить post-generation gate: 9–17 кадров, registration, monotonic purple
   area/chroma, outside-ROI changed fraction, OCR exact labels и shape check
   ключевых объектов. `fidelity-failed` не увеличивает
   `accepted_output_count`.

4. Сделать `observed-repair` отдельным versioned контрактом. Repair обязан
   ссылаться на model ID, SHA предыдущего `review.json` и коды вроде
   `trajectory_reversal`, `roi_leak`, `text_mutation`, `state_mutation`.

5. Сохранять resolved provider request и, если возможно, expanded prompt.
   Для Wan 2.7 отдельно сравнить versioned routes `prompt_extend on/off`;
   невозможность выключить Veo enhancer считать явным route risk.

6. Перед POST выполнять trusted-origin GET/HEAD preflight, проверять status,
   redirect policy, MIME, размер и SHA. Ввести typed outcomes
   `source-rejected-before-job`, `policy-rejected-before-job`,
   `auth-rejected-before-job`, `rate-limited`, `submit-ambiguous`,
   `provider-terminal-failed`.

7. Ввести атомарный budget ledger: worst-case reservation до POST, источник
   цены, upstream retry policy, release только при доказанном отсутствии job.

8. Для строгой инфографики использовать детерминированный masked compositor
   как production route. Generative I2V здесь полезен как исследование, но не
   даёт требуемой сохранности даже после трёх разных prompt-механизмов.

## Решение по case 21

В демке можно показать по одному доступному ролику каждой модели с явным
`Visual review · fidelity failed`, чтобы результат исследования не потерялся.
При этом `available_output_count` должен быть 3, а `accepted_output_count` — 0.
Для production-публикации этой анимации рекомендуется deterministic masked
compositor либо новый model route, прошедший автоматический temporal/ROI gate.
