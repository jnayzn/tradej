import { Outlet } from 'react-router-dom';
import { useBridge } from './AuthContext';

/**
 * Boot-time gate: blocks the dashboard until the owner's API token has been
 * fetched (or surfaces an error if the backend is unreachable). There is no
 * login flow — see ``AuthContext`` for the rationale.
 */
export default function RequireAuth() {
  const { info, loading, error } = useBridge();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-slate-400">
        Loading…
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg p-6 text-center text-slate-300">
        <h1 className="text-lg font-semibold text-rose-400">Backend unreachable</h1>
        <p className="max-w-md text-sm text-slate-400">
          The dashboard could not load its API token from the server. Make sure the
          backend is running and reachable, then reload this page.
        </p>
        {error && (
          <code className="max-w-md break-all rounded-md bg-bg-800 px-3 py-2 font-mono text-xs text-slate-300">
            {error}
          </code>
        )}
      </div>
    );
  }

  return <Outlet />;
}
