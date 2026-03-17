import { Navigate, useParams, useNavigate } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { PageShell } from '@/components/layout/PageShell';
import { LoadingState } from '@/components/layout/LoadingState';
import { EmptyState } from '@/components/layout/EmptyState';
import { Rocket } from 'lucide-react';

/**
 * Handles /runs/latest/* by finding the most recent run
 * and redirecting to /runs/<run_id>/<subpage>.
 * Shows empty state if no runs exist.
 */
export default function LatestRunRedirect() {
  const { '*': subpage } = useParams();
  const navigate = useNavigate();
  const { data: runs, isLoading } = useRuns();

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Finding latest run..." />
      </PageShell>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <PageShell>
        <EmptyState
          icon={Rocket}
          title="No runs yet"
          description="Run a workflow first, then come back to analyze it."
          action={{ label: 'Go to Dashboard', onClick: () => navigate('/') }}
        />
      </PageShell>
    );
  }

  // Sort by started_at descending, pick first
  const sorted = [...runs].sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
  );
  const latestRunId = sorted[0].run_id;

  return <Navigate to={`/runs/${latestRunId}/${subpage ?? ''}`} replace />;
}
