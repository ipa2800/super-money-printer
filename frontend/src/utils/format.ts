// utils/format.ts — 数字 / 百分比 / 成交量格式化

export function fmtNum(v: number | null | undefined, d = 2): string {
  if (v == null) return "-";
  return Number(v).toFixed(d);
}

export function changeClass(c: number | null | undefined): string {
  if (c == null || c === 0) return "text-ink-mute";
  return c > 0 ? "text-pos" : "text-neg";
}

export function fmtPct(v: number | null | undefined): string {
  if (v == null) return "-";
  return (v > 0 ? "+" : "") + fmtNum(v, 2) + "%";
}

export function fmtVol(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toLocaleString();
}

export function fmtShares(v: number | null | undefined): string {
  if (!v) return "-";
  return (v / 1e8).toFixed(2);
}

export function fmtAmt(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e12) return (v / 1e12).toFixed(2) + "万亿";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}