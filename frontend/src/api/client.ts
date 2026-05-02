import axios from 'axios';
import type {
  BridgeInfo,
  CalendarMonth,
  EquityPoint,
  ImportResult,
  Insights,
  PaginatedResponse,
  Summary,
  SymbolStat,
  Trade,
} from '../types';

export const baseURL =
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

// Endpoints that can legitimately return 401 (the bridge/info endpoint never
// does, but in case the server's owner token was rotated externally and the
// stored one is stale, we want to refetch — not bounce to a login screen
// since there isn't one).
const SAFE_401_ENDPOINTS = ['/bridge/info/', '/bridge/regenerate-token/'];

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const requestUrl = error?.config?.url ?? '';
    const isSafeRequest = SAFE_401_ENDPOINTS.some((path) => requestUrl.includes(path));
    if (error?.response?.status === 401 && !isSafeRequest) {
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

export async function fetchBridgeInfo(): Promise<BridgeInfo> {
  const { data } = await api.get<BridgeInfo>('/bridge/info/');
  return data;
}

export async function regenerateBridgeToken(): Promise<BridgeInfo> {
  const { data } = await api.post<BridgeInfo>('/bridge/regenerate-token/');
  return data;
}

export function bridgeScriptDownloadUrl(): string {
  return `${baseURL}/bridge/script/`;
}
