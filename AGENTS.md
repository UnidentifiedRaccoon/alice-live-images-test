# Project Agents

This project has one registered working agent.

## clipmaker

Use the clipmaker agent when you need to create Wan 2.2 Image-to-Video prompts
from a single input image.

- Entry point: [docs/agents/clipmaker/README.md](docs/agents/clipmaker/README.md)
- Workflow: [docs/agents/clipmaker/pipeline.md](docs/agents/clipmaker/pipeline.md)
- Prompt blocks and output format: [docs/agents/clipmaker/prompt-templates.md](docs/agents/clipmaker/prompt-templates.md)

The clipmaker agent must start from the image, infer one small completed action,
choose camera motion only when it fits the image, and return a final English
positive prompt plus a final English negative prompt.

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
3. Один уровень навигации объединяет Generated Library и MP4/WebP comparison.
4. Визуальная иерархия строится типографикой, ритмом и контрастом, а не лишними
   контейнерами и декоративными эффектами.
5. Все интерактивные состояния доступны с клавиатуры, соответствуют WCAG AA и
   уважают `prefers-reduced-motion`.
