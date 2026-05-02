import { isAxiosError } from 'axios';
import { useEffect, useState } from 'react';
import { useBridge } from '../auth/AuthContext';

function formatDateJoined(iso: string | null): string {
  if (!iso) return '—';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return '—';
  const d = new Date(ts);
  // dd/MM/yyyy, HH:mm:ss — matches the mockup screenshot.
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}, ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export default function SystemConfig() {
  const { info, updateProfile, regenerate, terminate } = useBridge();
  const [username, setUsername] = useState(info?.owner_username ?? '');
  const [savingName, setSavingName] = useState(false);
  const [nameNotice, setNameNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(
    null,
  );
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [terminating, setTerminating] = useState(false);

  // Sync the input when the underlying owner_username changes (e.g. after
  // regenerate/terminate refetched the profile).
  useEffect(() => {
    if (info?.owner_username !== undefined) setUsername(info.owner_username);
  }, [info?.owner_username]);

  if (!info) return null;

  async function saveName() {
    if (username.trim() === info!.owner_username) {
      setNameNotice(null);
      return;
    }
    setSavingName(true);
    setNameNotice(null);
    try {
      await updateProfile({ username: username.trim() });
      setNameNotice({ kind: 'ok', text: 'Saved.' });
    } catch (err) {
      let text = 'Could not save.';
      if (isAxiosError(err)) {
        const data = err.response?.data as { username?: string[] } | undefined;
        if (data?.username?.length) text = data.username[0];
      }
      setNameNotice({ kind: 'err', text });
    } finally {
      setSavingName(false);
    }
  }

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(info!.token);
      setCopied(true);
      setRevealed(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard refused; ignore */
    }
  }

  async function rotate() {
    if (
      !confirm(
        'Regenerating your token will immediately invalidate your current token. Any active scripts or EAs will fail until updated. Continue?',
      )
    ) {
      return;
    }
    setRotating(true);
    try {
      await regenerate();
      setRevealed(true);
    } finally {
      setRotating(false);
    }
  }

  async function onTerminate() {
    if (
      !confirm(
        'Terminate this session? The cached token on this device will be cleared and the page will reload from the server.',
      )
    ) {
      return;
    }
    setTerminating(true);
    try {
      await terminate();
    } finally {
      setTerminating(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">System Configuration</h1>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
          Identity &amp; API Access
        </p>
      </header>

      {/* Identity Profile */}
      <section className="card space-y-5 p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand">
            Identity Profile
          </p>
          <p className="mt-1 text-sm text-slate-400">Your core trading identity details.</p>
        </div>

        <div className="space-y-2">
          <label htmlFor="trader-id" className="text-xs uppercase tracking-wider text-slate-400">
            Trader ID (Username)
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              id="trader-id"
              className="input flex-1 font-mono"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                setNameNotice(null);
              }}
              autoComplete="off"
              spellCheck={false}
              maxLength={32}
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={saveName}
              disabled={savingName || username.trim() === info.owner_username}
            >
              {savingName ? 'Saving…' : 'Save'}
            </button>
          </div>
          {nameNotice && (
            <p
              className={`text-xs ${
                nameNotice.kind === 'ok' ? 'text-emerald-400' : 'text-rose-400'
              }`}
              role={nameNotice.kind === 'err' ? 'alert' : undefined}
            >
              {nameNotice.text}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-xs uppercase tracking-wider text-slate-400">
            Account Created
          </label>
          <div className="rounded-lg border border-border bg-bg-900 px-3 py-2 font-mono text-sm text-slate-200">
            {formatDateJoined(info.date_joined)}
          </div>
        </div>

        <div>
          <button
            type="button"
            className="btn btn-danger"
            onClick={onTerminate}
            disabled={terminating}
          >
            <LogoutIcon className="h-4 w-4" />
            {terminating ? 'Terminating…' : 'Terminate Session'}
          </button>
        </div>
      </section>

      {/* API Connectivity */}
      <section className="card space-y-5 p-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand">
            API Connectivity
          </p>
          <p className="mt-1 text-sm text-slate-400">
            Use this token to authenticate external platforms like MT5 EAs or scripts.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-xs uppercase tracking-wider text-slate-400">Bearer Token</label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              readOnly
              className="input flex-1 font-mono"
              value={revealed ? info.token : '•'.repeat(Math.min(info.token.length, 48))}
              onFocus={(e) => e.currentTarget.select()}
            />
            <button
              type="button"
              className="btn"
              onClick={() => setRevealed((v) => !v)}
              title={revealed ? 'Hide token' : 'Reveal token'}
            >
              <EyeIcon className="h-4 w-4" />
            </button>
            <button type="button" className="btn" onClick={copyToken}>
              <CopyIcon className="h-4 w-4" />
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-rose-300">
            <AlertIcon className="h-4 w-4" />
            Danger Zone
          </p>
          <p className="mt-2 text-sm text-slate-300">
            Regenerating your token will immediately invalidate your current token. Any
            active scripts or EAs will fail until updated.
          </p>
          <button
            type="button"
            className="btn btn-danger mt-3"
            onClick={rotate}
            disabled={rotating}
          >
            <RefreshIcon className="h-4 w-4" />
            {rotating ? 'Regenerating…' : 'Regenerate Token'}
          </button>
        </div>
      </section>
    </div>
  );
}

/* ================================== icons ================================= */

type IconProps = { className?: string };

function EyeIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function CopyIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}
function RefreshIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
      <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}
function LogoutIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}
function AlertIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4" />
      <circle cx="12" cy="17" r="0.5" fill="currentColor" />
    </svg>
  );
}
