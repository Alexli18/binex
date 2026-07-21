import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { HelpCircle, X, Compass } from 'lucide-react';
import { cn } from '@/lib/utils';
import { startTour } from '@/lib/tour';

const HELP_CONTENT: Record<string, { title: string; sections: { heading: string; body: string }[] }> = {
  '/': {
    title: 'Dashboard',
    sections: [
      { heading: 'Overview', body: 'The Dashboard lists all workflow runs. Use filters to narrow by status or search by run ID.' },
      { heading: 'Starting a Run', body: 'Click "New Run" to select a workflow and optionally set variables (key=value format, one per line).' },
      { heading: 'Run Statuses', body: 'completed = all nodes finished, running = execution in progress, failed = one or more nodes errored, cancelled = manually stopped.' },
      { heading: 'Costs Tab', body: 'Track LLM API costs across runs. Cost Trend shows spending over time. Cost by Model and Cost by Node break down where money is going.' },
      { heading: 'Budget Tab', body: 'Set max_cost in your workflow YAML to cap spending. "stop" policy halts execution when exceeded. "warn" policy logs a warning but continues.' },
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
  const navigate = useNavigate();
  const help = getHelpForPath(location.pathname);

  // Re-launch the guided tour on demand. Its anchors live on the Dashboard, so
  // route there first, then start once the page has painted.
  const handleTakeTour = () => {
    setOpen(false);
    navigate('/');
    window.setTimeout(() => startTour(), 450);
  };

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
          'fixed top-14 right-3 z-40 p-2 rounded-full transition-colors',
          open
            ? 'bg-amber-500 text-black'
            : 'bg-[#1a1a1d] text-[#80808a] hover:text-[#f0f0f0] hover:bg-[#252528] border border-[#252528]',
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
          <div className="fixed top-0 right-0 z-50 h-full w-80 bg-[#131315] border-l border-[#252528] shadow-xl overflow-y-auto animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between p-4 border-b border-[#252528]">
              <h2 className="text-sm font-semibold text-[#f0f0f0]">
                {help.title}
              </h2>
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded text-[#80808a] hover:text-[#f0f0f0] hover:bg-[#1a1a1d]"
              >
                <X size={16} />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {help.sections.map((section) => (
                <div key={section.heading}>
                  <h3 className="text-xs font-semibold text-[#80808a] uppercase tracking-wider mb-1">
                    {section.heading}
                  </h3>
                  <p className="text-sm text-[#80808a] leading-relaxed">
                    {section.body}
                  </p>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-[#252528]">
              <button
                onClick={handleTakeTour}
                className="flex items-center gap-2 w-full justify-center py-2 rounded text-xs font-medium text-[#80808a] border border-[#252528] hover:text-[#f0f0f0] hover:border-[#333338] transition-colors"
              >
                <Compass size={14} />
                Take the guided tour
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
