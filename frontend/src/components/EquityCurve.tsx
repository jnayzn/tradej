import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  TimeScale,
  Tooltip,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { Line } from 'react-chartjs-2';
import type { EquityPoint } from '../types';

ChartJS.register(
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  TimeScale,
  Tooltip,
  Legend,
  Filler,
);

interface Props {
  points: EquityPoint[];
}

export default function EquityCurve({ points }: Props) {
  if (points.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center text-sm text-muted">
        No trades yet — import your MT5 history to see your equity curve.
      </div>
    );
  }

  const data = {
    datasets: [
      {
        label: 'Equity',
        data: points.map((p) => ({ x: p.close_time, y: p.equity })),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.15)',
        fill: true,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 4,
        borderWidth: 2,
      },
    ],
  };

  return (
    <div className="h-72">
      <Line
        data={data}
        options={{
          maintainAspectRatio: false,
          responsive: true,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#10141c',
              borderColor: '#222a37',
              borderWidth: 1,
              titleColor: '#e2e8f0',
              bodyColor: '#cbd5e1',
              callbacks: {
                title: (items) => new Date(items[0].parsed.x as number).toLocaleString(),
                label: (item) =>
                  `Equity: ${Number(item.parsed.y).toLocaleString('en-US', {
                    style: 'currency',
                    currency: 'USD',
                  })}`,
              },
            },
          },
          scales: {
            x: {
              type: 'time',
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: { color: '#7e8aa0' },
            },
            y: {
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: {
                color: '#7e8aa0',
                callback: (v) => `$${Number(v).toLocaleString()}`,
              },
            },
          },
        }}
      />
    </div>
  );
}
