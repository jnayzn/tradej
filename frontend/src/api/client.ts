import axios from 'axios';
import type {
  CalendarMonth,
  EquityPoint,
  ImportResult,
  Insights,
  PaginatedResponse,
  Summary,
  SymbolStat,
  Trade,
} from '../types';

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8000/api';

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

export async function listTrades(params: {
  limit?: number;
  offset?: number;
  ordering?: string;
  search?: string;
} = {}): Promise<PaginatedResponse<Trade>> {
  const { data } = await api.get<PaginatedResponse<Trade>>('/trades/', { params });
  return data;
}

export async function getSummary(): Promise<Summary> {
  const { data } = await api.get<Summary>('/stats/summary/');
  return data;
}

export async function getEquity(): Promise<EquityPoint[]> {
  const { data } = await api.get<{ points: EquityPoint[] }>('/stats/equity/');
  return data.points;
}

export async function getCalendar(year: number, month: number): Promise<CalendarMonth> {
  const { data } = await api.get<CalendarMonth>('/stats/calendar/', {
    params: { year, month },
  });
  return data;
}

export async function getBySymbol(): Promise<SymbolStat[]> {
  const { data } = await api.get<{ symbols: SymbolStat[] }>('/stats/by-symbol/');
  return data.symbols;
}

export async function getInsights(): Promise<Insights> {
  const { data } = await api.get<Insights>('/stats/insights/');
  return data;
}

export async function importFile(file: File): Promise<ImportResult> {
  const fd = new FormData();
  fd.append('file', file);
  const { data } = await api.post<ImportResult>('/trades/import/', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}
