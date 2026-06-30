// utils.js — DOM helpers, formatters, ECharts spark helper
export const $ = (id) => document.getElementById(id);

// ── 数字 / 百分比 / 成交量格式化 ──
export function fmtNum(v, d) {
  if (v == null) return "-";
  return Number(v).toFixed(d ?? 2);
}
export function changeClass(c) {
  if (c > 0) return "up";
  if (c < 0) return "down";
  return "flat";
}
export function fmtPct(v) {
  if (v == null) return "-";
  return (v > 0 ? "+" : "") + fmtNum(v, 2) + "%";
}
export function fmtVol(v) {
  if (!v) return "-";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString();
}
export function fmtShares(v) {
  if (!v) return "-";
  return (v / 1e8).toFixed(2);
}

// ── ECharts sparkline (mini line) ──
export function sparkOption(values, color) {
  return {
    backgroundColor: "transparent",
    grid: { top: 2, right: 2, bottom: 2, left: 2, containLabel: false },
    xAxis: { type: "category", show: false, data: values.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    tooltip: { show: false },
    series: [{
      type: "line", data: values, smooth: true, symbol: "none",
      lineStyle: { color, width: 1.5 },
      areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: color + "40" }, { offset: 1, color: color + "00" }] } },
    }],
  };
}
// ponytail: explicit width prevents canvas-bleed when CSS grid settles after init
export function initSpark(el, opt) {
  const w = el.offsetWidth || 200;
  const h = el.offsetHeight || 36;
  const inst = echarts.init(el, null, { width: w, height: h, renderer: "canvas" });
  inst.setOption(opt);
  return inst;
}

// ── fetch wrapper — throws Error with detail message ──
export async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// ── HTTP helpers (used by API modules) ──
export const POST = (url, body) => fetchJSON(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body ?? {}),
});
export const DELETE_ = (url) => fetchJSON(url, { method: "DELETE" });
export const PATCH_ = (url, body) => fetchJSON(url, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body ?? {}),
});

// ── HTML escape for safe interpolation ──
export function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}