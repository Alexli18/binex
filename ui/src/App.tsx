import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import RunDetail from './pages/RunDetail';
import RunLive from './pages/RunLive';
import WorkflowEditor from './pages/WorkflowEditor';
import WorkflowBrowse from './pages/WorkflowBrowse';
import Scaffold from './pages/Scaffold';
import DebugPage from './pages/DebugPage';
import DiagnosePage from './pages/DiagnosePage';
import TracePage from './pages/TracePage';
import LineagePage from './pages/LineagePage';
import DiffPage from './pages/DiffPage';
import BisectPage from './pages/BisectPage';
import CostDashboard from './pages/CostDashboard';
import BudgetPage from './pages/BudgetPage';
import ExportPage from './pages/ExportPage';
import DoctorPage from './pages/DoctorPage';
import PluginsPage from './pages/PluginsPage';
import GatewayPage from './pages/GatewayPage';

export default function App() {
  return (
    <div className="flex h-screen bg-slate-900 text-slate-100">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/runs/:runId/live" element={<RunLive />} />
          <Route path="/runs/:runId/debug" element={<DebugPage />} />
          <Route path="/runs/:runId/diagnose" element={<DiagnosePage />} />
          <Route path="/runs/:runId/trace" element={<TracePage />} />
          <Route path="/runs/:runId/lineage" element={<LineagePage />} />
          <Route path="/workflows" element={<WorkflowBrowse />} />
          <Route path="/editor" element={<WorkflowEditor />} />
          <Route path="/scaffold" element={<Scaffold />} />
          <Route path="/diff" element={<DiffPage />} />
          <Route path="/bisect" element={<BisectPage />} />
          <Route path="/costs" element={<CostDashboard />} />
          <Route path="/costs/budget" element={<BudgetPage />} />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/system/doctor" element={<DoctorPage />} />
          <Route path="/system/plugins" element={<PluginsPage />} />
          <Route path="/system/gateway" element={<GatewayPage />} />
        </Routes>
      </main>
    </div>
  );
}
