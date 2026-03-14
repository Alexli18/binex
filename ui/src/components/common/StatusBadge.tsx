const statusColors: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  running: 'bg-blue-100 text-blue-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
  over_budget: 'bg-yellow-100 text-yellow-800',
  interrupted: 'bg-orange-100 text-orange-800',
  pending: 'bg-gray-100 text-gray-500',
  skipped: 'bg-gray-100 text-gray-400',
};

export function StatusBadge({ status }: { status: string }) {
  const colors = statusColors[status] || 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {status}
    </span>
  );
}
