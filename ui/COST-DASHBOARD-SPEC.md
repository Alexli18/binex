# Cost Dashboard — Design Spec

> **Status**: Draft | **Author**: designer | **Date**: 2026-03-16
> **Blocks**: Task #9 (backend), Task #10 (frontend implementation)

## 1. Overview

Выделенная страница Cost Dashboard заменяет вкладку "costs" на текущем Dashboard.
Доступна из Sidebar → группа "Analyze" → **Costs** (иконка: `DollarSign` из lucide-react).

**URL**: `/costs` (новый route в App.tsx)

**Цель**: Дать пользователю полную картину расходов на LLM-вызовы — сколько потрачено, на что, тренд, бюджет.

---

## 2. Page Layout (Wireframe)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Costs                                            │
│ PageHeader: "Cost Dashboard"  [actions: Export CSV | period picker]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │Total Cost│ │Avg / Run │ │Total Runs│ │  Budget  │              │
│  │ $12.45   │ │  $1.24   │ │    10    │ │ 65% used │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Cost Trend (Area Chart)                         │   │
│  │  $                                                          │   │
│  │  │    ╱╲                                                    │   │
│  │  │   ╱  ╲    ╱╲                                             │   │
│  │  │  ╱    ╲  ╱  ╲                                            │   │
│  │  │ ╱      ╲╱    ╲___                                        │   │
│  │  └──────────────────────── date                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐   │
│  │  Cost by Model (Bar H)   │  │  Cost by Node (Bar H)        │   │
│  │  gpt-4o        ████ $5.4 │  │  search       ███ $2.1       │   │
│  │  claude-sonnet ██   $2.1 │  │  analyze      ██  $1.5       │   │
│  │  gemini-flash  █    $0.8 │  │  summarize    █   $0.8       │   │
│  └──────────────────────────┘  └──────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Runs Table (sortable, filterable)                          │   │
│  │  ┌────────┬──────────┬────────┬─────────┬────────┬───────┐ │   │
│  │  │ Run ID │ Workflow │ Status │  Cost   │ Nodes  │ Date  │ │   │
│  │  ├────────┼──────────┼────────┼─────────┼────────┼───────┤ │   │
│  │  │ abc123 │ simple   │ ✓ done │  $0.45  │  3/3   │ 03-16 │ │   │
│  │  │ def456 │ complex  │ ✗ fail │  $1.20  │  5/8   │ 03-15 │ │   │
│  │  │ ghi789 │ simple   │ ⚠ budg │  $0.50  │  2/3   │ 03-15 │ │   │
│  │  └────────┴──────────┴────────┴─────────┴────────┴───────┘ │   │
│  │  [Sort by: Cost ▼]  [Filter: All statuses]  [Search...]    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Budget Configuration                                       │   │
│  │                                                             │   │
│  │  Current: max_cost=$1.00, policy=stop                       │   │
│  │                                                             │   │
│  │  ┌─ How to configure ─────────────────────────────────┐    │   │
│  │  │  budget:                                            │    │   │
│  │  │    max_cost: 1.00                                   │    │   │
│  │  │    policy: stop  # or warn                          │    │   │
│  │  └────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Sections Detail

### 3.1 Period Picker

**Компонент**: shadcn `Select` (уже мигрирован в Фазе 1)
**Опции**: `24h` | `7d` (default) | `30d` | `all`
**Расположение**: PageHeader actions slot (справа)
**Поведение**: Смена периода перезагружает все данные через `useCostDashboard(period)`

### 3.2 KPI Cards (4 штуки)

**Layout**: `grid grid-cols-2 md:grid-cols-4 gap-4`

| Card | Данные | Форматирование | Иконка |
|------|--------|---------------|--------|
| Total Cost | `total_cost` | `$XX.XX` (2 знака) | `DollarSign` (lucide) |
| Avg per Run | `avg_per_run` | `$X.XX` | `TrendingUp` |
| Total Runs | `run_count` | целое число | `Activity` |
| Budget Used | вычисляется | `XX%` + progress bar | `Shield` |

**Компонент**: Переиспользовать shadcn `Card` с `CardHeader` + `CardContent`

**Budget Card logic**:
- Если budget не настроен → показать "Not configured" + ссылка на секцию Budget Configuration
- Если настроен → показать progress bar с цветами:
  - `< 50%`: `colors.success.DEFAULT` (emerald)
  - `50-80%`: `colors.warning.DEFAULT` (amber)
  - `> 80%`: `colors.danger.DEFAULT` (red)
- Progress bar: `<div>` с `role="progressbar"`, `aria-valuenow`, `aria-valuemin=0`, `aria-valuemax=100`, `aria-label="Budget usage"`

**Styling**: Использовать `surface.raised` из design-tokens для card bg, `typography.heading` для значений.

### 3.3 Cost Trend Chart

**Тип**: Area Chart (Recharts `<AreaChart>`)
**Данные**: `cost_trend[]` — `{date, cost, runs}`
**X-axis**: Даты, формат зависит от периода:
  - `24h`: `HH:mm`
  - `7d`/`30d`: `MMM dd`
  - `all`: `MMM yyyy`
**Y-axis**: Cost ($), автоскейл
**Tooltip**: Показывает `cost` + `runs` count
**Градиент**: Fill с opacity 0.3 → 0 (существующий паттерн из Dashboard)
**Цвет линии**: `chartColors.primary` из design-tokens

**Responsive**:
- Desktop: `height={300}`
- Mobile (< 768px): `height={200}`
- Использовать `<ResponsiveContainer width="100%">`

**Empty state**: Если `cost_trend` пуст → EmptyState компонент: "No cost data for this period" + иконка `BarChart3`

**Accessibility**:
- `aria-label="Cost trend over time"` на контейнере
- Tooltip доступен по keyboard focus (Recharts default)
- gridlines: `stroke={chartColors.grid}` (subtle)

### 3.4 Breakdown Charts (Side-by-Side)

**Layout**: `grid grid-cols-1 lg:grid-cols-2 gap-6`

#### Cost by Model (Horizontal Bar Chart)
- **Тип**: `<BarChart layout="vertical">` (Recharts)
- **Данные**: `cost_by_model[]` отсортированные по cost desc, top-10
- **Y-axis**: Model name (truncate > 20 chars, tooltip для полного)
- **X-axis**: Cost ($)
- **Bar color**: `chartColors.primary`
- **Label**: Прямо на bar — `$X.XX` (direct labeling, уменьшает eye travel)
- **Height**: Адаптивная — `Math.max(200, data.length * 40)`

#### Cost by Node (Horizontal Bar Chart)
- **Тип**: Аналогично Cost by Model
- **Данные**: `cost_by_node[]` отсортированные по cost desc, top-10
- **Bar color**: `chartColors.secondary`

**Empty states**: Каждый чарт индивидуально — "No model/node cost data"

### 3.5 Runs Cost Table

**Компонент**: Кастомная таблица (как в Dashboard, но с улучшениями из аудита)

**Columns**:
| Column | Field | Width | Sort | Format |
|--------|-------|-------|------|--------|
| Run ID | `run_id` | auto | - | Truncate 8 chars + Tooltip |
| Workflow | `workflow_name` | auto | ✓ | Truncate 20 chars |
| Status | `status` | 100px | ✓ | StatusBadge component |
| Cost | `total_cost` | 100px | ✓ (default desc) | `$X.XXXX` monospace |
| Nodes | computed | 80px | - | `completed/total` |
| Date | `started_at` | 120px | ✓ | Relative ("2h ago") + tooltip абс. дата |

**Features**:
- **Sorting**: По клику на header, `aria-sort` attribute для accessibility
- **Filter**: shadcn `Select` для status filter (All | Completed | Failed | Over Budget)
- **Search**: shadcn `Input` для поиска по workflow name
- **Row click**: Навигация к `/runs/{run_id}` (RunDetail page)
- **Sticky header**: `sticky top-0 z-10` при вертикальном скролле
- **Hover**: `surface.hover` из design-tokens

**Responsive** (< 768px):
- Скрыть Nodes column
- Run ID → 6 chars
- Date → только relative

**Empty state**: EmptyState — "No runs found for this period"

**Styling**:
- Header: `surface.raised`, `typography.muted` для labels
- Cost column: `font-mono` для выравнивания цифр (tabular figures)
- Rows with `over_budget`: `bg-amber-900/10` subtle highlight

### 3.6 Budget Configuration

**Отображение**: Collapsible section (shadcn нет Collapsible — использовать `<details>/<summary>` с Tailwind styling, или простой toggle)

**Содержание**:
1. Текущий бюджет (если есть в последнем run): `max_cost`, `policy`
2. Code block с примером YAML конфигурации
3. Описание policies: `stop` vs `warn`

**Styling**: `surface.raised` card, code block с `bg-slate-900 font-mono text-sm`

---

## 4. Components Map

### Новые компоненты (создать)

| Component | Path | Описание |
|-----------|------|----------|
| `CostDashboardPage` | `pages/CostDashboard.tsx` | Главная страница |
| `KPICard` | `components/cost/KPICard.tsx` | Переиспользуемая KPI card |
| `CostTrendChart` | `components/cost/CostTrendChart.tsx` | Area chart трендов |
| `CostBreakdownChart` | `components/cost/CostBreakdownChart.tsx` | Horizontal bar chart (reusable для model/node) |
| `CostRunsTable` | `components/cost/CostRunsTable.tsx` | Таблица с сортировкой и фильтрами |
| `BudgetStatus` | `components/cost/BudgetStatus.tsx` | Budget progress + config info |

### Переиспользуемые (уже существуют)

| Component | Source | Как используется |
|-----------|--------|-----------------|
| `PageShell` | `layout/PageShell` | Обёртка страницы |
| `PageHeader` | `layout/PageHeader` | Заголовок + breadcrumb + actions |
| `Breadcrumb` | `common/Breadcrumb` | Home > Costs |
| `StatusBadge` | `common/StatusBadge` | Статус run'а в таблице |
| `LoadingState` | `layout/LoadingState` | Skeleton при загрузке |
| `EmptyState` | `layout/EmptyState` | Пустые состояния |
| `ErrorState` | `layout/ErrorState` | Ошибки загрузки |
| `Select` | `ui/select` | Period picker, status filter |
| `Input` | `ui/input` | Поиск в таблице |
| `Card` | `ui/card` | KPI cards |
| `Button` | `ui/button` | Export action |
| `Tooltip` | `ui/tooltip` | Truncated text |

---

## 5. API Endpoints (существующие)

Все endpoints уже реализованы:

| Endpoint | Hook | Данные |
|----------|------|--------|
| `GET /api/v1/costs/dashboard?period=7d` | `useCostDashboard(period)` | KPI + charts + trend |
| `GET /api/v1/runs` | `useRuns()` | Таблица runs (уже есть total_cost) |
| `POST /api/v1/costs/estimate` | `useCostEstimate()` | Оценка стоимости (не нужен на этой странице) |

**Новый endpoint не нужен** — все данные доступны через существующие hooks.

Единственное дополнение: `useRuns()` уже возвращает `total_cost` в каждом run. Для сортировки по cost — сортировка на клиенте (runs обычно < 1000).

---

## 6. Data Flow

```
Period Picker (state)
       │
       ▼
useCostDashboard(period) ──► KPI Cards
       │                 ──► Cost Trend Chart
       │                 ──► Cost by Model Chart
       │                 ──► Cost by Node Chart
       │
useRuns() ──────────────► Runs Table (client-side sort/filter)
```

**State management**: React useState для:
- `period` (default: "7d")
- `sortColumn` + `sortDirection` (default: cost desc)
- `statusFilter` (default: "all")
- `searchQuery` (default: "")

**Refetch**: `useCostDashboard` автоматически refetch при смене period (queryKey включает period).

---

## 7. Routing & Navigation

### App.tsx addition
```tsx
<Route path="/costs" element={<CostDashboardPage />} />
```

### Sidebar addition
В группе "Analyze" добавить пункт:
```tsx
{ to: '/costs', icon: DollarSign, label: 'Costs' }
```
Между "Compare" и "Bisect".

### Dashboard migration
Удалить вкладки "costs" и "budget" из Dashboard.tsx. Вместо них — одна ссылка "View Cost Dashboard →" в header area.

---

## 8. Design Tokens Usage

Все цвета из `lib/design-tokens.ts`:

| Элемент | Token |
|---------|-------|
| Page bg | `surface.base` |
| Card bg | `surface.raised` |
| Card border | `surface.border` |
| KPI value text | `typography.heading` |
| KPI label text | `typography.muted` |
| Table header bg | `surface.raised` |
| Table row hover | `surface.hover` |
| Chart primary | `chartColors.primary` |
| Chart secondary | `chartColors.secondary` |
| Chart tooltip bg | `chartColors.tooltipBg` |
| Chart grid | `chartColors.grid` |
| Budget ok | `colors.success.DEFAULT` |
| Budget warning | `colors.warning.DEFAULT` |
| Budget danger | `colors.danger.DEFAULT` |
| Status badges | `getStatusColors(status)` |

---

## 9. Responsive Breakpoints

| Breakpoint | KPI Grid | Charts | Table | Budget |
|------------|----------|--------|-------|--------|
| < 640px (sm) | 2 cols | stacked | hide Nodes, short IDs | collapsed |
| 640-1024px (md) | 4 cols | stacked | full | collapsed |
| ≥ 1024px (lg) | 4 cols | side-by-side | full | expanded |

---

## 10. Accessibility Checklist

- [x] All KPI cards: `aria-label` с описанием ("Total cost: $12.45 for last 7 days")
- [x] Budget progress bar: `role="progressbar"` + `aria-valuenow/min/max`
- [x] Chart containers: `aria-label` describing the chart
- [x] Table: `aria-sort` на sortable columns
- [x] Table row: `role="link"` or `<tr tabIndex={0}>` для keyboard nav
- [x] Tooltip для truncated text: keyboard-accessible
- [x] Color не единственный индикатор: иконки + текст для status
- [x] Focus management: tab order follows visual order
- [x] Cost values: `font-mono` для tabular figures (accessibility + readability)

---

## 11. Loading & Error States

| State | Визуализация |
|-------|-------------|
| Initial load | `LoadingState variant="skeleton"` — 4 skeleton cards + chart skeleton + table skeleton |
| Period change | Skeleton overlay на charts (не на KPI — они обновляются мгновенно) |
| Error | `ErrorState` с retry button |
| Empty (no runs) | `EmptyState` — "No cost data yet. Run a workflow to see costs here." + Button "Run Workflow" → `/editor` |
| Empty chart | Per-chart empty message (не блокирует остальные секции) |

---

## 12. Export

**Button**: "Export CSV" в PageHeader actions (рядом с period picker)
**Данные**: Все runs за выбранный период с cost breakdown
**Формат**: CSV (`run_id, workflow, status, total_cost, budget, started_at`)
**Реализация**: Client-side через существующий `useExport()` hook или простой Blob download

---

## 13. Interaction Flows

### Flow 1: Drill-down from chart
1. Пользователь кликает bar в "Cost by Model" → фильтрует таблицу по этой модели
2. URL обновляется: `/costs?model=gpt-4o`

### Flow 2: Navigate to run
1. Пользователь кликает row в таблице → переход на `/runs/{run_id}`
2. Back button → возврат на `/costs` с сохранением фильтров (state preservation)

### Flow 3: Budget alert
1. Если budget usage > 80% → KPI card подсвечивается `colors.danger.bg`
2. Toast notification при первом рендере если > 90%: "Budget is 92% used"

---

## 14. Implementation Notes for frontend-dev

1. **Начать с**: `CostDashboardPage` + route + sidebar link
2. **Затем**: KPI cards (самые простые, сразу видимый результат)
3. **Потом**: Charts (переиспользовать Recharts паттерн из Dashboard)
4. **Далее**: Table (самый сложный — сортировка, фильтры, responsive)
5. **Последним**: Budget section + export + drill-down interactions

**Estimated effort**: 3-4 часа для полной реализации
