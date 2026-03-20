# Binex UI/UX Improvement Log

## Iteration 1 — 2026-03-20
**Change:** Added colored accent strip, icon badge with tinted background, and type subtitle to collapsed nodes for visual hierarchy
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — nodes now have clear type identity at a glance
**Decision:** kept
**Reason:** Previously all collapsed nodes were flat boxes with only a thin border color difference. Now each node has: (1) a 3px colored accent bar at the top for instant type recognition, (2) an icon in a tinted rounded badge instead of bare icon, (3) a two-line layout with node name (prominent) and type label (secondary) creating clear visual hierarchy. No new dependencies, single file change.

## Iteration 2 — 2026-03-20
**Change:** Unified expanded node header with collapsed node style — accent strip, icon badge, type subtitle
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — expanded and collapsed views now feel like the same component
**Decision:** kept
**Reason:** Expanded header previously had a bare icon and thick colored border, inconsistent with the new collapsed style. Now uses the same accent strip + icon badge + type label pattern. Also removed heavy border-2 in favor of subtle border with tinted background for a more refined look.

## Iteration 3 — 2026-03-20
**Change:** Styled edge connections — smoothstep routing, 2px stroke, arrow markers for clear directionality
**File:** ui/src/components/editor/EditorCanvas.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — connections now have visible arrows and route cleanly between nodes
**Decision:** kept
**Reason:** Default React Flow edges are thin, straight bezier curves with no arrowheads — hard to follow direction. Added `defaultEdgeOptions` with smoothstep type (routes around nodes), 2px slate-600 stroke, and ArrowClosed markers. Single constant, no logic changes.

## Iteration 4 — 2026-03-20
**Change:** Enhanced node palette — added descriptions, icon badges, drag grip indicator, wider sidebar
**File:** ui/src/components/editor/NodePalette.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — each palette item now self-explanatory
**Decision:** kept
**Reason:** Palette items were icon+label only, no context for new users. Added `description` field to NodeTypeConfig, visible as a second line under each label. Icon now in tinted badge (matching node style). Added GripVertical indicator on hover to signal draggability. Sidebar widened from w-48 to w-52 to fit descriptions. Category header renamed "Nodes" → "Agents" for clarity.

## Iteration 5 — 2026-03-20
**Change:** Added empty canvas state — icon + "Drag a node from the sidebar to get started" message
**File:** ui/src/components/editor/EditorCanvas.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — empty canvas is no longer confusing
**Decision:** kept
**Reason:** When canvas has no nodes, it was just a blank grid with no guidance. Now shows a centered MousePointerClick icon with two lines of instructional text. Uses pointer-events-none so drop events still work through the overlay. Disappears as soon as first node is added.

## Iteration 6 — 2026-03-20
**Change:** Added drop zone highlight when dragging a node over the canvas
**File:** ui/src/components/editor/EditorCanvas.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — canvas now visually responds to drag events
**Decision:** kept
**Reason:** Dragging a node from the palette onto the canvas gave zero visual feedback — users couldn't tell if they were in a valid drop zone. Now the canvas shows a blue ring (ring-2 ring-blue-500/30) and the grid background tints blue when dragging over. Resets on drag leave and drop. Simple state + CSS, no logic changes.

## Iteration 7 — 2026-03-20
**Change:** Improved connection handles — larger (w-2.5 h-2.5), dark border, blue hover highlight
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — handles now discoverable and interactive-feeling
**Decision:** kept
**Reason:** Default handles were tiny grey dots that blended into the node border. Now 10px with slate-700 border, slate-400 fill, and blue hover state. Makes connection points discoverable and signals interactivity. All 4 handles (2 collapsed + 2 expanded) updated consistently.

## Iteration 8 — 2026-03-20
**Change:** Switched canvas background from grid lines to dots pattern — cleaner, more professional
**File:** ui/src/components/editor/EditorCanvas.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — canvas feels intentional, not like a spreadsheet
**Decision:** kept
**Reason:** Grid lines made the canvas feel like a spreadsheet. Dots (BackgroundVariant.Dots, size 1.5, gap 24) are subtler and more common in professional node editors (Figma, Miro). Dot color still tints blue during drag-over for visual feedback consistency.

## Iteration 9 — 2026-03-20
**Change:** Added selected node focus state — blue border + ring glow
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — selected node immediately visible on canvas
**Decision:** kept
**Reason:** Clicking a node showed no visual selection feedback. Now uses React Flow's `selected` prop to apply blue border (border-blue-500/60) and subtle ring glow (ring-2 ring-blue-500/20) on both collapsed and expanded states. Makes it clear which node is active.

## Iteration 10 — 2026-03-20
**Change:** Styled zoom/pan controls — dark theme, rounded, proper hover states
**File:** ui/src/index.css
**Eval:** tsc: pass | vite build: pass | visual: better — controls match the dark theme instead of looking like a white widget
**Decision:** kept
**Reason:** React Flow's default controls are white with light borders — jarring in a slate-950 dark theme. Overrode with slate-800 background, slate-700 borders, proper hover colors, rounded corners, and 28px compact buttons. CSS-only change, no JS modifications.

## Iteration 11 — 2026-03-20
**Change:** Highlight connected edges when a node is selected — blue animated for connected, dimmed for others
**File:** ui/src/components/editor/EditorCanvas.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — data flow paths immediately visible on node selection
**Decision:** kept
**Reason:** When a node was selected, all edges looked the same — impossible to trace data flow. Now connected edges turn blue (#3b82f6), thicken to 2.5px, and animate. Unconnected edges dim to 40% opacity. Uses memoized computation from selected node IDs.

## Iteration 12 — 2026-03-20
**Change:** Smooth collapse/expand animation for node settings sections + hover highlight on headers
**File:** ui/src/components/editor/CollapsibleSection.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — sections open/close smoothly instead of popping
**Decision:** kept
**Reason:** Sections toggled instantly (content appeared/disappeared). Replaced conditional render with CSS grid-template-rows transition (0fr ↔ 1fr) for smooth height animation. Also added hover bg on section headers for better interactivity feedback. Content always rendered (overflow hidden when collapsed) — no layout jank.

## Iteration 13 — 2026-03-20
**Change:** Added helper text to fields and semantic temperature label (precise/balanced/creative)
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — fields now self-documenting
**Decision:** kept
**Reason:** Temperature slider showed only a number (0.7) with no meaning. Now shows "(precise)" for ≤0.3, "(balanced)" for 0.4-1.1, "(creative)" for ≥1.2. Added helper text under Max Tokens ("Maximum response length") and Budget Limit ("Stop this node if cost exceeds limit"). Small additions, big clarity gain for new users.

## Iteration 14 — 2026-03-20
**Change:** Wrapped non-LLM node settings in CollapsibleSections with helper text for all fields
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — all node types now have consistent settings panel structure
**Decision:** kept
**Reason:** Local, Human, A2A node configs were raw divs without the CollapsibleSection wrapper that LLM nodes use. Inconsistent UX. Now all node types use CollapsibleSection with proper titles ("Configuration", "Connection") and every field has a helper description. "Host:Port" renamed to "Endpoint" for clarity.

## Iteration 15 — 2026-03-20
**Change:** Synced palette colors with design tokens — LLM violet, Local cyan, Human amber, A2A indigo
**File:** ui/src/components/editor/NodePalette.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — palette and canvas nodes now share exact same accent colors
**Decision:** kept
**Reason:** Palette used blue (#3b82f6) for LLM while canvas nodes used violet (#8b5cf6). Similar mismatches for Local (green vs cyan), A2A (cyan vs indigo), Human (mixed colors). Created NODE_COLOR constant aligned with design-tokens.ts nodeTypeColors. All human subtypes now consistently amber.

## Iteration 16 — 2026-03-20
**Change:** Added node entrance animation — subtle scale+fade when dropping onto canvas
**Files:** ui/src/index.css, ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — nodes now appear smoothly instead of popping
**Decision:** kept
**Reason:** Dropping a node onto the canvas gave no visual confirmation — it just appeared. Added `node-appear` keyframes (scale 0.92→1, opacity 0→1, 200ms ease-out) applied via `animate-node-appear` class on collapsed nodes. Subtle enough to not feel heavy, noticeable enough to confirm the drop action succeeded.

## Iteration 17 — 2026-03-20
**Change:** Added "Auto-saved" indicator in expanded node footer after settings changes
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — users now see confirmation that changes are applied
**Decision:** kept
**Reason:** program.md says "Save/Apply action should be obvious and feel responsive." Settings auto-save via notifyChange() but with no visual feedback. Now a brief green "Auto-saved" indicator with check icon appears for 1.5s in the expanded node footer after any change. Timer cleanup on unmount prevents leaks.

## Iteration 18 — 2026-03-20
**Change:** Added hint text at bottom of palette — "Drag any agent onto the canvas..."
**File:** ui/src/components/editor/NodePalette.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — new users immediately understand drag interaction
**Decision:** kept
**Reason:** Palette items have GripVertical icon on hover but new users might not realize items are draggable. Added subtle hint text at the bottom of the sidebar (mt-auto pushes it to the bottom). Minimal addition, big discoverability gain.
