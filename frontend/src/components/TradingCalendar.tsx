import type { CalendarMonth } from '../types';
import { formatCurrency } from '../lib/format';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface Props {
  data: CalendarMonth | null;
  loading?: boolean;
}

export default function TradingCalendar({ data, loading }: Props) {
  if (loading || !data) {
    return (
      <div className="card flex h-80 items-center justify-center text-sm text-muted">
        Loading…
      </div>
    );
  }

  const { year, month, days } = data;
  // First-of-month padding (Monday-based weeks).
  const firstDate = new Date(Date.UTC(year, month - 1, 1));
  // getUTCDay: 0=Sun, 1=Mon..6=Sat → convert to Mon=0..Sun=6
  const firstWeekday = (firstDate.getUTCDay() + 6) % 7;

  const totals = days.reduce(
    (acc, d) => {
      acc.pnl += d.pnl;
      acc.trades += d.trades;
      acc.greenDays += d.pnl > 0 ? 1 : 0;
      acc.redDays += d.pnl < 0 ? 1 : 0;
      return acc;
    },
    { pnl: 0, trades: 0, greenDays: 0, redDays: 0 },
  );

  const monthName = firstDate.toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="card-title">Calendar</div>
          <div className="mt-1 text-xl font-semibold">{monthName}</div>
        </div>
        <div className="grid grid-cols-3 gap-3 text-right text-xs text-muted">
          <div>
            <div>Net PnL</div>
            <div className={`text-base font-semibold ${totals.pnl > 0 ? 'text-profit' : totals.pnl < 0 ? 'text-loss' : 'text-slate-300'}`}>
              {formatCurrency(totals.pnl)}
            </div>
          </div>
          <div>
            <div>Green / Red</div>
            <div className="text-base font-semibold">
              <span className="text-profit">{totals.greenDays}</span>
              <span className="text-muted"> / </span>
              <span className="text-loss">{totals.redDays}</span>
            </div>
          </div>
          <div>
            <div>Trades</div>
            <div className="text-base font-semibold">{totals.trades}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-2 text-center text-xs uppercase tracking-wider text-muted">
        {WEEKDAYS.map((d) => (
          <div key={d} className="py-1">
            {d}
          </div>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-2">
        {Array.from({ length: firstWeekday }).map((_, i) => (
          <div key={`pad-${i}`} className="h-20 rounded-lg border border-dashed border-border-subtle/60" />
        ))}
        {days.map((d) => {
          const profit = d.pnl > 0;
          const loss = d.pnl < 0;
          const day = Number(d.date.split('-')[2]);
          const empty = d.trades === 0;
          return (
            <div
              key={d.date}
              className={`h-20 rounded-lg border p-2 text-left text-xs transition ${
                empty
                  ? 'border-border-subtle bg-bg-700/30 text-muted'
                  : profit
                    ? 'border-profit/40 bg-profit/15 text-profit'
                    : loss
                      ? 'border-loss/40 bg-loss/15 text-loss'
                      : 'border-border bg-bg-700 text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={empty ? 'font-medium text-muted' : 'font-semibold'}>{day}</span>
                {!empty && (
                  <span className="text-[10px] uppercase tracking-wider opacity-80">
                    {d.trades}T
                  </span>
                )}
              </div>
              {!empty && (
                <div className="mt-2 text-sm font-semibold">
                  {formatCurrency(d.pnl)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
