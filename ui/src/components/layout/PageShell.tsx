import { cn } from '@/lib/utils';

interface PageShellProps {
  children: React.ReactNode;
  className?: string;
}

export function PageShell({ children, className }: PageShellProps) {
  return (
    <div className={cn('mx-auto w-full max-w-7xl px-6 py-6', className)}>
      {children}
    </div>
  );
}
