import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}

export function CollapsibleSection({ title, defaultOpen = false, badge, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-t border-[#252528]/30 first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 w-full px-2.5 py-1.5 text-[11px] font-medium text-[#80808a] hover:text-[#80808a] hover:bg-[#1a1a1d]/30 transition-colors"
      >
        <ChevronRight
          size={12}
          className={cn('transition-transform duration-200 shrink-0', open && 'rotate-90')}
        />
        {title}
        {badge && <span className="ml-auto">{badge}</span>}
      </button>
      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <div className="px-2.5 pb-2 space-y-1.5">{children}</div>
        </div>
      </div>
    </div>
  );
}
