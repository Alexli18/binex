import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, Terminal, Repeat, Users, Trophy, RefreshCw, GitBranch, Workflow, Scale, CheckCheck, ListChecks } from 'lucide-react';

export interface NodeTypeConfig {
  type: string;
  subtype?: string;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  agentPrefix: string;
  defaultAgent: string;
  category?: string;
}

// Colors matching UI Kit design system
const NODE_COLOR = {
  llm: '#e8a020',     // amber — primary accent
  local: '#22d3ee',   // cyan
  human: '#22c55e',   // green
  a2a: '#f472b6',     // magenta
  cao: '#f97316',     // orange
  pattern: '#a78bfa', // violet
} as const;

export const NODE_TYPES: NodeTypeConfig[] = [
  { type: 'llm', label: 'LLM Agent', description: 'Call an LLM model', icon: Bot, color: NODE_COLOR.llm, agentPrefix: 'llm://', defaultAgent: 'llm://openrouter/google/gemma-3-27b-it:free' },
  { type: 'local', label: 'Local Script', description: 'Python function', icon: Monitor, color: NODE_COLOR.local, agentPrefix: 'local://', defaultAgent: 'local://echo' },
  { type: 'human-approve', subtype: 'approve', label: 'Approve', description: 'Human approval gate', icon: ShieldCheck, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://approve' },
  { type: 'human-input', subtype: 'input', label: 'Human Input', description: 'Free-form input', icon: MessageSquare, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://input' },
  { type: 'human-output', subtype: 'output', label: 'Output', description: 'Display results', icon: Eye, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://output' },
  { type: 'a2a', label: 'A2A Agent', description: 'Remote agent', icon: Globe, color: NODE_COLOR.a2a, agentPrefix: 'a2a://', defaultAgent: 'a2a://localhost:8001' },
  { type: 'cao', label: 'CAO Agent', description: 'CLI orchestrator', icon: Terminal, color: NODE_COLOR.cao, agentPrefix: 'cao://', defaultAgent: 'cao://default', category: 'CLI AGENTS' },
  // Patterns
  { type: 'pattern-critic', label: 'Critic', description: 'Draft→critique→refine', icon: Repeat, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://critic', category: 'PATTERNS' },
  { type: 'pattern-debate', label: 'Debate', description: 'Multi-agent debate', icon: Users, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://debate', category: 'PATTERNS' },
  { type: 'pattern-best_of_n', label: 'Best of N', description: 'Generate N, pick best', icon: Trophy, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://best_of_n', category: 'PATTERNS' },
  { type: 'pattern-reflexion', label: 'Reflexion', description: 'Act→reflect loop', icon: RefreshCw, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://reflexion', category: 'PATTERNS' },
  { type: 'pattern-scatter', label: 'Scatter', description: 'Map→workers→reduce', icon: GitBranch, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://scatter', category: 'PATTERNS' },
  { type: 'pattern-fsm', label: 'State Machine', description: 'Finite state machine', icon: Workflow, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://fsm', category: 'PATTERNS' },
  { type: 'pattern-constitutional', label: 'Constitutional', description: 'Principle-guided AI', icon: Scale, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://constitutional', category: 'PATTERNS' },
  { type: 'pattern-chain_of_verification', label: 'Verify Chain', description: 'Generate→verify→revise', icon: CheckCheck, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://chain_of_verification', category: 'PATTERNS' },
  { type: 'pattern-plan_execute', label: 'Plan & Execute', description: 'Plan→execute→verify', icon: ListChecks, color: NODE_COLOR.pattern, agentPrefix: 'pattern://', defaultAgent: 'pattern://plan_execute', category: 'PATTERNS' },
];

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: NodeTypeConfig) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeType));
    event.dataTransfer.effectAllowed = 'move';
  };

  const defaultNodes = NODE_TYPES.filter((nt) => !nt.category);
  const cliAgents = NODE_TYPES.filter((nt) => nt.category === 'CLI AGENTS');
  const patternNodes = NODE_TYPES.filter((nt) => nt.category === 'PATTERNS');

  const sectionLabel: React.CSSProperties = {
    padding: "6px 14px 3px",
    fontSize: 9,
    color: "#4a4a52",
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    userSelect: "none",
  };

  const renderItem = (nt: NodeTypeConfig) => {
    const Icon = nt.icon;
    return (
      <div
        key={nt.type}
        draggable
        onDragStart={(e) => onDragStart(e, nt)}
        title={nt.description}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "7px 14px",
          borderLeft: `2px solid ${nt.color}`,
          cursor: "grab",
          transition: "background 0.1s",
        }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "#1a1a1d")}
        onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "transparent")}
      >
        <Icon size={13} style={{ color: nt.color, flexShrink: 0 }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <span style={{ fontSize: 11, color: "#f0f0f0" }}>{nt.label}</span>
          <span style={{ fontSize: 9, color: "#4a4a52", marginLeft: 6 }}>{nt.description}</span>
        </div>
      </div>
    );
  };

  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: 0,
      borderRight: "1px solid #252528",
      background: "#131315",
      width: 192, flexShrink: 0,
      overflowY: "auto",
    }}>
      <div style={sectionLabel}>Agents</div>
      {defaultNodes.map(renderItem)}
      {cliAgents.length > 0 && (
        <>
          <div style={{ ...sectionLabel, borderTop: "1px solid #252528", marginTop: 4, paddingTop: 10 }}>CLI</div>
          {cliAgents.map(renderItem)}
        </>
      )}
      {patternNodes.length > 0 && (
        <>
          <div style={{ ...sectionLabel, borderTop: "1px solid #252528", marginTop: 4, paddingTop: 10 }}>Patterns</div>
          {patternNodes.map(renderItem)}
        </>
      )}
      <div style={{ marginTop: "auto", padding: "8px 14px", fontSize: 9, color: "#4a4a52" }}>
        drag onto canvas
      </div>
    </div>
  );
}
