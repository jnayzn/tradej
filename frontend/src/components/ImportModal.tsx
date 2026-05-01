import { useEffect, useState } from 'react';
import { importFile } from '../api/client';
import type { ImportResult } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function ImportModal({ open, onClose }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  useEffect(() => {
    if (!open) {
      setFile(null);
      setError(null);
      setResult(null);
      setBusy(false);
    }
  }, [open]);

  if (!open) return null;

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await importFile(file);
      setResult(r);
      // Force a soft refresh of the data after a successful import.
      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('trades:imported'));
      }, 100);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ??
        (err as Error)?.message ??
        'Upload failed.';
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-bg-800 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 text-base font-semibold">Import trades</div>
        <p className="mb-4 text-sm text-muted">
          Upload a <code className="rounded bg-bg-700 px-1 py-0.5">.csv</code> or{' '}
          <code className="rounded bg-bg-700 px-1 py-0.5">.json</code> export from MetaTrader 5
          (or any compatible journal). Trades with a <code className="rounded bg-bg-700 px-1 py-0.5">ticket</code> field are deduplicated.
        </p>

        <label className="block">
          <span className="text-xs font-medium uppercase tracking-wider text-muted">File</span>
          <input
            type="file"
            accept=".csv,.json,text/csv,application/json"
            className="mt-1 block w-full cursor-pointer rounded-lg border border-border bg-bg-700 px-3 py-2 text-sm text-slate-200 file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1 file:text-white"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>

        {error && (
          <div className="mt-4 rounded-lg border border-loss/40 bg-loss/10 p-3 text-sm text-loss">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 rounded-lg border border-profit/40 bg-profit/10 p-3 text-sm text-profit">
            <div>
              Created: <strong>{result.created}</strong>, Updated:{' '}
              <strong>{result.updated}</strong>, Skipped: <strong>{result.skipped}</strong>
            </div>
            {result.errors.length > 0 && (
              <details className="mt-2 text-xs text-muted">
                <summary>{result.errors.length} row error(s)</summary>
                <ul className="mt-1 list-inside list-disc">
                  {result.errors.slice(0, 8).map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={submit}
            disabled={!file || busy}
          >
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  );
}
