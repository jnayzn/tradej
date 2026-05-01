import { useEffect, useState } from 'react';
import EquityCurve from '../components/EquityCurve';
import StatCard from '../components/StatCard';
import TradesTable from '../components/TradesTable';
import { getEquity, getSummary, listTrades } from '../api/client';
import type { EquityPoint, Summary, Trade } from '../types';
import { formatCurrency, formatPct, pnlColor } from '../lib/format';
import { useReload } from '../lib/useReload';

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [recent, setRecent] = useState<Trade[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tick] = useReload();

  useEffect(() => {
    setError(null);
    Promise.all([getSummary(), getEquity(), listTrades({ limit: 10 })])
      .then(([s, e, t]) => {
        setSummary(s);
        setEquity(e);
        setRecent(t.results);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load data';
        setError(msg);
      });
  }, [tick]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted">An overview of your trading performance.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-loss/40 bg-loss/10 p-4 text-sm text-loss">
          {error}. Make sure the backend API is running and{' '}
          <code className="rounded bg-bg-700 px-1 py-0.5">VITE_API_BASE_URL</code> is correct.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          title="Total PnL"
          value={summary ? formatCurrency(summary.total_pnl) : '—'}
          valueClassName={summary ? pnlColor(summary.total_pnl) : ''}
          hint={summary ? `${summary.total_trades} trades` : undefined}
        />
        <StatCard
          title="Winrate"
          value={summary ? formatPct(summary.winrate) : '—'}
          hint={
            summary ? `${summary.wins} W / ${summary.losses} L / ${summary.breakeven} B` : undefined
          }
        />
        <StatCard
          title="Profit factor"
          value={summary ? summary.profit_factor.toFixed(2) : '—'}
          hint={
            summary
              ? `Gross +${formatCurrency(summary.gross_profit)} / ${formatCurrency(summary.gross_loss)}`
              : undefined
          }
        />
        <StatCard
          title="Expectancy / trade"
          value={summary ? formatCurrency(summary.expectancy) : '—'}
          valueClassName={summary ? pnlColor(summary.expectancy) : ''}
          hint={summary ? `Avg trade ${formatCurrency(summary.average_trade)}` : undefined}
        />
        <StatCard
          title="Biggest win"
          value={summary ? formatCurrency(summary.biggest_win) : '—'}
          valueClassName="text-profit"
        />
        <StatCard
          title="Biggest loss"
          value={summary ? formatCurrency(summary.biggest_loss) : '—'}
          valueClassName="text-loss"
        />
        <StatCard
          title="Average win"
          value={summary ? formatCurrency(summary.average_win) : '—'}
          valueClassName="text-profit"
        />
        <StatCard
          title="Average loss"
          value={summary ? formatCurrency(summary.average_loss) : '—'}
          valueClassName="text-loss"
        />
      </div>

      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="card-title">Equity curve</div>
            <div className="text-base font-semibold">Cumulative net PnL</div>
          </div>
        </div>
        <EquityCurve points={equity} />
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Recent trades</h2>
          <span className="text-xs text-muted">Showing last {recent.length}</span>
        </div>
        <TradesTable trades={recent} emptyMessage="No trades imported yet." />
      </div>
    </div>
  );
}
