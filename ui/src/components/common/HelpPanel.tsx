import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { HelpCircle, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const HELP_CONTENT: Record<string, { title: string; sections: { heading: string; body: string }[] }> = {
  '/': {
    title: 'Dashboard',
    sections: [
      { heading: 'Overview', body: 'The Dashboard lists all workflow runs. Use filters to narrow by status or search by run ID.' },
      { heading: 'Starting a Run', body: 'Click "New Run" to select a workflow and optionally set variables (key=value format, one per line).' },
      { heading: 'Run Statuses', body: 'completed = all nodes finished, running = execution in progress, failed = one or more nodes errored, cancelled = manually stopped.' },
    ],
  },
  '/editor': {
    title: 'Workflow Editor',
    sections: [
      { heading: 'Editing Modes', body: 'Switch between Visual (drag-and-drop canvas) and YAML (text editor with live DAG preview). Changes sync bidirectionally.' },
      { heading: 'DSL Syntax', body: 'Workflows define nodes with agent prefixes: llm:// (LLM calls), local:// (Python functions), a2a:// (remote agents), human:// (approval/input). Dependencies are set via depends_on arrays.' },
      { heading: 'Node Config', body: 'Each node can have config: temperature (0-2, controls randomness), max_tokens (response length limit), system_prompt (instructions for the agent).' },
      { heading: 'Cost Estimate', body: 'Toggle the $ icon to see estimated costs before running. Estimates are based on model pricing and max_tokens.' },
    ],
  },
  '/debug': {
    title: 'Debug Inspector',
    sections: [
      { heading: 'Node List', body: 'Shows all nodes with their execution status. Toggle "Errors only" to filter to failed nodes. Click a node for details.' },
      { heading: 'Timing', body: 'started_at = when execution began, completed_at = when it finished, duration = wall-clock time in seconds.' },
      { heading: 'Artifacts', body: 'Each node produces artifacts. Types include: text (plain text output), code (source code), decision (human approval result), error (error details).' },
      { heading: 'Replay', body: 'Re-run a single node with modified parameters (agent, prompt, model) without re-running the entire workflow.' },
    ],
  },
  '/trace': {
    title: 'Trace Timeline',
    sections: [
      { heading: 'Gantt Chart', body: 'Each bar represents a node execution. Bar width = duration, position = start time offset. Parallel nodes appear on separate rows.' },
      { heading: 'Colors', body: 'Blue = completed successfully, Red = failed, Amber = still running. Orange ring = latency anomaly detected.' },
      { heading: 'Anomalies', body: 'Nodes flagged as anomalies took significantly longer than average (ratio shows how many times slower). Investigate these for performance issues.' },
    ],
  },
  '/costs': {
    title: 'Cost Dashboard',
    sections: [
      { heading: 'Metrics', body: 'Total Cost = sum of all LLM API costs. Avg per Run = total divided by run count. Budget Used = percentage of estimated capacity consumed.' },
      { heading: 'Cost Calculation', body: 'Costs are calculated via litellm.completion_cost() based on model, input tokens, and output tokens. Non-LLM nodes (local://, human://) have zero cost.' },
      { heading: 'Budget Policies', body: '"stop" policy halts execution when budget is exceeded, skipping remaining nodes. "warn" policy logs a warning but continues execution.' },
      { heading: 'Charts', body: 'Cost Trend shows spending over time. Cost by Model and Cost by Node break down where money is going.' },
    ],
  },
  '/costs/budget': {
    title: 'Budget Configuration',
    sections: [
      { heading: 'Budget Limit', body: 'Set max_cost in your workflow YAML to cap spending. The orchestrator checks budget between scheduling batches.' },
      { heading: 'Policies', body: 'stop = halt workflow and mark remaining nodes as over_budget. warn = log warning and continue execution.' },
    ],
  },
  '/diagnose': {
    title: 'Diagnose',
    sections: [
      { heading: 'Root Causes', body: 'Automatically identifies failed nodes that may have caused downstream failures.' },
      { heading: 'Recommendations', body: 'Actionable suggestions based on the failure pattern and latency analysis.' },
    ],
  },
  '/diff': {
    title: 'Run Comparison',
    sections: [
      { heading: 'How to Use', body: 'Enter two run IDs to compare node-by-node. Shows status changes, duration differences, cost deltas, and artifact diffs.' },
    ],
  },
  '/bisect': {
    title: 'Bisect',
    sections: [
      { heading: 'Divergence Finder', body: 'Given a "good" and "bad" run, finds the first node where outputs diverge. Similarity score shows how closely the runs match.' },
    ],
  },
};

function getHelpForPath(pathname: string) {
  // Exact match first
  if (HELP_CONTENT[pathname]) return HELP_CONTENT[pathname];
  // Strip run ID prefix for analysis pages
  const analysisMatch = pathname.match(/\/runs\/[^/]+\/(debug|trace|diagnose|lineage)/);
  if (analysisMatch) return HELP_CONTENT[`/${analysisMatch[1]}`];
  return null;
}

export function HelpPanel() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const help = getHelpForPath(location.pathname);

  // Close panel on navigation
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  if (!help) return null;

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'fixed top-3 right-3 z-40 p-2 rounded-full transition-colors',
          open
            ? 'bg-blue-600 text-white'
            : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 border border-slate-700',
        )}
        aria-label="Toggle help panel"
      >
        <HelpCircle size={18} />
      </button>

      {/* Sliding panel */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40 bg-black/20"
            onClick={() => setOpen(false)}
          />
          {/* Panel */}
          <div className="fixed top-0 right-0 z-50 h-full w-80 bg-slate-900 border-l border-slate-700 shadow-xl overflow-y-auto animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between p-4 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200">
                {help.title}
              </h2>
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {help.sections.map((section) => (
                <div key={section.heading}>
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    {section.heading}
                  </h3>
                  <p className="text-sm text-slate-300 leading-relaxed">
                    {section.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
