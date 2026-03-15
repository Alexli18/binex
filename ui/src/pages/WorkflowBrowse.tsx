import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileCode, Plus, CheckCircle, Pencil } from 'lucide-react';
import { useWorkflows, useWorkflow } from '../hooks/useWorkflows';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { EmptyState } from '@/components/layout/EmptyState';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import yaml from 'js-yaml';

function ValidateButton({ path }: { path: string }) {
  const { data: workflowData } = useWorkflow(path);
  const [validating, setValidating] = useState(false);

  const handleValidate = (e: React.MouseEvent) => {
    e.stopPropagation();
    setValidating(true);
    try {
      if (!workflowData?.content) {
        toast.error('Could not load workflow content');
        return;
      }
      const parsed = yaml.load(workflowData.content) as { name?: string; nodes?: Record<string, unknown> };
      if (!parsed || typeof parsed !== 'object') {
        toast.error('Invalid YAML: not an object');
        return;
      }
      if (!parsed.nodes || Object.keys(parsed.nodes).length === 0) {
        toast.warning('Workflow has no nodes defined');
        return;
      }
      toast.success(`Valid workflow: ${Object.keys(parsed.nodes).length} nodes`);
    } catch (err) {
      toast.error(`YAML error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setValidating(false);
    }
  };

  return (
    <Button
      onClick={handleValidate}
      disabled={validating}
      variant="outline"
      size="sm"
      className="h-7 text-xs"
      title="Validate workflow YAML"
    >
      <CheckCircle size={12} className="mr-1" />
      Validate
    </Button>
  );
}

export default function WorkflowBrowse() {
  const navigate = useNavigate();
  const { data: workflows, isLoading, error, refetch } = useWorkflows();

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading workflows..." />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'Workflows' }]} className="mb-4" />
        <ErrorState
          title="Failed to load workflows"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'Workflows' }]} className="mb-4" />

      <PageHeader
        title="Workflows"
        description="Browse and manage your workflow files"
        actions={
          <Button onClick={() => navigate('/scaffold')} size="sm">
            <Plus size={16} className="mr-1.5" />
            Create New
          </Button>
        }
      />

      <div className="mt-6">
        {!workflows || workflows.length === 0 ? (
          <EmptyState
            icon={FileCode}
            title="No workflow files found"
            description="Create one with the Scaffold wizard or place YAML files in your project."
            action={{ label: 'Create Workflow', onClick: () => navigate('/scaffold') }}
          />
        ) : (
          <div className="border border-slate-700 rounded-card overflow-hidden">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 bg-slate-800/50">
                  <th className="text-left px-4 py-3 font-medium text-slate-400">
                    File Path
                  </th>
                  <th className="text-right px-4 py-3 font-medium text-slate-400">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {workflows.map((path) => (
                  <tr
                    key={path}
                    className="hover:bg-slate-700/30 cursor-pointer transition-colors"
                    onClick={() =>
                      navigate(`/editor?file=${encodeURIComponent(path)}`)
                    }
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileCode size={16} className="text-slate-500 shrink-0" />
                        <span className="font-mono text-xs text-slate-200 truncate">
                          {path}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(
                              `/editor?file=${encodeURIComponent(path)}`,
                            );
                          }}
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          title="Edit workflow"
                        >
                          <Pencil size={12} className="mr-1" />
                          Edit
                        </Button>
                        <ValidateButton path={path} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PageShell>
  );
}
