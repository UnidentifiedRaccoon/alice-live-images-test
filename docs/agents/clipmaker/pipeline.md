# Clipmaker Pipeline

Используй этот model-agnostic конвейер для каждого изображения отдельно.
Анализ выполняй внутренне и не добавляй его в финальный ответ без явной просьбы.

## 0. Разреши model ID

1. Получи точный `model_id`.
2. Найди его в таблице [README.md](README.md#поддерживаемые-model-id).
3. Загрузи ровно одну соответствующую model-spec.
4. Зафиксируй из неё `target_duration`, prompt-поля, подтверждённые лимиты и
   model-specific правила композиции.

Если ID неизвестен, остановись по
[unknown-model contract](prompt-templates.md#unknown-model-output). Не начинай
анализ prompt, не выбирай параметры по названию и не используй spec другой
модели.

## 1. Зафиксируй факты первого кадра

Определи только подтверждаемое изображением:

```text
Subject        — главный персонаж или объект.
State          — точная поза, действие и фаза действия в первом кадре.
Direction      — направление взгляда, корпуса, движения или взаимодействия.
Anchors        — детали, которые должны остаться узнаваемыми.
Motion sources — видимые элементы, способные двигаться естественно.
Risks          — лицо, руки, конечности, текст, логотипы, инструменты,
                 колёса, отражения и другие хрупкие детали.
Spatial grammar — цельная фото/3D-сцена либо спроектированная плоская
                  макроструктура с независимыми областями.
```

Не угадывай намерение персонажа, содержимое закрытого объекта, продолжение
надписи или событие за границей кадра.

## 2. Назначь scene routing

Сначала попытайся выбрать ровно один `primary_class` из
[scene-modules.md](scene-modules.md). Перед subtype-признаками примени
[границу graphic routing](scene-modules.md#граница-до-graphic-routing): цельный
фото- или 3D-мир маршрутизируется по главному субъекту, а спроектированная
плоская композиция — в `text_interface_collage`. Доминирующий визуальный
сценарий определяется тем, что несёт смысл кадра и требует наибольшего
preservation, а не тематикой статьи, наличием бренда или отдельной надписи.

Если evidence не позволяет честно выбрать один класс либо признаки классов
конфликтуют, не назначай наиболее похожий класс наугад. Отметь runtime routing
как `unresolved` и примени
[общий fallback](scene-modules.md#общий-fallback-для-unresolved-primary-class).
Это служебное состояние, а не одиннадцатый `primary_class`: curated-разметка
каталога по-прежнему обязана содержать ровно один валидный класс.

Пересекающиеся признаки запиши как `scene_tags`. Они могут только:

- усилить anchors;
- добавить релевантный risk или negative fragment.

`scene_tags` не являются входом для выбора primary action, secondary motion или
camera module. Они не создают второй scene profile. Для mixed-сцены сначала
выбери доминирующий класс, затем сохрани только его cross-cutting risks и
anchors как tags.

Если выбран `text_interface_collage` и graphic routing разрешён, дополнительно
назначь:

```text
graphic_kind  — один активный prompt-route;
graphic_kinds — все самостоятельные видимые виды графики, начиная с активного.
```

Используй только controlled vocabulary и правила mixed routing из
[scene-modules.md](scene-modules.md#управляемый-словарь-graphic_kinds).
`graphic_kind` выбирает action policy внутри графического профиля; все
`graphic_kinds` добавляют anchors и формируют candidate negative fragments.
В итоговый negative попадает активный kind и максимум один дополнительный вид
по остаточному бюджету. Добавляй secondary kind только когда это самостоятельная
видимая макроструктура со своими preservation anchors, а не декоративная шкала,
набор thumbnail-картинок или текст внутри контейнера. Для остальных классов эти
поля не создаются.

Считай вход одним плоским растром. Не делай выводов о масках, слоях, DOM,
редактируемой схеме или исходном документе. Если runtime graphic routing
отсутствует, неизвестен или конфликтует, не создавай `graphic_kind` наугад:
отметь routing как unresolved, используй locked flat-raster fallback с Module A
и не извлекай kind из свободного `scene_description`. Не добавляй kind-specific
action или negative clauses. Если пересечение policy нескольких распознанных
kinds пусто, конфликтует или не подтверждено, используй
`ACT_HOLD_AND_SETTLE`, `SEC_NONE` и Module A. Это исключение только для
runtime-анализа; сохранённая разметка `text_interface_collage` обязана иметь
валидные поля routing.

Внешние поля taxonomy и legacy `scene_tags` считай подсказкой, а не источником
истины. Принимай только значения из текущего controlled contract, сверяй их с
изображением и заново выводи preservation/risk tags из видимого evidence.
Свободные или неизвестные значения не должны влиять на routing, action или
camera. Каталог расширяемый: новый класс добавляется отдельным профилем без
изменения этого pipeline.

## 3. Разреши неоднозначность действия

Определи фазу сцены: `before`, `during`, `after` или `still/posed`.

Если возможны несколько трактовок:

1. Используй совместимое направление пользователя.
2. Иначе выбери самое короткое естественное продолжение видимого состояния.
3. При высоком риске выбери settling motion вместо нового действия.

Для графики тип не является intent. Совместимое явное направление должно
назвать видимую цель и одно разрешённое kind-policy действие над ней. Общие
слова вроде «оживи», `dynamic`, `cinematic`, `parallax` или «добавь движения»
недостаточны. Акцент существующего элемента или локальная микродинамика
фотообласти разрешены только таким направлением пользователя. Неясное,
нетаргетированное или несовместимое направление переводит весь растр в hold.
Scroll, click, typing, перестройка данных и reveal отсутствующего состояния
несовместимы с single-frame flat-raster workflow.

В positive prompt можно кратко закрепить трактовку:

```text
The first frame already shows [correct state], not [likely wrong state].
```

Подробные failure modes перенеси в negative prompt и не повторяй их дословно в
обоих блоках.

## 4. Выбери одно законченное действие

Одно действие — один причинно связанный beat с ясным финальным состоянием.
Дыхание, один blink, движение ткани или отражений могут быть вторичной
микродинамикой, но не отдельными событиями.

```text
Start:  The first frame already shows [exact visible state].
Action: [Subject] completes [one small natural action].
Finish: By the final frames, [clear settled state].
```

При resolved primary routing выбирай условный action module из активного scene
profile и заполняй его видимыми деталями кадра. Профиль — меню допустимых
продолжений, а не готовый случайный prompt. При unresolved primary routing не
заимствуй module соседнего класса: используй общий `ACT_HOLD_AND_SETTLE`.

Для `text_interface_collage` с resolved kind routing сначала примени policy
активного `graphic_kind`. Без compatible intent выбери
`ACT_HOLD_AND_SETTLE`. При explicit intent разрешены только
`ACT_GRAPHIC_ACCENT` или `ACT_LOCAL_MEDIA_MICROMOTION` в границах kind-policy;
mixed-графика получает пересечение ограничений всех kinds.
Если routing kind unresolved или безопасное пересечение не доказано, используй
только `ACT_HOLD_AND_SETTLE` без kind-specific действия.

Предпочитай завершение уже начатого жеста, небольшую смену опоры или взгляда,
короткое перемещение с остановкой либо settling motion. Исключай цепочки
действий, старт большого действия с нуля, уход из композиции, появление новых
объектов и финал без наблюдаемого устойчивого состояния.

## 5. Разложи действие по времени

Используй `target_duration` выбранной model-spec. Не подставляй длительность из
памяти или соседнего model ID.

Общий ритм масштабируется пропорционально:

```text
0–15%     exact first-frame continuity; motion starts without a jump
15–70%    one primary action reaches its meaningful phase
70–100%   deceleration, settling and a stable final state
```

Короткая spec требует меньшей амплитуды, а не ускоренного сложного действия.
Более длинная spec даёт больше времени на естественное развитие и settle, но
не разрешает второй beat, смену сцены или вторую камеру. Точные поправки темпа
бери из model-spec.

## 6. Выбери ровно одно состояние камеры

Выбери один модуль A–E из
[prompt-templates.md](prompt-templates.md#camera-modules), следуя routing
активного scene profile либо правилам общего unresolved fallback:

- Module A — locked frame;
- Module B — minimal drift;
- Module C — open-scene glide;
- Module D — front-side drift;
- Module E — landscape glide.

Каждый prompt обязан содержать ровно один модуль A–E. Module A означает
отсутствие движения камеры и тем самым реализует безопасный вариант внутри той
же cardinality. Если активное движение не даёт уверенной пользы, используй A
или B. При любом graphic evidence, хрупком тексте/интерфейсе/геометрии
используй A. При unresolved primary routing Module B допустим только для явно
фотографической безопасной сцены без этих рисков; иначе используй A. Нельзя
смешивать модули или соединять glide с `locked composition`, `no reframing` и
другими конфликтующими командами.

## 7. Добавь вторичную динамику

Бери её только из `Motion sources` и допустимого пула scene profile. Пар, вода,
волосы, ткань, листва, облака, отражения и свет двигаются лишь тогда, когда
соответствующий элемент или физический источник виден в первом кадре.

При unresolved primary routing всегда используй `SEC_NONE`: без активного
профиля видимый источник сам по себе не разрешает secondary motion.

Микродинамика остаётся слабее основного действия. Если основания нет, пропусти
этот слой: статичность безопаснее выдуманного «оживления».

## 8. Собери positive prompt

Для обычной сцены с resolved primary routing примени
[positive template](prompt-templates.md#positive-prompt-template). Для
`text_interface_collage` используй
[flat-raster graphic template](prompt-templates.md#flat-raster-graphic-positive-template),
затем model-specific синтаксис и лимит. При unresolved primary routing используй
обычный template только для явно фотографической сцены; при graphic evidence
используй flat-raster template с общими видимыми anchors, без kind placeholders
и kind-specific обещаний.

Порядок приоритетов:

1. подтверждённые first-frame anchors;
2. kind-specific preservation для resolved плоской графики либо общие видимые
   flat-raster anchors для unresolved routing;
3. одно действие и его финальное состояние;
4. один camera module;
5. только видимая вторичная динамика;
6. краткие realism и temporal-consistency terms.

Если prompt не помещается, сокращай с конца этого списка. Runtime-параметры
обычно передаются отдельно; добавляй их в текст только когда выбранная spec или
интерфейс явно этого требует.

## 9. Собери negative prompt

Проверь в model-spec:

- есть ли отдельное negative-поле;
- как оно называется и куда передаётся;
- подтверждён ли лимит;
- требует ли модель fragments или instructive language.

Для обычной сцены собирай negative в таком бюджете:

1. наиболее вероятное неправильное действие или направление;
2. исчезновение, появление или трансформация anchors;
3. ошибки хрупких деталей из profile и `scene_tags`;
4. один релевантный конфликт камеры;
5. короткий technical tail.

Для flat graphics с resolved kind routing subtype должен действительно улучшать
выбор и не может быть вытеснен общими формулировками:

1. наиболее вероятное неправильное действие или направление;
2. одна или несколько релевантных clauses активного `graphic_kind` —
   обязательный kind-specific блок;
3. при наличии места — релевантные clauses максимум одного secondary kind;
4. только ещё не покрытые ошибки anchors, profile и `scene_tags` без дублей;
5. один релевантный конфликт камеры;
6. короткий technical tail.

Для flat graphics с unresolved kind routing не требуй несуществующий active
kind и не подставляй ближайший subtype. После наиболее вероятного wrong action
выбери только релевантные общие flat-raster failures из
[unresolved fallback](prompt-templates.md#unresolved-flat-raster-negative-fallback),
затем один camera conflict и короткий technical tail. Не используй
kind-specific clauses ни для active, ни для secondary kind.

Kind-fragment — меню comma-separated clauses, а не неделимая строка. Выбирай
только подтверждённые кадром риски: не упоминай CTA или QR без CTA/QR, coastline
без видимой береговой линии, arrows без стрелок. Kind-specific clause заменяет
покрытую им generic/tag clause, а не складывается с ней.

Не включай нерелевантные модули. При жёстком лимите считай весь body, включая
пробелы и пунктуацию, и сокращай в порядке: technical tail → camera conflict →
generic/profile/tag clauses → secondary kind. Затем для resolved routing
сократи активный kind до одной самой важной релевантной clause, но не удаляй
его полностью. Для unresolved routing сохраняй самую важную общую flat-raster
clause. Никогда не обрезай строку вслепую посередине слова или смысла.

## 10. Проверь результат

Перед выдачей убедись:

- точный model ID распознан и загружена соответствующая spec;
- первый кадр описан без домыслов;
- назначен ровно один `primary_class` либо runtime routing явно помечен
  `unresolved` и применён общий fallback без выдуманного класса;
- `scene_tags` влияют только на preservation и negatives;
- для `text_interface_collage` либо назначены валидные `graphic_kind` и
  `graphic_kinds`, либо runtime routing явно unresolved и применён locked
  flat-raster fallback; сохранённая разметка всегда использует первый вариант;
- secondary `graphic_kinds` соответствуют самостоятельным видимым
  макроструктурам, а mixed-policy имеет доказанное безопасное пересечение;
- graphic routing применён к flat raster без допущений о слоях;
- выбран один основной beat, физически правдоподобный для `target_duration`;
- действие завершается и оставляет устойчивый финал;
- использован ровно один непротиворечивый camera module A–E, где A явно
  кодирует отсутствие движения камеры;
- вторичная динамика относится только к видимым источникам;
- positive и negative не противоречат друг другу;
- важные лица, руки, объекты, текст и логотипы защищены;
- подтверждённые model-specific лимиты соблюдены;
- неизвестные ограничения не выданы за факты;
- ответ соответствует final output выбранной spec.
