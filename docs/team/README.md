# Binex Team Roles

Каждый файл в этой папке описывает одного агента команды: кто он, что делает, чего не делает, и точный промпт который ему передаётся при создании.

## Состав команды

| Агент | Ответственность |
|-------|----------------|
| [team-lead](team-lead.md) | Координатор — принимает все решения, управляет жизненным циклом команды |
| [product-manager](product-manager.md) | Продуктовое видение → задачи для команды |
| [architect](architect.md) | Системный дизайн, API контракты, технические решения |
| [designer](designer.md) | UX ownership + UI код (Tailwind, компоненты) |
| [frontend-dev](frontend-dev.md) | React логика, state, API интеграция |
| [backend-dev](backend-dev.md) | Python backend (FastAPI, CLI, модели) |
| [qa-tester](qa-tester.md) | Тесты, регрессии, баг-репорты |
| [docs-maintainer](docs-maintainer.md) | Документация (README, CLAUDE.md, docs/) |
| [devops](devops.md) | CI/CD, GitHub Actions, релизы |
| [meta-agent](meta-agent.md) | Smart context compaction |
| [crew-advisor](crew-advisor.md) | Советует team-lead по составу команды |

## Коммуникационный протокол

### После каждой задачи агент отправляет ДВА сообщения:

```
1. → meta-agent:  "Закончил: [задача]. Context: ok/warning/critical"
2. → team-lead:   "Закончил: [задача]. Idle."
```

### Реакция meta-agent:
- `ok` → ничего не делает
- `warning` → запрашивает у агента состояние, готовит brief, делает compact
- `critical` → немедленный compact

### Реакция crew-advisor (только по запросу team-lead):
```
team-lead → crew-advisor: "Агент X idle. TaskList: [список]"
crew-advisor → team-lead: рекомендация по составу
```

## Граница designer / frontend-dev

| Вопрос | Кто отвечает |
|--------|-------------|
| Почему это так выглядит? | designer |
| Как это работает технически? | frontend-dev |
| UX, spacing, типографика, Tailwind | designer |
| React state, хуки, API, React Flow | frontend-dev |
