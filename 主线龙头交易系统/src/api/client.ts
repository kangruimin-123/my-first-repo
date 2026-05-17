import { BacktestData, EvaluationData, NewPositionInput, Position, RadarData, WatchlistItem } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl();

function defaultApiBaseUrl(): string {
  if (typeof window !== 'undefined' && window.location.hostname === 'localhost' && window.location.port === '3000') {
    return 'http://127.0.0.1:8000';
  }
  return '';
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  evaluation: () => request<EvaluationData>('/api/evaluation'),
  radar: () => request<RadarData>('/api/radar'),
  positions: () => request<Position[]>('/api/positions'),
  createPosition: (payload: NewPositionInput) => post<Position>('/api/positions', payload),
  watchlist: () => request<WatchlistItem[]>('/api/watchlist'),
  backtest: () => request<BacktestData>('/api/backtest'),
  status: () => request<{
    status: string;
    latest_trade_date: string;
    updated_at: string;
    trade_day: {
      last_phase: string;
      last_message: string;
      last_detail: string;
      last_run_at: string;
    };
  }>('/api/status'),
};

export function asNumber(value: string | number | undefined, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
