# Project Agents

This project has one registered working agent.

## clipmaker

Use the clipmaker agent when you need to create image-to-video prompts from a
single input image for one explicitly selected model:

- `alibaba/wan-2.2`;
- `alibaba/wan-2.7`;
- `google/veo-3.1-lite`.

- Entry point: [docs/agents/clipmaker/README.md](docs/agents/clipmaker/README.md)
- Workflow: [docs/agents/clipmaker/pipeline.md](docs/agents/clipmaker/pipeline.md)
- Scene routing: [docs/agents/clipmaker/scene-modules.md](docs/agents/clipmaker/scene-modules.md)
- Prompt blocks and output format: [docs/agents/clipmaker/prompt-templates.md](docs/agents/clipmaker/prompt-templates.md)

The clipmaker agent must load the selected model spec, start from visible image
evidence, resolve one primary scene profile or use the explicit generic
unresolved fallback, and infer one small completed action. Only a resolved
`text_interface_collage` frame receives one active `graphic_kind` plus all
independent visible `graphic_kinds`. Unresolved or conflicting graphic routing
fails closed to a locked flat-raster hold without kind-specific action or
negative clauses. The agent must select exactly one camera state A–E; Module A
represents no camera motion, so modules are never combined or omitted. Unknown
model IDs must fail closed; model durations and prompt limits must never be
guessed or copied between models. Graphic routing must not assume masks, layers
or editable source files.

## Interface design

Always use the `impeccable` skill when designing, redesigning, reviewing, or
polishing user interfaces in this project. Read `.impeccable.md` before making
interface decisions and keep its Design Context up to date when the product
audience, use cases, or visual direction change.

## Design Context

### Users

Внутренняя продуктовая и медиа-команда. Интерфейс используется как рабочая
демка для быстрой визуальной оценки generated-видео, исходных изображений и
результатов конвертации MP4 в animated WebP. Главная задача — быстро замечать
разницу в качестве, тайминге и весе файлов, не теряя технический контекст.

### Brand Personality

Спокойный, точный, редакционный. Интерфейс должен вызывать доверие к данным,
оставлять медиаматериалы главным визуальным объектом и ощущаться как аккуратно
собранный внутренний инструмент, а не универсальный dashboard.

### Aesthetic Direction

Светлая тема с тёплыми, слегка тонированными нейтралями и редким фирменным
акцентом Алисы. Выразительная типографика, ясная иерархия, асимметричная
редакционная композиция и спокойные поверхности. Исключены типичные AI-паттерны:
градиентный текст, неон на тёмном фоне, стеклянные карточки, чрезмерное скругление
и сетки из одинаковых карточек.

### Design Principles

1. Медиа важнее chrome: изображения и видео получают максимум пространства.
2. Сравнение должно считываться мгновенно: состояния, форматы и размеры видны
   без расшифровки интерфейса.
3. Один уровень навигации объединяет Generated Library, MP4/WebP comparison и model review.
4. Визуальная иерархия строится типографикой, ритмом и контрастом, а не лишними
   контейнерами и декоративными эффектами.
5. Все интерактивные состояния доступны с клавиатуры, соответствуют WCAG AA и
   уважают `prefers-reduced-motion`.
