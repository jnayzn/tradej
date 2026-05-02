import axios from 'axios';
import type {
  AuthPayload,
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

export const TOKEN_STORAGE_KEY = 'tradej.authToken';

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn;
}

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      unauthorizedHandler?.();
    }
    return Promise.reject(error);
  },
);

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

export async function register(input: {
  username: string;
  email?: string;
  password: string;
}): Promise<AuthPayload> {
  const { data } = await api.post<AuthPayload>('/auth/register/', input);
  return data;
}

export async function login(input: {
  username: string;
  password: string;
}): Promise<AuthPayload> {
  const { data } = await api.post<AuthPayload>('/auth/login/', input);
  return data;
}

export async function fetchMe(): Promise<AuthPayload> {
  const { data } = await api.get<AuthPayload>('/auth/me/');
  return data;
}

export async function regenerateToken(): Promise<AuthPayload> {
  const { data } = await api.post<AuthPayload>('/auth/regenerate-token/');
  return data;
}
