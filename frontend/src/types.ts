export type OrderType = 'BUY' | 'SELL';

export interface Trade {
  id: number;
  ticket: number | null;
  symbol: string;
  order_type: OrderType;
  volume: string;
  open_time: string;
  close_time: string;
  open_price: string;
  close_price: string;
  profit: string;
  commission: string;
  swap: string;
  comment: string;
  magic_number: number | null;
  mae: string | null;
  mfe: string | null;
  notes: string;
  net_profit: string;
  is_win: boolean;
  duration_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Summary {
  total_trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  winrate: number;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
  biggest_win: number;
  biggest_loss: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  expectancy: number;
  average_trade: number;
}

export interface EquityPoint {
  trade_id: number;
  close_time: string;
  symbol: string;
  pnl: number;
  equity: number;
}

export interface CalendarDay {
  date: string;
  pnl: number;
  trades: number;
  wins: number;
  losses: number;
}

export interface CalendarMonth {
  year: number;
  month: number;
  days: CalendarDay[];
}

export interface SymbolStat {
  symbol: string;
  trades: number;
  wins: number;
  losses: number;
  pnl: number;
  winrate: number;
}

export type FindingKind = 'success' | 'warning' | 'danger' | 'info';

export interface Finding {
  kind: FindingKind;
  title: string;
  detail: string;
}

export interface Insights {
  score: number;
  findings: Finding[];
  metrics: Record<string, number>;
}

export interface ImportResult {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface BridgeInfo {
  owner_username: string;
  token: string;
  last_sync_at: string | null;
}
