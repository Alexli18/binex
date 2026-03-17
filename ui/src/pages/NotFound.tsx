import { Link } from 'react-router-dom';
import { Home, AlertCircle } from 'lucide-react';
import { PageShell } from '@/components/layout/PageShell';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <PageShell>
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <AlertCircle className="w-12 h-12 text-slate-500 mb-4" />
        <h1 className="text-2xl font-bold text-slate-100 mb-2">Page Not Found</h1>
        <p className="text-sm text-slate-400 mb-6 max-w-sm">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Button asChild>
          <Link to="/">
            <Home className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
      </div>
    </PageShell>
  );
}
