import { useState, useCallback, useMemo } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import Sidebar from './components/Sidebar';
import { HelpPanel } from './components/common/HelpPanel';
import { CommandPalette } from './components/common/CommandPalette';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import Dashboard from './pages/Dashboard';
import RunDetail from './pages/RunDetail';
import RunLive from './pages/RunLive';
import WorkflowEditor from './pages/WorkflowEditor';
import Scaffold from './pages/Scaffold';
import DebugPage from './pages/DebugPage';
import DiagnosePage from './pages/DiagnosePage';
import TracePage from './pages/TracePage';
import LineagePage from './pages/LineagePage';
import DiffPage from './pages/DiffPage';
import BisectPage from './pages/BisectPage';
import ExportPage from './pages/ExportPage';
import DoctorPage from './pages/DoctorPage';
import PluginsPage from './pages/PluginsPage';
import GatewayPage from './pages/GatewayPage';
import PromptLibrary from './pages/PromptLibrary';
import CostDashboard from './pages/CostDashboard';
import NotFound from './pages/NotFound';
import LatestRunRedirect from './pages/LatestRunRedirect';

export default function App() {
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);

  const togglePalette = useCallback(() => setCmdPaletteOpen((v) => !v), []);

  const shortcuts = useMemo(() => [
    { key: 'k', meta: true, handler: togglePalette },
  ], [togglePalette]);

  useKeyboardShortcuts(shortcuts);

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100">
      <Toaster position="top-right" richColors />
      <CommandPalette open={cmdPaletteOpen} onOpenChange={setCmdPaletteOpen} />
      <Sidebar />
      <HelpPanel />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs/latest/*" element={<LatestRunRedirect />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/runs/:runId/live" element={<RunLive />} />
          <Route path="/runs/:runId/debug" element={<DebugPage />} />
          <Route path="/runs/:runId/diagnose" element={<DiagnosePage />} />
          <Route path="/runs/:runId/trace" element={<TracePage />} />
          <Route path="/runs/:runId/lineage" element={<LineagePage />} />
          <Route path="/editor" element={<WorkflowEditor />} />
          <Route path="/scaffold" element={<Scaffold />} />
          <Route path="/prompts" element={<PromptLibrary />} />
          <Route path="/costs" element={<CostDashboard />} />
          <Route path="/diff" element={<DiffPage />} />
          <Route path="/bisect" element={<BisectPage />} />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/system/doctor" element={<DoctorPage />} />
          <Route path="/system/plugins" element={<PluginsPage />} />
          <Route path="/system/gateway" element={<GatewayPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
