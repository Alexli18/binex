import { useQuery } from '@tanstack/react-query';
import { getCaoHealth, type CaoHealthStatus } from '@/lib/api';

const STATUS_CONFIG = {
  online: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    label: 'CAO Online',
  },
  degraded: {
    dot: 'bg-amber-400',
    text: 'text-amber-400',
    label: 'CAO Degraded',
  },
  offline: {
    dot: 'bg-red-400',
    text: 'text-red-400',
    label: 'CAO Offline',
  },
} as const;

export function CaoServerStatus() {
  const { data, isLoading } = useQuery<CaoHealthStatus>({
    queryKey: ['cao-health'],
    queryFn: getCaoHealth,
    refetchInterval: 30_000,
    retry: 0,
    staleTime: 15_000,
  });

  if (isLoading) return null;

  const status = data?.status ?? 'offline';
  const config = STATUS_CONFIG[status];
  const url = data?.server_url ?? '';

  return (
    <div
      className="flex items-center gap-2 text-xs"
      title={`CAO server: ${url}`}
    >
      <span className={`inline-block w-2 h-2 rounded-full ${config.dot}`} />
      <span className={config.text}>{config.label}</span>
    </div>
  );
}
