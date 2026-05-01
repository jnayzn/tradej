import type { ReactNode } from 'react';

interface Props {
  title: string;
  value: ReactNode;
  hint?: ReactNode;
  valueClassName?: string;
}

export default function StatCard({ title, value, hint, valueClassName = '' }: Props) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className={`stat-value ${valueClassName}`}>{value}</div>
      {hint !== undefined && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
