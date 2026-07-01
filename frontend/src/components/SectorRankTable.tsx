// components/SectorRankTable.tsx — 板块分析排名表 (4 维度合一)
// 默认按 rank_overall 降序, 点列头切换排序
import { useEffect, useState } from "react";
import { sectorAnalytics, type SectorAnalyticsRow, type SortBy } from "../api";
import { fmtNum, fmtVol, fmtPct } from "../utils/format";

const COLS: { key: SortBy; label: string; align?: "right" }[] = [
  { key: "rank_overall",    label: "综合分" },
  { key: "rps_20",          label: "RPS_20" },
  { key: "accel_5_20",      label: "加速度" },
  { key: "net_flow_rank",   label: "资金分位" },
  { key: "limit_up_density", label: "涨停密度" },
];

export function SectorRankTable({ onSelect }: { onSelect?: (symbol: string) => void }) {
  const [rows, setRows] = useState<SectorAnalyticsRow[]>([]);
  const [sortBy, setSortBy] = useState<SortBy>("rank_overall");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    sectorAnalytics.rank({ sort_by: sortBy, limit: 50 })
      .then(r => setRows(r.items))
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, [sortBy]);

  if (err) return <div className="text-down text-xs">⚠ {err}</div>;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-ink-mute">
        <span className="text-ink font-medium">板块分析</span>
        <span>·</span>
        <span>4 维度排名 (动量+强度 / 资金流 / 涨停密度 / 综合)</span>
        <span className="ml-auto">{loading ? "加载中…" : `${rows.length} 个`}</span>
      </div>
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-card-grad/95 backdrop-blur text-ink-mute text-[10px] uppercase">
          <tr>
            {["类型","名称","代码","最新价","5日%","20日%"].map(h =>
              <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
            )}
            {COLS.map(c =>
              <th key={c.key}
                  onClick={() => setSortBy(c.key)}
                  className={`px-3 py-2 text-right font-medium whitespace-nowrap cursor-pointer hover:text-ink
                              ${sortBy === c.key ? "text-pos" : ""}`}>
                {c.label}{sortBy === c.key ? " ▼" : ""}
              </th>
            )}
            <th className="px-3 py-2 text-right font-medium whitespace-nowrap">净额(亿)</th>
            <th className="px-3 py-2 text-right font-medium whitespace-nowrap">涨停/成分股</th>
            <th className="px-3 py-2 text-right font-medium whitespace-nowrap">龙头连板</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const pct5 = r.ret_5d ?? 0;
            const pct20 = r.ret_20d ?? 0;
            const cls5 = pct5 > 0 ? "text-pos" : pct5 < 0 ? "text-neg" : "text-ink-mute";
            const cls20 = pct20 > 0 ? "text-pos" : pct20 < 0 ? "text-neg" : "text-ink-mute";
            return (
              <tr key={`${r.type}:${r.code}`}
                  onClick={() => onSelect?.(`${r.type}:${r.code}`)}
                  className={`border-b border-white/[0.03] hover:bg-white/[0.04] cursor-pointer
                              ${onSelect ? "" : ""}`}>
                <td className="px-3 py-2">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] ${r.type === "industry" ? "bg-blue-500/20 text-blue-300" : "bg-purple-500/20 text-purple-300"}`}>
                    {r.type === "industry" ? "行业" : "概念"}
                  </span>
                </td>
                <td className="px-3 py-2 text-ink">{r.name ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-ink-dim">{r.code}</td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{r.price != null ? fmtNum(r.price, 0) : "—"}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${cls5}`}>{pct5 != null ? fmtPct(pct5) : "—"}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${cls20}`}>{pct20 != null ? fmtPct(pct20) : "—"}</td>
                {/* 4 维度列 */}
                <td className="px-3 py-2 text-right tabular-nums font-semibold text-ink">
                  {r.rank_overall != null ? fmtNum(r.rank_overall, 0) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.rps_20 != null ? <RpsBadge v={r.rps_20} /> : "—"}
                </td>
                <td className={`px-3 py-2 text-right tabular-nums ${(r.accel_5_20 ?? 0) > 0 ? "text-pos" : (r.accel_5_20 ?? 0) < 0 ? "text-neg" : "text-ink-mute"}`}>
                  {r.accel_5_20 != null ? fmtNum(r.accel_5_20, 3) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-soft">
                  {r.net_flow_rank != null ? fmtNum(r.net_flow_rank, 0) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-soft">
                  {r.limit_up_density != null ? (r.limit_up_density * 100).toFixed(1) + "%" : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-soft">
                  {r.net_flow != null ? fmtVol(r.net_flow) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-soft">
                  {r.limit_up_count != null && r.constituents_count != null
                    ? `${r.limit_up_count}/${r.constituents_count}`
                    : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.max_continuous != null && r.max_continuous > 0
                    ? <span className={r.max_continuous >= 3 ? "text-pos font-semibold" : "text-ink"}>{r.max_continuous}</span>
                    : "—"}
                </td>
              </tr>
            );
          })}
          {!rows.length && !loading && (
            <tr><td colSpan={14} className="text-center text-ink-mute py-8">暂无数据 (l5_sector_analytics 跑一次)</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// RPS 着色: 80+ 强势(绿), 60-80 中性(白), <60 弱势(灰)
function RpsBadge({ v }: { v: number }) {
  const cls = v >= 80 ? "text-pos" : v >= 60 ? "text-ink" : "text-ink-mute";
  return <span className={cls}>{v.toFixed(0)}</span>;
}