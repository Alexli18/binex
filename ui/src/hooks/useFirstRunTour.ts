import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useRuns } from './useRuns';
import { hasSeenTour, startTour } from '../lib/tour';

/**
 * Auto-start the guided tour (issue #32) the first time a user lands on an
 * empty Dashboard — i.e. a genuine first run: no stored runs, tour never seen.
 *
 * Manual re-triggering is just `startTour()` (see HelpPanel); this hook only
 * owns the *automatic* first-run case so it fires at most once per session and
 * never surprises an existing user.
 */
export function useFirstRunTour(): void {
  const location = useLocation();
  const { data: runs, isSuccess } = useRuns();
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    // Never auto-launch under browser automation (Playwright/Selenium set
    // navigator.webdriver). The spotlight overlay would otherwise block the
    // e2e tests that drive an empty dashboard. Real users are unaffected.
    if (typeof navigator !== 'undefined' && navigator.webdriver) return;
    if (location.pathname !== '/') return; // anchors live on the Dashboard
    if (!isSuccess || runs === undefined) return; // wait for the runs query
    if (runs.length > 0) return; // not a first run
    if (hasSeenTour()) return;

    startedRef.current = true;
    // Let the Dashboard paint its New Run button before we spotlight it.
    const t = window.setTimeout(() => startTour(), 400);
    return () => window.clearTimeout(t);
  }, [location.pathname, isSuccess, runs]);
}
