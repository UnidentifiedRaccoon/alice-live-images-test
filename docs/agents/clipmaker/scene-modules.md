# Clipmaker Scene Modules

Этот файл переводит таксономию визуальных сцен в переиспользуемые модули для
clipmaker. Он дополняет [pipeline.md](pipeline.md) и использует определения камер
A–E из [prompt-templates.md](prompt-templates.md#camera-modules), не переопределяя
их. Здесь нет runtime-настроек, готовых prompts и привязки к конкретной модели.

## Контракт классификации

Для каждого изображения выбери ровно один `primary_class` из канонической
[таксономии PROMOPAGES-9857](../../../PROMOPAGES-9857/articles/taxonomy.md) по
доминирующему визуальному сценарию:

```text
portrait_closeup
people_action
product_still_life
food
animal
vehicle_mechanism
interior
architecture_place
nature_open_scene
text_interface_collage
```

`primary_class` отвечает на вопрос «что определяет сцену и её основное
движение». `scene_tags` не создают второй класс и не описывают тему публикации.
Они отмечают только сквозные anchors и риски, которые усиливают preservation и
negative constraints. Состояние действия и источники движения остаются в
first-frame evidence и не кодируются тегами.

Если в кадре есть признаки нескольких классов:

1. Выбери класс субъекта, потеря или деформация которого сильнее всего разрушит
   смысл кадра.
2. Сохрани пересекающиеся признаки через управляемые `scene_tags`.
3. При равном весе выбери более хрупкий профиль: текст и интерфейс важнее
   предметки; лицо важнее предмета в руке; транспортный салон важнее общего
   интерьера.
4. Не используй `scene_tags` для обхода ограничений выбранного профиля.

## Управляемый словарь `scene_tags`

Используй только значения из таблиц ниже. Значения записываются в
`lower_snake_case`, без дублей. Добавляй тег только тогда, когда он усиливает
конкретный anchor, risk или negative fragment. Теги не выбирают primary action,
secondary motion или camera module и не разрешают модуль другого профиля.

Свободные описания объектов, бренды, профессии, виды животных, названия еды и
локаций остаются во внутреннем разборе кадра, но не становятся тегами. Новый тег
добавляется в словарь только вместе с preservation или negative-правилом,
которое его потребляет хотя бы в одном профиле.

### Композиция

| Tag | Семантика |
| --- | --- |
| `close_framing` | Лицо, рука, предмет или деталь близки к границам кадра. |
| `wide_environment` | Пространство и отношения планов важны наравне с субъектом. |
| `overhead_flat_lay` | Верхняя точка и плоская раскладка требуют сохранения геометрии. |
| `cropped_subject` | Значимая часть субъекта уже обрезана исходной рамкой. |
| `partial_occlusion` | Части субъекта скрыты другим объектом и не должны достраиваться. |
| `shallow_depth_of_field` | Фокус и существующее размытие являются anchors композиции. |
| `layered_depth` | Отношения переднего, среднего и заднего планов являются anchors композиции. |
| `centered_symmetry` | Центральная симметрия должна остаться неизменной. |
| `stable_horizon` | Линия горизонта является хрупким геометрическим anchor. |
| `strict_verticals` | Вертикали, фасады, мебель или рамки не должны изгибаться. |
| `composite_layout` | Кадр состоит из самостоятельных панелей или графических фрагментов. |

### Anchors и риски

| Tag | Семантика |
| --- | --- |
| `face_identity` | Личность и пропорции видимого лица критичны. |
| `multiple_people` | Нужно сохранить число, позиции и различимость нескольких людей. |
| `crowd` | Большое число частично перекрытых людей создаёт риск слияния и дублирования. |
| `hands_visible` | Кисти, пальцы, хват или жест являются хрупкими anchors. |
| `hand_object_interaction` | Хват, контакт руки с предметом и взаимное положение должны сохраняться. |
| `readable_text` | Видимый текст должен сохранить содержание и читаемость. |
| `logo_or_label` | Логотип, этикетка или маркировка должны остаться узнаваемыми. |
| `interface_content` | Экран, элементы управления и их расположение нельзя перерисовывать. |
| `small_object` | Небольшой значимый объект легко исчезает, дублируется или меняет форму. |
| `fine_geometry` | Тонкие кромки, инструменты, украшения или детали механизма хрупки. |
| `repeating_elements` | Количество и ритм повторяющихся объектов должны сохраняться. |
| `reflection` | Отражение должно оставаться связано с исходным объектом и светом. |
| `transparent_material` | Стекло, жидкость или прозрачная упаковка должны сохранить материал. |
| `liquid_surface` | Объём, граница и контакт поверхности жидкости должны сохраняться. |
| `wheels_visible` | Форма колёс и их вращение должны быть согласованы с движением. |
| `animal_limbs_visible` | Число, перекрытия и контакты лап или ног должны сохраняться. |
| `food_components` | Состав, количество и раскладка ингредиентов являются anchors. |

### Динамические anchors и риски

| Tag | Семантика |
| --- | --- |
| `hair_visible` | Причёска, длина и контур волос должны сохраняться без придуманного ветра. |
| `fur_visible` | Рисунок, длина и контур шерсти должны сохраняться. |
| `fabric_visible` | Форма, складки и контакт видимой ткани являются anchors. |
| `foliage_visible` | Форма и количество заметной листвы не должны меняться. |
| `clouds_visible` | Форма облаков и исходная погода должны оставаться узнаваемыми. |
| `water_visible` | Берег, уровень, объём и отражения видимой воды должны сохраняться. |
| `steam_visible` | Уже видимый пар нельзя усиливать или превращать в новый источник. |
| `screen_glow_visible` | Свечение экрана не должно менять его контент или состояние. |
| `light_shadow_visible` | Направление света и исходный рисунок теней являются anchors. |

Примеры нормализации metadata, не prompts:

- `animal+textile` → `primary_class: animal` плюс `fabric_visible` и, если это
  видно, `partial_occlusion`;
- `vehicle+interface+text` → `primary_class: vehicle_mechanism` плюс
  `interface_content`, `readable_text` и релевантные геометрические risks;
- `architecture+water+lights` → `primary_class: architecture_place` плюс
  `water_visible`, `light_shadow_visible`, `stable_horizon` и
  `strict_verticals`;
- теги вроде `cat`, `suv`, `kitchen`, название бренда или свободная русская фраза
  не входят в управляемый словарь.

## Переиспользуемые motion modules

Выбери один primary action module. Secondary modules опциональны и не становятся
отдельными сюжетными beats.

### Primary action modules

| Module | Условие и роль |
| --- | --- |
| `ACT_HOLD_AND_SETTLE` | Сохранить устойчивое состояние; дать только естественное затухание уже видимой микродинамики. |
| `ACT_FINISH_VISIBLE_ACTION` | Завершить финальную фазу действия, явно начатого в первом кадре, и стабилизировать результат. |
| `ACT_MICRO_POSE` | Сделать одно малое изменение взгляда, головы, опоры или выражения и вернуться к устойчивой позе. |
| `ACT_SHORT_DIRECTED_MOTION` | Коротко продолжить однозначно видимое направление без смены маршрута и затем стабилизировать движение. |
| `ACT_LOCAL_PHYSICS` | Завершить локальное движение уже видимой капли, жидкости, пара, света или подвижной детали. |
| `ACT_GROUP_BEAT` | Завершить одно общее взаимодействие группы; остальные участники только поддерживают этот beat. |
| `ACT_MECHANICAL_CONTINUATION` | Согласованно продолжить уже видимое движение колёс или механизма без запуска нового режима. |

### Secondary-motion modules

| Module | Требуемое evidence |
| --- | --- |
| `SEC_SUBJECT_LIFE` | Видимый живой субъект: дыхание, одно естественное моргание или минимальная мимика. |
| `SEC_HAIR_FABRIC` | Волосы, шерсть или ткань видны в `Motion sources`, а физический источник движения следует primary action. |
| `SEC_LIGHT_REFLECTION` | Свет, тень, отражение, прозрачный материал или свечение экрана видны в первом кадре. |
| `SEC_ENVIRONMENT` | Листва, облака или вода видны в `Motion sources`; модуль не создаёт новую погоду. |
| `SEC_LIQUID_VAPOR` | Жидкость, вода или пар уже видны и способны продолжить локальное движение. |
| `SEC_MECHANICAL` | Колёса или механизм уже движутся; secondary motion согласован с primary action. |
| `SEC_DISTANT_PEOPLE` | Люди являются малой фоновой частью среды и не начинают отдельные действия. |
| `SEC_NONE` | Нет безопасного видимого источника вторичной динамики. |

## Общие negative fragments по tags

Это короткие составные fragments, а не готовый negative prompt. Добавляй только
фрагменты для реально выбранных tags и объединяй их с profile-specific
fragments ниже.

| Tag | Fragment |
| --- | --- |
| `face_identity` | `identity change, altered facial proportions, asymmetric eyes` |
| `multiple_people` | `changed person count, swapped identities, merged bodies` |
| `crowd` | `duplicated people, fused silhouettes, independently changing crowd` |
| `hands_visible` | `deformed hands, extra fingers, changed grip or gesture` |
| `hand_object_interaction` | `changed grip, detached hand, transformed interaction object` |
| `readable_text` | `changed or unreadable text, misspelled or warped letters` |
| `logo_or_label` | `changed label, replaced branding, logo distortion` |
| `interface_content` | `invented controls, redrawn interface, changing screen layout` |
| `small_object` | `missing, duplicated or transformed small object` |
| `fine_geometry` | `warped edges, bent thin parts, inconsistent geometry` |
| `repeating_elements` | `changed count, broken spacing, irregular repeated pattern` |
| `reflection` | `detached, delayed or incoherent reflections` |
| `transparent_material` | `opaque glass, melted transparency, inconsistent refraction` |
| `liquid_surface` | `uncontrolled splashing, impossible flow, changing liquid volume` |
| `wheels_visible` | `warped wheels, sliding vehicle, incoherent wheel rotation` |
| `animal_limbs_visible` | `extra limbs, warped paws or legs, broken ground contact` |
| `food_components` | `added or missing ingredients, rearranged garnish, plastic food texture` |
| `centered_symmetry` | `broken symmetry, drifting center, unequal repeated sides` |
| `stable_horizon` | `tilted or unstable horizon` |
| `strict_verticals` | `bent verticals, drifting perspective, warped borders` |
| `composite_layout` | `merged panels, changed grid, parallax between graphic fragments` |
| `partial_occlusion` | `invented hidden anatomy, revealed off-screen objects` |
| `cropped_subject` | `automatic reframing, completed or invented off-frame parts` |
| `shallow_depth_of_field` | `focus pumping, changing focal plane, reconstructed background` |
| `hair_visible` | `changed hairstyle, invented wind, unstable hair outline` |
| `fur_visible` | `changed coat pattern, unstable fur outline, excessive fur motion` |
| `fabric_visible` | `changed garment folds, floating fabric, detached cloth` |
| `foliage_visible` | `invented branches, changing foliage count, excessive wind` |
| `clouds_visible` | `new weather, replacing clouds, accelerated sky` |
| `water_visible` | `changing shoreline or water level, invented waves` |
| `steam_visible` | `invented steam source, growing smoke, excessive vapor` |
| `screen_glow_visible` | `changing screen content, pulsing display, invented controls` |
| `light_shadow_visible` | `new light source, changing shadow direction, exposure jump` |

## Scene profiles

В camera rules ниже `base` — первый выбор, `allowed` — только условные
альтернативы, `forbidden` — модули, несовместимые с профилем. Семантика A–E
остаётся канонической в `prompt-templates.md`.

### `portrait_closeup`

**Признаки.** Лицо, голова, плечи или фрагмент лица несут основной смысл.
Небольшой предмет в руке не меняет класс, если identity и выражение важнее
предмета. Типичные modifiers: `face_identity`, `close_framing`, `hands_visible`,
`hand_object_interaction`, `cropped_subject`, `shallow_depth_of_field`.

**Conditional primary action.**

- В первом кадре рука уже выполняет действие с предметом →
  `ACT_FINISH_VISIBLE_ACTION`; рука завершает только видимую фазу и сохраняет
  хват.
- Сцена still/posed без хрупкой руки у лица → `ACT_MICRO_POSE`.
- Видна settling phase, сложное перекрытие или высокий риск identity →
  `ACT_HOLD_AND_SETTLE`.

**Conditional secondary motion.** `SEC_SUBJECT_LIFE`; `SEC_HAIR_FABRIC` только
когда волосы или ткань есть в `Motion sources`; `SEC_LIGHT_REFLECTION` для уже
видимых очков, зеркала или света. Остальное → `SEC_NONE`.

**Anchors и risks.** Identity, положение глаз и рта, причёска, линия лица,
одежда у шеи, видимые руки, предмет возле лица, исходный crop и фокус.

**Camera.** Base: `B`. Allowed: `A` при тексте, руке у лица или тесном crop;
`D` только когда фронтальная сторона лица уже читается и остаётся главным
anchor. Forbidden: `C`, `E`.

**Вероятная ошибка.** Модель принимает микрожест за начало речи, большого
поворота головы или нового действия рукой.

**Profile fragments.** `speaking, exaggerated expression, large head turn,
changed hairstyle, hand leaving the visible interaction, camera moving behind
the subject`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE` + `SEC_SUBJECT_LIFE`; камера `A`,
если лицо, рука, текст или crop особенно хрупки, иначе base camera.

### `people_action`

**Признаки.** Человек в полный рост, группа или персонаж в среде; поза, жест и
пространственный контекст важны наравне с лицом. Типичные modifiers:
`multiple_people`, `crowd`, `hands_visible`, `hand_object_interaction`,
`wide_environment`, `partial_occlusion`.

**Conditional primary action.**

- В первом кадре видна незавершённая фаза → `ACT_FINISH_VISIBLE_ACTION`;
  продолжать только текущую причинно связанную фазу.
- Видимое направление движения имеет ясный маршрут →
  `ACT_SHORT_DIRECTED_MOTION`.
- Несколько людей уже участвуют в одном взаимодействии → `ACT_GROUP_BEAT`;
  один лидер действия, без независимых параллельных сюжетов.
- Сцена still/posed → `ACT_MICRO_POSE`; при перекрытиях →
  `ACT_HOLD_AND_SETTLE`.

**Conditional secondary motion.** `SEC_SUBJECT_LIFE`; `SEC_HAIR_FABRIC` только
для видимых волос или ткани с физическим источником; `SEC_DISTANT_PEOPLE` только
для фоновых фигур, не являющихся частью основной группы.

**Anchors и risks.** Число и identity людей, топология группы, перекрытия,
жесты, опора ног, одежда, реквизит, направление действия и положение каждого
человека относительно краёв кадра.

**Camera.** Base: `B`. Allowed: `A` для толпы, текста, сложных перекрытий или
статичной группы; `C` для явно направленного движения в открытой сцене; `D`,
когда лицо одного человека остаётся главным anchor. Forbidden: `E`.

**Вероятная ошибка.** Модель перезапускает действие, разводит участников по
независимым движениям или выводит человека за край кадра.

**Profile fragments.** `restarted action, reversed direction, new independent
actions, subject leaving frame, changed group formation, floating feet,
disappearing prop`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE`; `SEC_SUBJECT_LIFE` только для
одного ясно видимого ведущего субъекта, иначе `SEC_NONE`; камера `A` или base
camera.

### `product_still_life`

**Признаки.** Товар, упаковка или предметная композиция доминируют, а человек
не формирует сюжет. Типичные modifiers: `logo_or_label`, `readable_text`,
`small_object`, `fine_geometry`, `reflection`, `transparent_material`,
`overhead_flat_lay`, `hand_object_interaction`.

**Conditional primary action.**

- Уже видимая капля, подвижная деталь или локальная физика →
  `ACT_LOCAL_PHYSICS`.
- Видимая рука уже взаимодействует с предметом → `ACT_FINISH_VISIBLE_ACTION`
  только для стабилизации существующего хвата или микродвижения.
- Статичная упаковка, label или раскладка → `ACT_HOLD_AND_SETTLE`; сам товар не
  перемещается.

**Conditional secondary motion.** `SEC_LIGHT_REFLECTION` только при видимом
отражении, прозрачном материале или изменяемом свете; `SEC_LIQUID_VAPOR` только
при видимом источнике; иначе `SEC_NONE`.

**Anchors и risks.** Силуэт и количество предметов, упаковка, крышка, label,
логотип, мелкие детали, точный crop, тени, контакт с поверхностью и материал.

**Camera.** Base: `A`. Allowed: `B` только для объёмной предметки, если нет
читаемого текста, flat lay и хрупкой мелкой геометрии. Иначе сохраняй base
camera. Forbidden: `C`, `D`, `E`.

**Вероятная ошибка.** Модель превращает изменение блика в вращение товара,
перерисовывает упаковку или добавляет новые капли и предметы.

**Profile fragments.** `product rotation, product transformation, changed item
count, opening package, invented drops, floating object, changing material or
shadow contact`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE`; `SEC_LIGHT_REFLECTION` только при
видимом отражении или изменяемом свете, иначе `SEC_NONE`; camera `A`.

### `food`

**Признаки.** Блюдо, продукты или ингредиенты являются главным субъектом.
Типичные modifiers: `food_components`, `liquid_surface`, `steam_visible`,
`overhead_flat_lay`, `fine_geometry`, `reflection`, `hand_object_interaction`.

**Conditional primary action.**

- Видимая жидкость, пар или уже начавшееся локальное settling →
  `ACT_LOCAL_PHYSICS`.
- Рука или прибор уже завершают действие → `ACT_FINISH_VISIBLE_ACTION` без
  добавления новых ингредиентов и без нового шага приготовления.
- Готовая сервировка или flat lay → `ACT_HOLD_AND_SETTLE`.

**Conditional secondary motion.** `SEC_LIQUID_VAPOR` только по evidence;
`SEC_LIGHT_REFLECTION` для посуды, приборов и влажных поверхностей; иначе
`SEC_NONE`.

**Anchors и risks.** Состав и раскладка ингредиентов, объём блюда, форма посуды,
приборы, гарнир, текстуры, края жидкостей и контакт еды с поверхностью.

**Camera.** Base: `A`. Allowed: `B` для объёмной сцены без строгой раскладки и
читаемой упаковки. Forbidden: `C`, `D`, `E`.

**Вероятная ошибка.** Модель начинает готовить или сервировать уже законченное
блюдо, меняет ингредиенты, создаёт кипение, брызги или неестественное плавление.

**Profile fragments.** `new cooking action, stirring, pouring, added or removed
ingredients, boiling, large splash, uncontrolled melting, moving tableware`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE`; слабый `SEC_LIGHT_REFLECTION` при
наличии evidence; camera `A`.

### `animal`

**Признаки.** Животное является главным субъектом, даже если взаимодействует с
товаром, мебелью или текстилем. Типичные modifiers: `animal_limbs_visible`,
`partial_occlusion`, `fur_visible`, `fabric_visible`, `close_framing`,
`small_object`.

**Conditional primary action.**

- В первом кадре видна незавершённая фаза или однозначное направление при ясной
  позе конечностей → `ACT_FINISH_VISIBLE_ACTION` либо
  `ACT_SHORT_DIRECTED_MOTION` без смены направления.
- Сцена still/posed → `ACT_MICRO_POSE`: один взгляд, движение головы или ушей.
- Скрытые лапы, тесный crop или сложное перекрытие →
  `ACT_HOLD_AND_SETTLE`.

**Conditional secondary motion.** `SEC_SUBJECT_LIFE`; `SEC_HAIR_FABRIC` для
шерсти и видимого текстиля; остальные источники только по evidence.

**Anchors и risks.** Вид, окрас и рисунок шерсти, морда, глаза, уши, усы,
количество и перекрытия конечностей, хвост, контакт с поверхностью и предмет
взаимодействия.

**Camera.** Base: `B`. Allowed: `A` для тесного crop, скрытых конечностей,
текста или хрупкого предмета взаимодействия. Forbidden: `C`, `D`, `E`.

**Вероятная ошибка.** Модель достраивает скрытые лапы, меняет вид или превращает
небольшое движение головы в прыжок, ходьбу либо выход из кадра.

**Profile fragments.** `changed species or coat pattern, invented hidden limbs,
large body movement, jumping, leaving frame, unnatural gait, changed interaction
object`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE` + `SEC_SUBJECT_LIFE`; camera `A`
при partial occlusion, иначе base camera.

### `vehicle_mechanism`

**Признаки.** Автомобиль, салон, приборная панель или механизм определяют сцену.
Типичные modifiers: `wheels_visible`, `interface_content`, `readable_text`,
`logo_or_label`, `fine_geometry`, `reflection`, `strict_verticals`.

**Conditional primary action.**

- Транспорт уже движется в однозначном направлении, а колёса видны →
  `ACT_SHORT_DIRECTED_MOTION` с согласованным вращением и без нового манёвра.
- Видимая механическая часть уже движется → `ACT_MECHANICAL_CONTINUATION`;
  продолжает движение только эта часть.
- Статичный экстерьер → `ACT_HOLD_AND_SETTLE`; движение создают только свет и
  отражения.
- Салон, interface или техническая деталь → `ACT_HOLD_AND_SETTLE`; органы
  управления не активируются.

**Conditional secondary motion.** `SEC_MECHANICAL` только при видимом primary
motion; `SEC_LIGHT_REFLECTION` только для уже видимых бликов на кузове, стекле,
дисплее или металле; фоновые элементы только по evidence.

**Anchors и risks.** Модель и силуэт, колёса, кузовные панели, логотипы, свет,
механические связи, число деталей, интерфейс, органы управления и отражения.

**Camera.** Base: `B`; base меняется на `A` для салона, interface, текста и
технической детали. Allowed: `A`, `C` для уже движущегося транспорта в открытой
сцене. Forbidden: `D`, `E`.

**Вероятная ошибка.** Модель запускает припаркованный транспорт, меняет маршрут,
вращает органы управления, перерисовывает интерфейс или деформирует механизм.

**Profile fragments.** `vehicle starting from a parked state, reversing,
turning or drifting, new maneuver, opening doors, changing model, moving
controls, mechanical deformation`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE`; `SEC_LIGHT_REFLECTION` только при
видимом отражении или изменяемом свете, иначе `SEC_NONE`; camera `A`.

### `interior`

**Признаки.** Комната, мебель, отделка и планировочная глубина являются главным
субъектом. Автомобильный салон остаётся `vehicle_mechanism`. Типичные modifiers:
`strict_verticals`, `centered_symmetry`, `repeating_elements`, `reflection`,
`layered_depth`, `water_visible`, `light_shadow_visible`.

**Conditional primary action.**

- Видимые вода, штора, свет или отражение уже дают локальную динамику →
  `ACT_LOCAL_PHYSICS`.
- Во всех остальных случаях → `ACT_HOLD_AND_SETTLE`.
- Двери, ящики, мебель, техника и светильники не начинают новое действие без
  явной незавершённой фазы в первом кадре.

**Conditional secondary motion.** `SEC_LIGHT_REFLECTION` только для уже видимых
света или отражения; `SEC_LIQUID_VAPOR` для видимой воды; `SEC_HAIR_FABRIC`
только для уже видимой мягкой ткани; иначе `SEC_NONE`.

**Anchors и risks.** Планировка, прямые линии, число дверей и окон, мебель,
орнамент, светильники, отражения, уровень воды, границы пространства и
перспектива.

**Camera.** Base: `A`. Allowed: `E` только при ясно видимой глубине планов и
отсутствии строгой фронтальной геометрии. Forbidden: `B`, `C`, `D`.

**Вероятная ошибка.** Модель открывает мебель, переставляет предметы, создаёт
новые проёмы или заставляет вертикали и отражения плыть.

**Profile fragments.** `moving furniture, opening doors or drawers, added
windows, changing room layout, warped cabinetry, drifting verticals, changing
water level`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE` + `SEC_LIGHT_REFLECTION` только по
evidence; camera `A`.

### `architecture_place`

**Признаки.** Фасад, городская среда или крупное общественное пространство
задают смысл и масштаб. Типичные modifiers: `wide_environment`,
`stable_horizon`, `strict_verticals`, `centered_symmetry`, `repeating_elements`,
`layered_depth`, `water_visible`, `foliage_visible`, `crowd`.

**Conditional primary action.** Архитектура всегда остаётся статичной. Видимые
вода или свет могут выбрать `ACT_LOCAL_PHYSICS`, не меняя геометрию места; во
всех остальных случаях используй `ACT_HOLD_AND_SETTLE`. Фоновые люди не
становятся primary action.

**Conditional secondary motion.** `SEC_ENVIRONMENT` для уже видимых воды и
листвы; `SEC_LIGHT_REFLECTION` для уже видимых освещения и стекла;
`SEC_DISTANT_PEOPLE` только для малых фоновых фигур.

**Anchors и risks.** Фасады, окна, вертикали, горизонт, масштаб, перспектива,
симметрия, число повторяющихся деталей, вывески, отражения и размещение людей.

**Camera.** Base: `E`. Allowed: `A` для хрупкой геометрии, текста или симметрии;
`C` для пространства с уже выраженным направлением движения. Forbidden: `B`,
`D`.

**Вероятная ошибка.** Модель оживляет саму архитектуру, искривляет перспективу,
меняет масштаб или превращает фоновых людей в новый сюжет.

**Profile fragments.** `moving architecture, warped facade, changing windows,
scale shift, duplicated structures, jumping horizon, aggressive fly-through,
new foreground event`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE`; только слабый подтверждённый
secondary module; camera `A`.

### `nature_open_scene`

**Признаки.** Небо, ландшафт, вода или природная среда доминируют без более
сильного человека, животного, здания или транспорта. Типичные modifiers:
`wide_environment`, `stable_horizon`, `layered_depth`, `clouds_visible`,
`water_visible`, `foliage_visible`, `light_shadow_visible`.

**Conditional primary action.**

- Видимое направленное течение, движение облаков или settling воды →
  `ACT_LOCAL_PHYSICS`.
- Почти графичная или хрупкая световая композиция → `ACT_HOLD_AND_SETTLE`.
- В остальных случаях → `ACT_HOLD_AND_SETTLE`; новое природное событие не
  создаётся.

**Conditional secondary motion.** `SEC_ENVIRONMENT`; `SEC_LIQUID_VAPOR` для
воды; `SEC_LIGHT_REFLECTION` для света на воде или ландшафте. Каждый модуль
требует прямого видимого evidence в первом кадре.

**Anchors и risks.** Горизонт, береговая линия, форма облаков, направление
света, рельеф, отражения, границы воды и отсутствие новых объектов.

**Camera.** Base: `E`. Allowed: `A` для почти графичной композиции, солнца,
симметрии или хрупкого горизонта. Forbidden: `B`, `C`, `D`.

**Вероятная ошибка.** Модель ускоряет погоду, создаёт шторм, птиц или новые
объекты, меняет время суток либо раскачивает горизонт.

**Profile fragments.** `new weather, storm, fast clouds, added birds or people,
time-of-day change, exposure jump, changing shoreline, unstable horizon`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE` с одним слабым подтверждённым
environmental motion source; camera `A`.

### `text_interface_collage`

**Признаки.** Читаемый текст, interface или составная графическая композиция
являются ключевым содержанием. Типичные modifiers: `readable_text`,
`interface_content`, `logo_or_label`, `composite_layout`, `fine_geometry`,
`repeating_elements`, `overhead_flat_lay`, `cropped_subject`.

**Conditional primary action.** Всегда `ACT_HOLD_AND_SETTLE`. Текст, controls,
панели, иллюстрации и границы фрагментов не анимируются и не
перекомпоновываются.

**Conditional secondary motion.** `SEC_LIGHT_REFLECTION` допустим только как
единое слабое изменение общего света без локального параллакса и без изменения
контента. Иначе `SEC_NONE`.

**Anchors и risks.** Содержание и читаемость текста, логотипы, сетка, размеры и
положение панелей, границы фрагментов, UI controls, порядок слоёв и полный crop.

**Camera.** Base: `A`. Allowed: none. Forbidden: `B`, `C`, `D`, `E`.

**Вероятная ошибка.** Модель воспринимает interface как рабочий экран,
перерисовывает текст, переключает состояние controls или создаёт параллакс между
частями коллажа.

**Profile fragments.** `typing, scrolling, clicking controls, changing screen
state, rewritten text, invented interface elements, moving panels, changed grid,
parallax between fragments`.

**Low-risk fallback.** `ACT_HOLD_AND_SETTLE` + `SEC_NONE`; camera `A`.

## Порядок применения

1. Выбери один `primary_class` по визуальному доминанту.
2. Нормализуй только cross-cutting anchors и risks в `scene_tags`; отложи их
   для preservation и negative constraints, не используя для routing.
3. По состоянию и движению, непосредственно видимым в первом кадре, выбери один
   primary action module.
4. Добавь secondary-motion modules только из прямых `Motion sources`.
5. Начни с base camera; переходи к allowed camera только при ясной пользе,
   подтверждённой самим кадром. Тег не может разрешить или запретить камеру.
6. Зафиксируй anchors и собери только релевантные tag-level и profile-specific
   negative fragments; теги не добавляют действий или камер.
7. При неоднозначности используй `low-risk fallback` выбранного профиля.
8. Передай выбранные модули в общий pipeline и финальные prompt templates; не
   возвращай названия классов, tags или module IDs пользователю.
