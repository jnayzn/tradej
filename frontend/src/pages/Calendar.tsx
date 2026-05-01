import { useEffect, useMemo, useState } from 'react';
import TradingCalendar from '../components/TradingCalendar';
import { getCalendar } from '../api/client';
import type { CalendarMonth } from '../types';
import { useReload } from '../lib/useReload';

export default function Calendar() {
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState(today.getUTCFullYear());
  const [month, setMonth] = useState(today.getUTCMonth() + 1);
  const [data, setData] = useState<CalendarMonth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick] = useReload();

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCalendar(year, month)
      .then(setData)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load calendar';
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [year, month, tick]);

  function shift(delta: number) {
    let m = month + delta;
    let y = year;
    while (m < 1) {
      m += 12;
      y -= 1;
    }
    while (m > 12) {
      m -= 12;
      y += 1;
    }
    setYear(y);
    setMonth(m);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Calendar</h1>
          <p className="text-sm text-muted">Daily PnL heatmap. Green = profit, red = loss.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn" onClick={() => shift(-1)}>
            ← Prev
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setYear(today.getUTCFullYear());
              setMonth(today.getUTCMonth() + 1);
            }}
          >
            Today
          </button>
          <button type="button" className="btn" onClick={() => shift(1)}>
            Next →
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-loss/40 bg-loss/10 p-4 text-sm text-loss">
          {error}
        </div>
      )}

      <TradingCalendar data={data} loading={loading} />
    </div>
  );
}
