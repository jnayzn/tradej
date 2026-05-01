import { useEffect, useState } from 'react';
import InsightCard from '../components/InsightCard';
import StatCard from '../components/StatCard';
import { getBySymbol, getInsights } from '../api/client';
import type { Insights, SymbolStat } from '../types';
import { formatCurrency, formatPct, pnlColor } from '../lib/format';
import { useReload } from '../lib/useReload';

export default function Analytics() {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [symbols, setSymbols] = useState<SymbolStat[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tick] = useReload();

  useEffect(() => {
    setError(null);
    Promise.all([getInsights(), getBySymbol()])
      .then(([i, s]) => {
        setInsights(i);
        setSymbols(s);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load analytics';
        setError(msg);
      });
  }, [tick]);

  const score = insights?.score ?? null;
  const scoreColor =
    score === null
      ? ''
      : score >= 70
        ? 'text-profit'
        : score >= 40
          ? 'text-amber-400'
          : 'text-loss';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted">
          Smart insights derived from your trade history.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-loss/40 bg-loss/10 p-4 text-sm text-loss">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          title="Trader score"
          value={score === null ? '—' : `${score}/100`}
          valueClassName={scoreColor}
          hint={
            score === null
              ? undefined
              : score >= 70
                ? 'Strong'
                : score >= 40
                  ? 'Mixed'
                  : 'Needs work'
          }
        />
        <StatCard
          title="Risk / Reward"
          value={insights?.metrics.risk_reward != null ? insights.metrics.risk_reward.toFixed(2) : '—'}
          hint="avg win / |avg loss|"
        />
        <StatCard
          title="Profit factor"
          value={insights?.metrics.profit_factor != null ? insights.metrics.profit_factor.toFixed(2) : '—'}
        />
        <StatCard
          title="Winrate"
          value={insights?.metrics.winrate != null ? formatPct(insights.metrics.winrate) : '—'}
        />
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold">Findings</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {insights?.findings.map((f, i) => <InsightCard key={i} finding={f} />) ?? (
            <div className="text-sm text-muted">Loading…</div>
          )}
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold">By symbol</h2>
        {symbols.length === 0 ? (
          <div className="rounded-2xl border border-border bg-bg-800 p-10 text-center text-sm text-muted">
            No data yet.
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-border bg-bg-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-bg-700 text-xs uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 text-right font-medium">Trades</th>
                  <th className="px-4 py-3 text-right font-medium">Winrate</th>
                  <th className="px-4 py-3 text-right font-medium">PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {symbols.map((s) => (
                  <tr key={s.symbol} className="hover:bg-bg-700/40">
                    <td className="px-4 py-2.5 font-medium">{s.symbol}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{s.trades}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">
                      {formatPct(s.winrate)}
                    </td>
                    <td className={`px-4 py-2.5 text-right font-medium ${pnlColor(s.pnl)}`}>
                      {formatCurrency(s.pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
