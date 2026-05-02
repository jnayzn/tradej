import { useEffect, useState } from 'react';
import { useBridge } from '../auth/AuthContext';
import { baseURL, bridgeScriptDownloadUrl } from '../api/client';

const FRESH_THRESHOLD_MS = 90_000; // bridge polls every 15s by default

function maskToken(token: string): string {
  if (token.length <= 10) return token;
  return `${token.slice(0, 8)}${'•'.repeat(Math.max(0, token.length - 12))}${token.slice(-4)}`;
}

function formatRelative(iso: string | null): string {
  if (!iso) return 'jamais';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return 'jamais';
  const seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (seconds < 5) return "à l'instant";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}j ago`;
}

export default function MT5Bridge() {
  const { info, refresh, regenerate } = useBridge();
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Tick to recompute "X ago" display on the status row.
  const [, setTick] = useState(0);

  // Auto-refresh sync timestamp every 15s + tick the relative-time display
  // every 5s so "Dernière synchro" stays current.
  useEffect(() => {
    const interval = setInterval(() => {
      refresh().catch(() => {
        /* surface via manual refresh */
      });
    }, 15_000);
    const ticker = setInterval(() => setTick((n) => n + 1), 5_000);
    return () => {
      clearInterval(interval);
      clearInterval(ticker);
    };
  }, [refresh]);

  // Recompute on every render so the 5s ticker keeps the "Connecté" badge
  // in sync with the "X ago" label — useMemo would only recompute when
  // ``info`` changes, leaving the badge stuck on stale state for up to 15s
  // while the sibling text already shows "95s ago".
  const isConnected = (() => {
    if (!info?.last_sync_at) return false;
    const ts = Date.parse(info.last_sync_at);
    return !Number.isNaN(ts) && Date.now() - ts < FRESH_THRESHOLD_MS;
  })();

  if (!info) return null;

  const masked = maskToken(info.token);
  const display = revealed ? info.token : masked;
  const command = `python tradj_bridge.py \\\n    --api-url ${baseURL} \\\n    --api-token ${display} \\\n    --watch --interval 15`;

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(info!.token);
      setRevealed(true);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setErr('Impossible de copier le token (clipboard refusé). Sélectionne-le à la main.');
    }
  }

  async function rotate() {
    if (
      !confirm(
        'Régénérer le token ? Le bridge actuel arrêtera de synchroniser et tu devras coller le nouveau token.',
      )
    ) {
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await regenerate();
      setRevealed(true);
    } catch {
      setErr('Échec de la régénération. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">MT5 Bridge</h1>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
          Connexion automatique MetaTrader 5
        </p>
      </header>

      {/* Status card */}
      <section className="card space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Statut Bridge
            </p>
            <p className="mt-3 flex items-center gap-2 text-sm text-slate-300">
              <ClockIcon className="h-4 w-4 text-slate-400" />
              <span>
                Dernière synchro : <strong>{formatRelative(info.last_sync_at)}</strong>
              </span>
            </p>
          </div>
          <StatusBadge connected={isConnected} />
        </div>
        <p className="text-sm text-slate-400">
          {isConnected
            ? 'Bridge actif. Les nouveaux trades fermés sur MT5 apparaissent ici toutes les 15 secondes.'
            : "Le bridge n'est pas actif. Suis les étapes ci-dessous pour le lancer sur ton PC Windows avec MT5."}
        </p>
      </section>

      {/* Step 1 */}
      <Step number={1} title="Télécharge le script bridge">
        <p className="text-sm text-slate-400">
          Script Python à exécuter sur ton PC Windows où MT5 est installé.
        </p>
        <a
          href={bridgeScriptDownloadUrl()}
          download="tradj_bridge.py"
          className="btn btn-primary mt-1 w-fit"
        >
          <DownloadIcon className="h-4 w-4" />
          Télécharger tradj_bridge.py
        </a>
      </Step>

      {/* Step 2 */}
      <Step number={2} title="Installe les dépendances">
        <p className="text-sm text-slate-400">
          Dans un terminal PowerShell ou CMD sur ton PC Windows.
        </p>
        <CodeBlock prompt>{`pip install MetaTrader5 requests`}</CodeBlock>
      </Step>

      {/* Step 3 */}
      <Step number={3} title="Lance le bridge en mode temps réel">
        <p className="text-sm text-slate-400">
          Ouvre MT5 d'abord, puis lance cette commande. Les trades se synchronisent toutes
          les 15 secondes.
        </p>
        <CodeBlock prompt>{command}</CodeBlock>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn"
            onClick={() => setRevealed((v) => !v)}
          >
            <EyeIcon className="h-4 w-4" />
            {revealed ? 'Masquer le token' : 'Révéler & copier le token'}
          </button>
          <button type="button" className="btn" onClick={copyToken}>
            <CopyIcon className="h-4 w-4" />
            {copied ? 'Copié !' : 'Copier le token'}
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={rotate}
            disabled={busy}
          >
            {busy ? 'Régénération…' : 'Régénérer'}
          </button>
        </div>

        {err && (
          <p role="alert" className="text-sm text-rose-400">
            {err}
          </p>
        )}
      </Step>

      {/* Tips */}
      <section className="card space-y-3 p-5">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
          <CheckCircleIcon className="h-4 w-4" />
          Conseils
        </h3>
        <ul className="space-y-2 text-sm text-slate-300">
          <Bullet>
            MT5 doit être ouvert et connecté à ton broker avant de lancer le bridge.
          </Bullet>
          <Bullet>
            Le bridge synchronise uniquement les positions <strong>fermées</strong>.
          </Bullet>
          <Bullet>
            Laisse le terminal ouvert en arrière-plan pendant ta session de trading.
          </Bullet>
          <Bullet>
            Si tu régénères ton token, mets à jour la commande bridge sur ton PC Windows.
          </Bullet>
          <Bullet>
            Utilise <code className="font-mono text-amber-400">--days 90</code> sans{' '}
            <code className="font-mono text-amber-400">--watch</code> pour importer
            l'historique complet une fois.
          </Bullet>
        </ul>
      </section>

      {/* Prerequisites */}
      <section className="card space-y-3 p-5">
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
          <AlertCircleIcon className="h-4 w-4" />
          Prérequis
        </h3>
        <ul className="space-y-2 text-sm text-slate-300">
          <Bullet>
            Windows 10/11 (le package <code className="font-mono">MetaTrader5</code> est
            Windows uniquement)
          </Bullet>
          <Bullet>MetaTrader 5 installé et connecté à ton broker</Bullet>
          <Bullet>
            Python 3.8+ (
            <a
              href="https://www.python.org/downloads/"
              target="_blank"
              rel="noreferrer"
              className="text-brand hover:underline"
            >
              python.org
            </a>
            )
          </Bullet>
        </ul>
      </section>
    </div>
  );
}

/* ============================== sub-components ============================ */

function Step({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card space-y-3 p-5">
      <div className="flex items-center gap-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand/15 text-sm font-semibold text-brand">
          {number}
        </span>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
          {title}
        </h2>
      </div>
      <div className="space-y-3 pl-10">{children}</div>
    </section>
  );
}

function CodeBlock({
  children,
  prompt,
}: {
  children: React.ReactNode;
  prompt?: boolean;
}) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-border bg-bg-900 p-4 font-mono text-xs leading-relaxed text-slate-200">
      {prompt && <span className="mr-3 select-none text-slate-500">›_</span>}
      {children}
    </pre>
  );
}

function StatusBadge({ connected }: { connected: boolean }) {
  if (connected) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-300">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        Connecté
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-600/40 bg-slate-700/30 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
      <PlugOffIcon className="h-3 w-3" />
      Déconnecté
    </span>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-500" />
      <span>{children}</span>
    </li>
  );
}

/* ================================== icons ================================= */

type IconProps = { className?: string };

function ClockIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}
function DownloadIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 4v12" />
      <path d="m6 12 6 6 6-6" />
      <path d="M4 20h16" />
    </svg>
  );
}
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
function CheckCircleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12 3 3 5-6" />
    </svg>
  );
}
function AlertCircleIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <circle cx="12" cy="16" r="0.5" fill="currentColor" />
    </svg>
  );
}
function PlugOffIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 8 22 2" />
      <path d="m9 15 6-6" />
      <path d="m4 21 5-5" />
      <path d="M2 22 22 2" />
    </svg>
  );
}
