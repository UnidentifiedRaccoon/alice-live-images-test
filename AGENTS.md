# Project Agents

This project has two registered working agents.

## Required clipmaker routing

The canonical agent IDs are `clipmaker-classic` and `clipmaker-lite`. Select one
explicitly before clip planning; a model ID cannot select the agent because the
routes overlap. If the request says only "clipmaker", ask which contract to use.

Once selected, load only that agent's entry point and model specs. Unsupported
models, missing inputs, contract mismatches and runner errors fail inside the
selected route. Never fall back to the other clipmaker. An artifact counts as
Lite only when the Lite runner writes it below `artifacts/clipmaker-lite/v1/`
with `producer.agent_id: clipmaker-lite` and the runner's `provenance` command
returns `verified: true`.

## clipmaker-classic

Use `clipmaker-classic` only when the user explicitly selects this agent ID for
the existing routed and preservation-oriented workflow. It supports:

- `alibaba/wan-2.2`;
- `alibaba/wan-2.7`;
- `google/veo-3.1-lite`.

- Entry point: [docs/agents/clipmaker/README.md](docs/agents/clipmaker/README.md)
- Workflow: [docs/agents/clipmaker/pipeline.md](docs/agents/clipmaker/pipeline.md)
- Scene routing: [docs/agents/clipmaker/scene-modules.md](docs/agents/clipmaker/scene-modules.md)
- Prompt blocks and output format: [docs/agents/clipmaker/prompt-templates.md](docs/agents/clipmaker/prompt-templates.md)

## clipmaker-lite

Use `clipmaker-lite` only when the user explicitly selects this agent ID. It
analyzes the image together with the article text and exact image position,
prepares a short semantic scene brief, and plans each model independently.

- Supported model IDs: `alibaba/wan-2.7`, `google/veo-3.1-lite`.
- Entry point: [docs/agents/clipmaker-lite/README.md](docs/agents/clipmaker-lite/README.md)
- Locked contract: [docs/agents/clipmaker-lite/contract.json](docs/agents/clipmaker-lite/contract.json)
- Isolated runner: [scripts/clipmaker_lite_runner.py](scripts/clipmaker_lite_runner.py)

Before analysis, the Lite runner must prepare the run and its exact instruction
bundle. The runner then invokes an isolated Codex execution, captures its
structured response and stamps the result. Do not author an external
`draft.json`, write provenance/runtime manually, or bypass the execution receipt.

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
