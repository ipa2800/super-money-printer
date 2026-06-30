// api.ts — 所有后端端点的强类型封装 (一个文件覆盖所有域, 避免碎片化)

class HttpError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
    throw new HttpError(r.status, detail || `HTTP ${r.status}`);
  }
  return r.json();
}

const jsonPost = <T = unknown>(url: string, body?: unknown) =>
  request<T>(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
const jsonPatch = <T = unknown>(url: string, body?: unknown) =>
  request<T>(url, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });

// ── 类型 ──
export type Agg = "day" | "week" | "month";
export type KLineRow = { date: string; open: number; high: number; low: number; close: number; volume?: number; amount?: number };
export type MacroCard = {
  name: string; value: number; unit?: string; change?: number; date?: string;
  decimals?: number; source?: string; sparkline?: { date: string; value: number }[];
};
export type ETFRealtime = {
  code: string; name?: string; close?: number; change?: number; pct_chg?: number;
  iopv?: number; discount?: number; volume?: number; amount?: number;
  amplitude?: number; turnover?: number; shares?: number;
};
export type Alert = {
  id: number; alert_type: string; severity: "red" | "yellow"; source?: string;
  message: string; detail?: string; created_at: string; acknowledged?: boolean;
};
export type AlertSummary = { red: number; yellow: number; top: Alert[] };
export type Job = {
  job_id: string; layer: string; cron_expr: string; description?: string;
  enabled?: boolean; last_status?: string; last_run_at?: string | null;
};
export type JobLogEntry = { task_id: string; date: string; status: string; completed_at?: string };
export type ETFItem = { code: string; name?: string };
export type ETFSearchResult = { code: string; name: string };
export type IndexItem = { symbol: string; name?: string; min_date?: string; max_date?: string; n?: number };
export type StockItem = { code: string; name?: string };
export type StockSearchResult = { code: string; name: string };
export type StockRealtime = {
  code: string; name: string; price: number; prev_close: number;
  open: number; high: number; low: number; volume: number; amount: number;
  change: number; change_pct: number; time: string;
};
export type MinuteBar = { time: string; price: number; volume: number; amount: number; avg_price: number };
export type CacheItem = {
  scope: string; key: string; last_success: string | null;
  status: "success" | "stale" | "never" | "failed";
  ttl_seconds: number; row_count: number;
};
export type KLineData = { symbol: string; days: number; agg: Agg; count: number; data: KLineRow[] };

// ── 端点 ──
// alerts
export const alerts = {
  list:    (onlyUnack = false, limit = 50) => request<{ alerts: Alert[] }>(`/api/alerts?only_unack=${onlyUnack}&limit=${limit}`),
  summary: (limit = 3) => request<AlertSummary>(`/api/alerts/summary?limit=${limit}`),
  check:   () => jsonPost<{ triggered: number }>("/api/alerts/check"),
  ack:     (id: number) => jsonPost<{ ok: boolean }>(`/api/alerts/${id}/ack`),
};
// cache
export const cache = {
  status:   () => request<{ now: string; items: CacheItem[] }>("/api/cache/status"),
  ranges:   () => request<Record<string, Record<string, unknown>>>(`/api/cache/ranges`),
  refresh:  (jobId?: string) => jsonPost<{ result: string }>("/api/cache/refresh", jobId ? { job_id: jobId } : {}),
  backfill: (symbol: string, freq = "d", days = 30) =>
    jsonPost<{ symbol: string; n_written: number }>("/api/cache/backfill", { symbol, freq, days }),
  clear:    (scope: string, key?: string) => jsonPost<{ deleted: number }>("/api/cache/clear", { scope, key }),
};
// etf
export const etf = {
  list:     () => request<{ etfs: ETFItem[] }>("/api/etf/list"),
  add:      (code: string, name: string) => jsonPost<{ ok: boolean }>("/api/etf/add", { code, name }),
  remove:   (code: string) => request<{ ok: boolean }>(`/api/etf/${code}`, { method: "DELETE" }),
  search:   (q: string) => request<{ results: ETFSearchResult[] }>(`/api/etf/search?q=${encodeURIComponent(q)}`),
  overview: (days = 30) => request<{
    codes: string[]; shares_timeseries: Record<string, { date: string; shares: number }[]>;
    realtime: Record<string, ETFRealtime>;
  }>(`/api/etf/overview?days=${days}`),
};
// index
export const indexApi = {
  poolList:  () => request<{ indexes: IndexItem[] }>("/api/index/pool/list"),
  cacheList: () => request<{ indexes: IndexItem[] }>("/api/index/cache/list"),
  add:       (symbol: string, name?: string) => jsonPost<{ ok: boolean }>("/api/index/add", { symbol, name }),
  remove:    (symbol: string) => request<{ ok: boolean }>(`/api/index/remove?symbol=${encodeURIComponent(symbol)}`, { method: "DELETE" }),
  data:      (symbol: string, days = 30, agg: Agg = "day") =>
    request<KLineData>(`/api/index/data?symbol=${encodeURIComponent(symbol)}&freq=d&days=${days}&agg=${agg}`),
  kline:     (symbol: string, freq = "d", limit = 60) =>
    request<{ symbol: string; freq: string; count: number; data: KLineRow[] }>(`/api/index/kline?symbol=${encodeURIComponent(symbol)}&freq=${freq}&limit=${limit}`),
};
// stock
export const stock = {
  list:    () => request<{ stocks: StockItem[] }>("/api/stock/list"),
  add:     (code: string, name: string) => jsonPost<{ ok: boolean }>("/api/stock/add", { code, name }),
  remove:  (code: string) => request<{ ok: boolean }>(`/api/stock/${code}`, { method: "DELETE" }),
  search:  (q: string) => request<{ results: StockSearchResult[] }>(`/api/stock/search?q=${encodeURIComponent(q)}`),
  summary: (code: string) => request<Record<string, unknown>>(`/api/stock/${code}/summary`),
  fundFlow:(code: string) => request<{ rows: Record<string, unknown>[] }>(`/api/stock/${code}/fund_flow`),
  news:    (code: string, limit = 10) => request<{ news: Record<string, unknown>[] }>(`/api/stock/${code}/news?limit=${limit}`),
  kline:   (code: string, freq = "d", limit = 60) =>
    request<{ data: KLineRow[] }>(`/api/stock/${code}/kline?freq=${freq}&limit=${limit}`),
  realtime:(codes?: string[]) =>
    request<{ as_of: string; items: Record<string, StockRealtime> }>(
      `/api/stock/realtime${codes?.length ? `?codes=${codes.join(",")}` : ""}`,
    ),
  minute:  (code: string) => request<{ code: string; count: number; data: MinuteBar[] }>(`/api/stock/${code}/minute`),
};
// macro
export const macro = {
  cards:  () => request<{ cards: MacroCard[] }>("/api/macro/cards"),
  data:   (indicator: string, limit = 30) => request<{ indicator: string; rows: { date: string; value: number }[] }>(`/api/macro/data?indicator=${indicator}&limit=${limit}`),
  ranges: () => request<Record<string, unknown>>("/api/macro/ranges"),
};
// jobs
export const jobs = {
  list:  () => request<{ jobs: Job[] }>("/api/jobs"),
  patch: (id: string, body: { cron_expr?: string; enabled?: boolean; description?: string }) =>
    jsonPatch<{ ok: boolean }>(`/api/jobs/${id}`, body),
  log:   (id: string, limit = 10) => request<{ job_id: string; logs: JobLogEntry[] }>(`/api/jobs/${id}/log?limit=${limit}`),
};

export { HttpError };