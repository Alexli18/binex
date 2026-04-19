# Loop Container UI — Design Plan (018-loop-container)

> Для frontend-dev. Создан UI/UX Designer на основе полного аудита `ui/src/`.

---

## 0. Архитектурный контекст

### Текущее состояние Editor
- **React Flow v11** (`reactflow@11.11.4`) — два графа: EditorCanvas (редактирование) + WorkflowGraph (read-only)
- **Node types**: единственный тип `editable` (регистрация в `EditorCanvas.tsx:16`)
- **Drag & drop**: `NodePalette` → `application/reactflow` → `EditorCanvas.onDrop` → создание Node с `type: 'editable'`
- **Yaml↔Graph sync**: `graphToYaml()` (lib/graph-to-yaml.ts) + `yamlToRfGraph()` (WorkflowEditor.tsx:61-102)
- **Уведомление об изменениях**: `CustomEvent('binex:node-data-change')` → debounced sync → YAML
- **WorkflowEditorContext**: минимальный (только `mcpServerNames: string[]`)
- **Модалки**: SaveAsModal, ReplayModal (custom div), NewRunModal (shadcn Dialog)
- **Design tokens**: `lib/design-tokens.ts` — statusColors, nodeTypeColors, surface, chartColors

### Ограничения React Flow v11
- **Нет нативных GroupNode** — нужен кастомный parentNode механизм
- **parentNode + extent**: RF поддерживает `parentNode: string` на ноде + `extent: 'parent'` для ограничения позиции дочерних нод внутри parent
- **Позиция дочерних** — относительна parent (не абсолютна)
- **z-index**: parent рендерится ПОД дочерними — нужен правильный порядок в массиве nodes

---

## 1. Новые компоненты

### 1.1 LoopContainerNode (`components/editor/LoopContainerNode.tsx`)
**Тип**: React Flow custom node (регистрируется как `nodeTypes.loopContainer`)
**Назначение**: Визуальный контейнер на канвасе — пунктирная рамка с header и footer badge

### 1.2 LoopConfigModal (`components/editor/LoopConfigModal.tsx`)
**Тип**: Обязательный модал при создании loop
**Назначение**: Настройка exit condition + max iterations + тест condition

### 1.3 ExitConditionBuilder (`components/editor/ExitConditionBuilder.tsx`)
**Тип**: Inline-форма внутри LoopConfigModal
**Назначение**: Конструктор JSONPath + оператор + значение

### 1.4 LoopRuntimeBadge (`components/editor/LoopRuntimeBadge.tsx`)
**Тип**: Компонент для отображения runtime-состояния
**Назначение**: iteration counter, progress bar, cost display

### 1.5 LoopFooterBadge (`components/editor/LoopFooterBadge.tsx`)
**Тип**: Статический badge в нижней части контейнера
**Назначение**: Показывает exit condition + max iterations (edit mode) или runtime state

---

## 2. LoopContainerNode — детальный дизайн

### React Flow интеграция

```typescript
// EditorCanvas.tsx — расширить rfNodeTypes
const rfNodeTypes = {
  editable: EditableNode,
  loopContainer: LoopContainerNode,  // NEW
};
```

**Используем parentNode API** React Flow:
- Loop контейнер — обычная Node с `type: 'loopContainer'`
- Дочерние ноды внутри loop получают `parentNode: loopId` + `extent: 'parent'`
- Позиция дочерних — RELATIVE к parent (x=50, y=80 — от верхнего левого угла loop)

### Интерфейс данных

```typescript
// Новый файл: lib/loop-types.ts

export interface ExitCondition {
  jsonpath: string;       // e.g. "$.score"
  operator: '>=' | '<=' | '>' | '<' | '==' | '!=' | 'contains';
  value: string;          // e.g. "0.9"
}

export interface LoopContainerData {
  label: string;                    // e.g. "refinement_loop"
  exitCondition: ExitCondition | null;
  maxIterations: number;            // hard limit, default 5
  // Runtime fields (from SSE/API during execution)
  runtime?: {
    currentIteration: number;
    currentValue?: string;          // e.g. "0.74"
    status: 'pending' | 'running' | 'completed' | 'failed';
    totalCost?: number;
  };
}
```

### Визуальная структура

```
┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│  ↻ refinement_loop          [⚙] [✕]             │
│                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  Node A  │───→│  Node B  │───→│  Node C  │   │
│  └──────────┘    └──────────┘    └──────────┘   │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ ✓ exit: score ≥ 0.9 | max: 5               │ │
│  └─────────────────────────────────────────────┘ │
└─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

### Tailwind стили

```typescript
// Container border — dashed, teal color (unique for loop)
const LOOP_COLOR = '#14b8a6'; // teal-500

// Container classes
const containerClasses = cn(
  'rounded-xl border-2 border-dashed',
  'bg-slate-900/50',           // semi-transparent background
  'shadow-lg shadow-black/10',
  'min-w-[400px] min-h-[200px]',
  'relative',
);
// border color: style={{ borderColor: LOOP_COLOR }}

// Header
const headerClasses = cn(
  'flex items-center justify-between',
  'px-3 py-2',
  'bg-slate-800/60 rounded-t-xl',
  'border-b border-dashed border-teal-500/30',
);

// Footer badge (valid condition)
const footerValidClasses = cn(
  'mx-3 mb-2 px-3 py-1.5 rounded-md',
  'bg-emerald-500/10 border border-emerald-500/30',
  'text-[11px] text-emerald-400',
);

// Footer badge (no condition — error)
const footerErrorClasses = cn(
  'mx-3 mb-2 px-3 py-1.5 rounded-md',
  'bg-red-500/10 border border-red-500/30',
  'text-[11px] text-red-400',
);
```

### Handles

```typescript
// Top handle — input to the loop (from outside nodes)
<Handle type="target" position={Position.Top}
  className="!bg-teal-500 !border-teal-400" />

// Bottom handle — output from the loop (to outside nodes)
<Handle type="source" position={Position.Bottom}
  className="!bg-teal-500 !border-teal-400" />
```

### Размеры контейнера
- **Начальный размер**: 450×250px (width × height)
- **Авто-расширение**: Loop container должен расширяться когда дочерние ноды перетаскиваются к краям
- **Реализация**: `onNodesChange` слушает позиции дочерних нод и обновляет `style.width/height` parent'а
- **Минимальный размер**: 400×200px
- **Padding для дочерних**: top=70px (header), bottom=50px (footer), left/right=20px

### Header компонент

```tsx
<div className={headerClasses}>
  <div className="flex items-center gap-2">
    <RefreshCw size={14} className="text-teal-400" />
    <input
      value={label}
      onChange={(e) => updateLabel(e.target.value)}
      className="bg-transparent text-sm font-medium text-teal-300
                 border-none outline-none w-40"
    />
  </div>
  <div className="flex items-center gap-1.5">
    <button onClick={openConfig} title="Loop settings">
      <Settings size={13} className="text-slate-400 hover:text-teal-300" />
    </button>
    <button onClick={handleDelete} title="Delete loop">
      <Trash2 size={13} className="text-red-500 hover:text-red-400" />
    </button>
  </div>
</div>
```

---

## 3. LoopConfigModal — детальный layout

### Когда открывается
1. **При создании** (drag & drop) — ОБЯЗАТЕЛЬНЫЙ, нельзя закрыть без заполнения
2. **По клику на ⚙** в header loop container — редактирование

### Layout

```
┌──────────────────────────────────────────────────┐
│  ↻ Configure Loop                          [✕]   │
├──────────────────────────────────────────────────┤
│                                                    │
│  Loop Name                                         │
│  ┌──────────────────────────────────────────┐     │
│  │ refinement_loop                           │     │
│  └──────────────────────────────────────────┘     │
│                                                    │
│  ─── Exit Condition ────────────────────────       │
│                                                    │
│  JSONPath        Operator      Value               │
│  ┌────────────┐  ┌─────────┐  ┌──────────┐       │
│  │ $.score    │  │ >=    ▾ │  │ 0.9      │       │
│  └────────────┘  └─────────┘  └──────────┘       │
│                                                    │
│  ─── Limits ────────────────────────────────       │
│                                                    │
│  Max Iterations                                    │
│  ┌──────────────────────────────────────────┐     │
│  │ 5                                         │     │
│  └──────────────────────────────────────────┘     │
│  Hard limit. Loop stops regardless of condition.   │
│                                                    │
│  ─── Test Condition ────────────────────────       │
│                                                    │
│  [Select artifact ▾]       [Test]                  │
│                                                    │
│  Result: $.score = 0.74 → ✗ (0.74 < 0.9)         │
│                                                    │
├──────────────────────────────────────────────────┤
│                          [Cancel]  [Save Loop]     │
└──────────────────────────────────────────────────┘
```

### Реализация

```typescript
interface LoopConfigModalProps {
  open: boolean;
  onClose: () => void;           // disabled при mode='create' до заполнения
  onSave: (config: LoopContainerData) => void;
  mode: 'create' | 'edit';
  initialData?: LoopContainerData;
  availableArtifacts?: Array<{   // для Test функции
    run_id: string;
    node_id: string;
    content: unknown;
  }>;
}
```

### Валидация
- **Loop Name**: обязательное, `^[a-z][a-z0-9_]*$` (snake_case)
- **JSONPath**: обязательное, начинается с `$.`
- **Operator**: обязательное, один из 7 операторов
- **Value**: обязательное, непустое
- **Max Iterations**: обязательное, integer 1-100
- **Cancel** при `mode='create'`: удаляет loop ноду с канваса

### Компонент — shadcn Dialog

Используем `Dialog` из `@/components/ui/dialog` (уже есть в проекте):

```tsx
<Dialog open={open} onOpenChange={handleOpenChange}>
  <DialogContent className="sm:max-w-[500px] bg-slate-900 border-slate-700">
    <DialogHeader>
      <DialogTitle className="flex items-center gap-2 text-teal-300">
        <RefreshCw size={18} />
        Configure Loop
      </DialogTitle>
    </DialogHeader>
    {/* ... form fields ... */}
    <DialogFooter>
      <Button variant="ghost" onClick={handleCancel}
        disabled={mode === 'create' && !isValid}>
        Cancel
      </Button>
      <Button onClick={handleSave} disabled={!isValid}
        className="bg-teal-600 hover:bg-teal-500">
        {mode === 'create' ? 'Create Loop' : 'Save Changes'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

## 4. ExitConditionBuilder

### Inline-компонент внутри LoopConfigModal

```typescript
interface ExitConditionBuilderProps {
  value: ExitCondition;
  onChange: (condition: ExitCondition) => void;
  error?: string;
}
```

### Три поля в одной строке

```tsx
<div className="grid grid-cols-[1fr_100px_100px] gap-2">
  {/* JSONPath */}
  <div>
    <label className="text-[11px] text-slate-400 mb-1 block">JSONPath</label>
    <Input
      value={value.jsonpath}
      onChange={(e) => onChange({ ...value, jsonpath: e.target.value })}
      placeholder="$.score"
      className="h-8 bg-slate-800 border-slate-600 font-mono text-sm"
    />
  </div>

  {/* Operator */}
  <div>
    <label className="text-[11px] text-slate-400 mb-1 block">Operator</label>
    <Select value={value.operator} onValueChange={(op) => onChange({ ...value, operator: op })}>
      <SelectTrigger className="h-8 bg-slate-800 border-slate-600">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {OPERATORS.map((op) => (
          <SelectItem key={op} value={op}>{op}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>

  {/* Value */}
  <div>
    <label className="text-[11px] text-slate-400 mb-1 block">Value</label>
    <Input
      value={value.value}
      onChange={(e) => onChange({ ...value, value: e.target.value })}
      placeholder="0.9"
      className="h-8 bg-slate-800 border-slate-600 font-mono text-sm"
    />
  </div>
</div>
```

### Операторы

```typescript
const OPERATORS = ['>=', '<=', '>', '<', '==', '!=', 'contains'] as const;
```

### Тест condition

```tsx
<div className="space-y-2 mt-3">
  <div className="flex items-center gap-2">
    {/* Dropdown: select artifact from last run */}
    <Select value={selectedArtifact} onValueChange={setSelectedArtifact}>
      <SelectTrigger className="h-8 flex-1 bg-slate-800 border-slate-600 text-xs">
        <SelectValue placeholder="Select artifact to test..." />
      </SelectTrigger>
      <SelectContent>
        {artifacts.map((a) => (
          <SelectItem key={a.node_id} value={a.node_id}>
            {a.node_id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
    <Button size="sm" variant="outline" onClick={runTest}
      className="h-8 text-xs border-slate-600">
      Test
    </Button>
  </div>

  {/* Test result */}
  {testResult && (
    <div className={cn(
      'px-3 py-2 rounded-md text-xs font-mono',
      testResult.pass
        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
        : 'bg-red-500/10 text-red-400 border border-red-500/20'
    )}>
      {testResult.expression} → {testResult.pass ? '✓' : '✗'} ({testResult.details})
    </div>
  )}
</div>
```

### Логика теста (client-side)

```typescript
// lib/loop-utils.ts
export function evaluateExitCondition(
  condition: ExitCondition,
  artifact: unknown,
): { pass: boolean; expression: string; details: string } {
  // 1. Извлечь значение по JSONPath (jsonpath-plus или manual $.key parsing)
  // 2. Сравнить по operator
  // 3. Вернуть результат с деталями
}
```

> **Зависимость**: нужна библиотека `jsonpath-plus` (npm) или простой парсер для `$.key.subkey`. Рекомендую начать с простого `$.key` парсера через `lodash.get` или manual split, без полноценного JSONPath.

---

## 5. LoopRuntimeBadge — runtime display

### Когда отображается
- Заменяет footer badge во время выполнения (когда `runtime` поле присутствует)
- Данные приходят через SSE events от API

### Визуальная структура

```
┌─────────────────────────────────────────────┐
│  ↻ iteration 3 / 5                          │
│  ████████████░░░░░░░░  score: 0.74 → ≥ 0.9 │
│                                    $0.032   │
└─────────────────────────────────────────────┘
```

### Реализация

```tsx
interface LoopRuntimeBadgeProps {
  currentIteration: number;
  maxIterations: number;
  exitCondition: ExitCondition;
  currentValue?: string;
  totalCost?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

function LoopRuntimeBadge({
  currentIteration, maxIterations, exitCondition,
  currentValue, totalCost, status
}: LoopRuntimeBadgeProps) {
  const progress = (currentIteration / maxIterations) * 100;

  return (
    <div className={cn(
      'mx-3 mb-2 px-3 py-2 rounded-md space-y-1.5',
      status === 'running' && 'bg-blue-500/10 border border-blue-500/20',
      status === 'completed' && 'bg-emerald-500/10 border border-emerald-500/20',
      status === 'failed' && 'bg-red-500/10 border border-red-500/20',
    )}>
      {/* Iteration counter */}
      <div className="flex items-center justify-between text-[11px]">
        <span className={cn(
          'flex items-center gap-1 font-medium',
          status === 'running' && 'text-blue-400',
          status === 'completed' && 'text-emerald-400',
          status === 'failed' && 'text-red-400',
        )}>
          <RefreshCw size={11} className={status === 'running' ? 'animate-spin' : ''} />
          iteration {currentIteration} / {maxIterations}
        </span>
        {totalCost != null && (
          <span className="text-slate-500">${(totalCost ?? 0).toFixed(4)}</span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            status === 'running' && 'bg-blue-500',
            status === 'completed' && 'bg-emerald-500',
            status === 'failed' && 'bg-red-500',
          )}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {/* Current value vs target */}
      {currentValue && (
        <div className="text-[10px] text-slate-400 font-mono">
          {exitCondition.jsonpath.replace('$.', '')}: {currentValue} →{' '}
          <span className="text-slate-300">
            {exitCondition.operator} {exitCondition.value}
          </span>
        </div>
      )}
    </div>
  );
}
```

---

## 6. Drag & Drop — добавление loop на канвас

### 6.1 NodePalette — новый item

```typescript
// NodePalette.tsx — добавить в NODE_TYPES (или отдельную секцию)

import { RefreshCw } from 'lucide-react';

// Новая секция "Containers" под существующими Nodes
export const CONTAINER_TYPES: NodeTypeConfig[] = [
  {
    type: 'loopContainer',
    label: 'Loop',
    icon: RefreshCw,
    color: '#14b8a6',              // teal-500
    agentPrefix: 'loop://',        // виртуальный prefix
    defaultAgent: 'loop://container',
  },
];
```

### NodePalette layout — две секции

```tsx
<div className="flex flex-col gap-1 p-2 border-r border-slate-700 bg-slate-900 w-48 shrink-0">
  {/* Existing: Nodes */}
  <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
    Nodes
  </div>
  {NODE_TYPES.map(/* ... existing ... */)}

  {/* NEW: Containers */}
  <div className="px-2 py-1.5 mt-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
    Containers
  </div>
  {CONTAINER_TYPES.map((ct) => {
    const Icon = ct.icon;
    return (
      <div key={ct.type} draggable
        onDragStart={(e) => onDragStart(e, ct)}
        className="flex items-center gap-2 px-2 py-2 rounded cursor-grab
                   active:cursor-grabbing hover:bg-slate-800 transition-colors
                   border border-dashed border-transparent hover:border-teal-500/40"
        title={`Drag to add ${ct.label} container`}
      >
        <Icon size={18} style={{ color: ct.color }} className="shrink-0" />
        <span className="text-sm text-slate-300">{ct.label}</span>
      </div>
    );
  })}
</div>
```

### 6.2 EditorCanvas.onDrop — обработка loop

```typescript
// EditorCanvas.tsx — расширить onDrop

const onDrop = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  const raw = event.dataTransfer.getData('application/reactflow');
  if (!raw) return;
  const ntConfig: NodeTypeConfig = JSON.parse(raw);
  const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
  nodeIdCounter += 1;

  if (ntConfig.type === 'loopContainer') {
    // Создаём loop container node
    const id = `loop_${nodeIdCounter}`;
    const newNode: Node = {
      id,
      type: 'loopContainer',
      position,
      style: { width: 450, height: 250 },
      data: {
        label: id,
        exitCondition: null,
        maxIterations: 5,
      } as LoopContainerData,
    };
    setRfNodes((nds) => [...nds, newNode]);
    // Открываем обязательный LoopConfigModal
    setPendingLoopConfig(id);  // state в EditorCanvas
    return;
  }

  // ... existing node creation logic ...
}, [/* deps */]);
```

### 6.3 Перетаскивание нод внутрь loop

**Механизм**: при drop обычной ноды проверяем, попадает ли позиция внутрь bounds loop container.

```typescript
// lib/loop-utils.ts

export function findParentLoop(
  dropPosition: { x: number; y: number },
  loopNodes: Node[],
): string | null {
  for (const loop of loopNodes) {
    const w = (loop.style?.width as number) || 450;
    const h = (loop.style?.height as number) || 250;
    if (
      dropPosition.x >= loop.position.x &&
      dropPosition.x <= loop.position.x + w &&
      dropPosition.y >= loop.position.y &&
      dropPosition.y <= loop.position.y + h
    ) {
      return loop.id;
    }
  }
  return null;
}
```

**В onDrop** (для обычных нод):

```typescript
// После создания newNode, проверяем parent loop
const loopNodes = rfNodes.filter((n) => n.type === 'loopContainer');
const parentLoop = findParentLoop(position, loopNodes);

if (parentLoop) {
  // Конвертируем позицию в relative
  const loop = loopNodes.find((n) => n.id === parentLoop)!;
  newNode.parentNode = parentLoop;
  newNode.extent = 'parent';
  newNode.position = {
    x: position.x - loop.position.x,
    y: position.y - loop.position.y,
  };
}
```

### 6.4 Drag existing node INTO loop

При `onNodeDragStop` проверяем, оказалась ли нода внутри loop:

```typescript
const onNodeDragStop = useCallback((_: unknown, node: Node) => {
  if (node.type === 'loopContainer') return; // loop сам не вкладывается

  const loopNodes = rfNodes.filter((n) => n.type === 'loopContainer');
  const absolutePos = getAbsolutePosition(node, rfNodes); // учитываем parentNode

  // Проверяем: нода уже в loop? Или переместилась в другой/из loop?
  const newParent = findParentLoop(absolutePos, loopNodes);
  const currentParent = node.parentNode || null;

  if (newParent !== currentParent) {
    setRfNodes((nds) => nds.map((n) => {
      if (n.id !== node.id) return n;
      if (newParent) {
        const loop = loopNodes.find((l) => l.id === newParent)!;
        return {
          ...n,
          parentNode: newParent,
          extent: 'parent' as const,
          position: {
            x: absolutePos.x - loop.position.x,
            y: absolutePos.y - loop.position.y,
          },
        };
      } else {
        // Вытащили из loop
        const { parentNode, extent, ...rest } = n;
        return { ...rest, position: absolutePos };
      }
    }));
    onGraphChange();
  }
}, [rfNodes, setRfNodes, onGraphChange]);
```

### 6.5 Запрет вложенных loops

```typescript
// В onDrop для loopContainer:
const loopNodes = rfNodes.filter((n) => n.type === 'loopContainer');
const parentLoop = findParentLoop(position, loopNodes);

if (parentLoop) {
  // Показать toast-предупреждение
  toast.error('Nested loops are not supported');
  return; // Не создаём
}
```

### 6.6 Предупреждение о human approval внутри loop

```typescript
// В onDrop для human-approve внутри loop:
if (parentLoop && ntConfig.type === 'human-approve') {
  toast.warning(
    'Human approval inside a loop will pause every iteration. Are you sure?',
    { duration: 5000 }
  );
  // Разрешаем, но предупреждаем
}
```

---

## 7. Цвета и design tokens

### Расширение design-tokens.ts

```typescript
// Добавить в nodeTypeColors:
loop: {
  bg: 'bg-teal-500/15',
  text: 'text-teal-400',
  border: 'border-teal-500/40',
  icon: 'text-teal-400',
},
```

### Цветовая палитра loop

| Элемент | Цвет | Tailwind |
|---------|-------|----------|
| Container border | teal-500 | `border-teal-500` |
| Container bg | slate-900/50 | `bg-slate-900/50` |
| Header text | teal-300 | `text-teal-300` |
| Icon (↻) | teal-400 | `text-teal-400` |
| Footer badge (valid) | emerald-400 on emerald/10 | `text-emerald-400 bg-emerald-500/10` |
| Footer badge (error) | red-400 on red/10 | `text-red-400 bg-red-500/10` |
| Runtime progress | blue-500 | `bg-blue-500` |
| Cost text | slate-500 | `text-slate-500` |
| Dashed border | — | `border-dashed` |

### Почему teal
- Уникальный цвет — не конфликтует с existing node types:
  - violet (LLM), cyan (local), indigo (A2A), amber (human)
  - emerald (completed), blue (running), red (failed)
- Семантика: teal ассоциируется с "цикличностью", "обновлением"

---

## 8. YAML ↔ Graph sync

### 8.1 YAML формат для loop (определяется backend, но UI должен уметь парсить/генерить)

```yaml
name: my-workflow
nodes:
  fetch_data:
    agent: llm://openai/gpt-4
    outputs: [output]

  refinement_loop:
    type: loop                          # NEW: тип loop
    exit_condition:
      jsonpath: "$.score"
      operator: ">="
      value: "0.9"
    max_iterations: 5
    nodes:                              # вложенные ноды
      evaluate:
        agent: llm://openai/gpt-4
        depends_on: [fetch_data]
        outputs: [output]
      refine:
        agent: llm://openai/gpt-4
        depends_on: [evaluate]
        outputs: [output]

  final_output:
    agent: human://output
    depends_on: [refinement_loop]
```

### 8.2 graphToYaml — расширение

```typescript
// graph-to-yaml.ts — добавить обработку loop nodes

export function graphToYaml(
  nodes: Node[], edges: Edge[],
  workflowName = 'my-workflow',
  options?: GraphToYamlOptions,
): string {
  const nodesObj: Record<string, Record<string, unknown>> = {};
  const deps: Record<string, string[]> = { /* ... */ };

  // Разделяем loop containers и обычные ноды
  const loopContainers = nodes.filter((n) => n.type === 'loopContainer');
  const regularNodes = nodes.filter((n) => n.type !== 'loopContainer');

  // Обычные ноды без parentNode → top-level
  for (const node of regularNodes) {
    if (node.parentNode) continue; // обрабатываются внутри loop
    nodesObj[node.data.label] = buildNodeEntry(node, edges, nodes);
  }

  // Loop containers
  for (const loop of loopContainers) {
    const loopData = loop.data as LoopContainerData;
    const childNodes = regularNodes.filter((n) => n.parentNode === loop.id);

    const loopEntry: Record<string, unknown> = {
      type: 'loop',
      max_iterations: loopData.maxIterations,
    };

    if (loopData.exitCondition) {
      loopEntry.exit_condition = {
        jsonpath: loopData.exitCondition.jsonpath,
        operator: loopData.exitCondition.operator,
        value: loopData.exitCondition.value,
      };
    }

    // Nested nodes
    const nestedNodes: Record<string, Record<string, unknown>> = {};
    for (const child of childNodes) {
      nestedNodes[child.data.label] = buildNodeEntry(child, edges, nodes);
    }
    loopEntry.nodes = nestedNodes;

    // External deps on the loop container itself
    if (deps[loop.id]?.length) {
      loopEntry.depends_on = deps[loop.id];
    }

    nodesObj[loopData.label] = loopEntry;
  }

  // ... rest same ...
}
```

### 8.3 yamlToRfGraph — расширение

```typescript
// WorkflowEditor.tsx — yamlToRfGraph

function yamlToRfGraph(yamlContent: string): YamlParseResult {
  // ... existing parsing ...

  for (const [id, spec] of entries) {
    if ((spec as any).type === 'loop') {
      // Create loop container node
      const loopNode: Node = {
        id,
        type: 'loopContainer',
        position: { x: 100, y: yOffset },
        style: { width: 450, height: 250 },
        data: {
          label: id,
          exitCondition: (spec as any).exit_condition || null,
          maxIterations: (spec as any).max_iterations || 5,
        } as LoopContainerData,
      };
      nodes.push(loopNode);

      // Create child nodes inside loop
      const nestedNodes = (spec as any).nodes || {};
      let childY = 80;
      for (const [childId, childSpec] of Object.entries(nestedNodes)) {
        const agent = (childSpec as any).agent || 'local://echo';
        const { nodeType, color } = agentToNodeType(agent);
        nodes.push({
          id: childId,
          type: 'editable',
          position: { x: 50, y: childY },
          parentNode: id,
          extent: 'parent',
          data: { label: childId, nodeType, agent, config: {}, color },
        });
        childY += 120;
      }

      yOffset += 300; // skip space for loop
    } else {
      // ... existing node creation ...
    }
  }

  return { nodes, edges, mcpServers, schedule };
}
```

---

## 9. Изменения в существующих файлах

### 9.1 EditorCanvas.tsx

```diff
+ import { LoopContainerNode } from './LoopContainerNode';
+ import { LoopConfigModal } from './LoopConfigModal';
+ import type { LoopContainerData } from '@/lib/loop-types';

- const rfNodeTypes = { editable: EditableNode };
+ const rfNodeTypes = {
+   editable: EditableNode,
+   loopContainer: LoopContainerNode,
+ };

// Добавить state:
+ const [pendingLoopConfig, setPendingLoopConfig] = useState<string | null>(null);

// Расширить onDrop для loopContainer (см. секцию 6.2)
// Добавить onNodeDragStop (см. секцию 6.4)

// Добавить LoopConfigModal в return:
+ {pendingLoopConfig && (
+   <LoopConfigModal
+     open
+     mode="create"
+     onClose={() => {
+       // Удаляем незавершённый loop
+       setRfNodes((nds) => nds.filter((n) => n.id !== pendingLoopConfig));
+       setPendingLoopConfig(null);
+     }}
+     onSave={(config) => {
+       setRfNodes((nds) => nds.map((n) =>
+         n.id === pendingLoopConfig ? { ...n, data: config } : n
+       ));
+       setPendingLoopConfig(null);
+       onGraphChange();
+     }}
+   />
+ )}
```

### 9.2 NodePalette.tsx

```diff
+ import { RefreshCw } from 'lucide-react';
+ export const CONTAINER_TYPES: NodeTypeConfig[] = [...]; // см. секцию 6.1
// Добавить секцию "Containers" под "Nodes" (см. секцию 6.1)
```

### 9.3 graph-to-yaml.ts

```diff
+ import type { LoopContainerData } from './loop-types';
// Добавить обработку loop containers (см. секцию 8.2)
```

### 9.4 WorkflowEditor.tsx — yamlToRfGraph

```diff
// Добавить парсинг type: loop нод (см. секцию 8.3)
```

### 9.5 design-tokens.ts

```diff
export const nodeTypeColors = {
  // ... existing ...
+ loop: {
+   bg: 'bg-teal-500/15',
+   text: 'text-teal-400',
+   border: 'border-teal-500/40',
+   icon: 'text-teal-400',
+ },
};
```

### 9.6 WorkflowEditorContext.tsx (опционально)

Если нужен доступ к loop data из дочерних нод:

```diff
interface WorkflowEditorContextValue {
  mcpServerNames: string[];
+ loopContainers: Array<{ id: string; label: string }>;
}
```

---

## 10. Новые файлы — полный список

| Файл | Тип | Описание |
|------|-----|----------|
| `ui/src/lib/loop-types.ts` | Types | ExitCondition, LoopContainerData interfaces |
| `ui/src/lib/loop-utils.ts` | Utils | findParentLoop, evaluateExitCondition, getAbsolutePosition |
| `ui/src/components/editor/LoopContainerNode.tsx` | Component | React Flow custom node — container с header/footer |
| `ui/src/components/editor/LoopConfigModal.tsx` | Component | Modal для настройки loop (обязательный при создании) |
| `ui/src/components/editor/ExitConditionBuilder.tsx` | Component | JSONPath + operator + value builder |
| `ui/src/components/editor/LoopRuntimeBadge.tsx` | Component | Runtime: iteration counter + progress + cost |
| `ui/src/components/editor/LoopFooterBadge.tsx` | Component | Static footer badge (condition summary) |

---

## 11. Порядок реализации

### Phase 1: Core (минимально работающий loop)
1. `loop-types.ts` — типы данных
2. `LoopContainerNode.tsx` — визуальный контейнер (без runtime)
3. `LoopFooterBadge.tsx` — статический footer
4. Регистрация в `EditorCanvas.tsx` — nodeTypes
5. `NodePalette.tsx` — секция Containers + drag
6. `EditorCanvas.tsx` — onDrop для loop + parentNode logic

### Phase 2: Config Modal
7. `ExitConditionBuilder.tsx`
8. `LoopConfigModal.tsx` — полный modal с валидацией
9. Интеграция modal в EditorCanvas (pendingLoopConfig state)

### Phase 3: YAML sync
10. `loop-utils.ts` — findParentLoop, evaluateExitCondition
11. `graph-to-yaml.ts` — сериализация loop + nested nodes
12. `yamlToRfGraph` — парсинг loop из YAML

### Phase 4: Drag into loop
13. onNodeDragStop — перетаскивание нод внутрь/из loop
14. Валидации: запрет вложенных loops, предупреждение human-approve

### Phase 5: Runtime
15. `LoopRuntimeBadge.tsx` — iteration counter + progress
16. Интеграция с SSE events для live updates
17. `design-tokens.ts` — loop color tokens

---

## 12. Accessibility & Edge Cases

### Keyboard
- **Tab**: навигация между полями в LoopConfigModal
- **Escape**: закрыть modal (только в edit mode, не при создании)
- **Delete**: удалить loop container (с confirmation если есть дочерние ноды)

### Edge Cases
- **Удаление loop**: удаляет ВСЕ дочерние ноды + edges (confirmation dialog)
- **Удаление ноды из loop**: обычное удаление, loop container остаётся
- **Пустой loop**: разрешён, но footer badge показывает "⚠ empty loop"
- **Loop без exit condition**: красный badge "⚠ no exit condition"
- **Undo/Redo**: React Flow не поддерживает нативно, пока не реализуем
- **Copy/Paste loop**: пока не поддерживаем (v2)
- **Resize loop**: через drag corner handle (React Flow `NodeResizer` компонент)

### Responsive
- LoopConfigModal: `sm:max-w-[500px]` — на мобильных fullscreen
- LoopContainerNode: minimum 400×200px, максимум определяется содержимым

---

## 13. Зависимости npm

Новые пакеты НЕ требуются. Всё решается существующими:
- `reactflow` — parentNode, extent, NodeResizer
- `js-yaml` — YAML parsing/generation
- `lucide-react` — RefreshCw, Settings icons
- `sonner` — toast notifications
- `@radix-ui/react-dialog` — уже есть (shadcn Dialog)
- `@radix-ui/react-select` — уже есть (shadcn Select)

> JSONPath evaluator: простой `$.key.subkey` парсер в `loop-utils.ts` (10-15 строк), без внешних зависимостей.

---

## 14. Тестирование (рекомендации для QA)

### Unit Tests
- `ExitConditionBuilder`: валидация полей, изменение оператора
- `evaluateExitCondition`: все 7 операторов + edge cases (null, undefined, string/number)
- `findParentLoop`: hit/miss, overlapping loops (должен быть запрещён)
- `graphToYaml` с loop nodes: правильная YAML структура
- `yamlToRfGraph` с loop YAML: правильные parentNode, extent, позиции

### Integration Tests
- Drag loop → modal opens → fill → save → loop appears on canvas
- Drag node into loop → parentNode set → YAML updated
- Drag node out of loop → parentNode removed
- Nested loop attempt → error toast
- Delete loop → children removed
- YAML mode → visual mode → loop preserved
