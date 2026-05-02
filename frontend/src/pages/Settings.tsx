import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8000/api';

export default function Settings() {
  const { user, token, regenerateToken } = useAuth();
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user || !token) return null;

  async function copy() {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  async function rotate() {
    if (!confirm('Rotate your API token? The bridge will need the new value to keep syncing.')) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await regenerateToken();
      setRevealed(true);
    } catch {
      setError('Could not rotate the token. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  const masked = token ? `${token.slice(0, 6)}${'•'.repeat(Math.max(0, token.length - 10))}${token.slice(-4)}` : '';
  // Mirror the Reveal/Hide toggle here so a screen-shared Settings page never
  // leaks the full token via the bridge command snippet.
  const displayToken = revealed ? token : masked;
  const exampleCommand =
    `python mt5_bridge.py --api-url ${baseURL} --api-token ${displayToken} --watch --interval 15`;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-slate-400">
          Signed in as <span className="font-mono text-slate-200">{user.username}</span>
          {user.email ? <> · {user.email}</> : null}
        </p>
      </div>

      <section className="card space-y-4 p-5">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">API token</h2>
          <p className="text-sm text-slate-400">
            Paste this into the MT5 bridge so your trades sync to <em>your</em> account.
            Treat it like a password — anyone with this token can write trades on your
            behalf. If it leaks, rotate it.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <code className="select-all rounded-md bg-bg-800 px-3 py-2 font-mono text-sm">
            {revealed ? token : masked}
          </code>
          <button
            type="button"
            className="btn"
            onClick={() => setRevealed((v) => !v)}
          >
            {revealed ? 'Hide' : 'Reveal'}
          </button>
          <button type="button" className="btn" onClick={copy}>
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={rotate}
            disabled={busy}
          >
            {busy ? 'Rotating…' : 'Rotate'}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-sm text-rose-400">
            {error}
          </p>
        )}

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Bridge command (copy/paste)
          </p>
          <pre className="overflow-x-auto rounded-md bg-bg-800 p-3 font-mono text-xs text-slate-200">
            {exampleCommand}
          </pre>
          <p className="text-xs text-slate-500">
            Or set <code className="font-mono">BRIDGE_API_TOKEN</code> as an environment
            variable instead of passing <code className="font-mono">--api-token</code>.
          </p>
        </div>
      </section>
    </div>
  );
}
