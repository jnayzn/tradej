import type { Trade } from '../types';
import { formatCurrency, formatDateTime, pnlColor } from '../lib/format';

interface Props {
  trades: Trade[];
  emptyMessage?: string;
}

export default function TradesTable({ trades, emptyMessage }: Props) {
  if (trades.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-bg-800 p-10 text-center text-sm text-muted">
        {emptyMessage ?? 'No trades to show.'}
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-bg-800">
      <div className="max-h-[60vh] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-bg-700 text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Symbol</th>
              <th className="px-4 py-3 font-medium">Side</th>
              <th className="px-4 py-3 font-medium">Volume</th>
              <th className="px-4 py-3 font-medium">Open</th>
              <th className="px-4 py-3 font-medium">Close</th>
              <th className="px-4 py-3 text-right font-medium">PnL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {trades.map((t) => {
              const net = Number(t.net_profit);
              return (
                <tr key={t.id} className="hover:bg-bg-700/40">
                  <td className="px-4 py-2.5 font-medium">{t.symbol}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-md px-2 py-0.5 text-xs font-medium ${
                        t.order_type === 'BUY'
                          ? 'bg-profit/15 text-profit'
                          : 'bg-loss/15 text-loss'
                      }`}
                    >
                      {t.order_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-300">{Number(t.volume).toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-slate-300">{formatDateTime(t.open_time)}</td>
                  <td className="px-4 py-2.5 text-slate-300">{formatDateTime(t.close_time)}</td>
                  <td className={`px-4 py-2.5 text-right font-medium ${pnlColor(net)}`}>
                    {formatCurrency(net)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
