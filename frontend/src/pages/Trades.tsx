import { useEffect, useState } from 'react';
import TradesTable from '../components/TradesTable';
import { listTrades } from '../api/client';
import type { Trade } from '../types';
import { useReload } from '../lib/useReload';

const PAGE_SIZE = 50;

export default function Trades() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [tick] = useReload();

  useEffect(() => {
    setError(null);
    listTrades({ limit: PAGE_SIZE, offset, search: search || undefined })
      .then((res) => {
        setTrades(res.results);
        setCount(res.count);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load trades';
        setError(msg);
      });
  }, [tick, offset, search]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Trades</h1>
          <p className="text-sm text-muted">{count} total trades</p>
        </div>
        <input
          type="search"
          placeholder="Search symbol / comment / notes…"
          className="rounded-lg border border-border bg-bg-700 px-3 py-1.5 text-sm focus:border-brand focus:outline-none"
          value={search}
          onChange={(e) => {
            setOffset(0);
            setSearch(e.target.value);
          }}
        />
      </div>

      {error && (
        <div className="rounded-lg border border-loss/40 bg-loss/10 p-4 text-sm text-loss">
          {error}
        </div>
      )}

      <TradesTable trades={trades} emptyMessage="No trades match the current filter." />

      <div className="flex items-center justify-between text-sm text-muted">
        <span>
          Page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn"
            disabled={offset + PAGE_SIZE >= count}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
