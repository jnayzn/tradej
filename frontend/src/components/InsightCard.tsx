import type { Finding } from '../types';

const STYLES: Record<Finding['kind'], { border: string; text: string; label: string }> = {
  success: { border: 'border-profit/40 bg-profit/10', text: 'text-profit', label: 'Good' },
  warning: { border: 'border-amber-500/40 bg-amber-500/10', text: 'text-amber-400', label: 'Warn' },
  danger: { border: 'border-loss/40 bg-loss/10', text: 'text-loss', label: 'Risk' },
  info: { border: 'border-brand/40 bg-brand/10', text: 'text-brand', label: 'Info' },
};

export default function InsightCard({ finding }: { finding: Finding }) {
  const s = STYLES[finding.kind];
  return (
    <div className={`rounded-2xl border p-5 ${s.border}`}>
      <div className={`text-xs font-semibold uppercase tracking-wider ${s.text}`}>
        {s.label}
      </div>
      <div className="mt-1 text-base font-semibold text-white">{finding.title}</div>
      <p className="mt-2 text-sm text-slate-300">{finding.detail}</p>
    </div>
  );
}
