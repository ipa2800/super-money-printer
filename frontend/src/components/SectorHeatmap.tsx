// components/SectorHeatmap.tsx — 板块分析热力图
// 行=板块 (按综合分降序, top N), 列=维度, 颜色=分位 (红-灰-绿)
// 直观看到: 哪些板块在多维度上同时走强/走弱
import { useEffect, useState } from "react";
import * as echarts from "echarts";
import { sector, sectorAnalytics, type SectorAnalyticsRow, type SectorItem } from "../api";
import { fmtPct } from "../utils/format";

// 高级维度 (sector_analytics 有数据时用)
const ADV_DIMS = [
  { key: "ret_5d",          label: "5日%" },
  { key: "ret_20d",         label: "20日%" },
  { key: "rps_20",          label: "RPS" },
  { key: "accel_5_20",      label: "加速度" },
  { key: "net_flow_rank",   label: "资金分位" },
  { key: "limit_up_density", label: "涨停密度" },
  { key: "max_continuous",  label: "龙头连板" },
] as const;

// 基础维度 (sector.snapshot 总有数据, 降级用)
const BASIC_DIMS = [
  { key: "pct_chg",     label: "涨跌幅" },
  { key: "leader_pct",  label: "领涨%" },
  { key: "up_ratio",    label: "上涨比" },
  { key: "turnover",    label: "换手率" },
] as const;

export function SectorHeatmap({ topN = 30 }: { topN?: number }) {
  const [rows, setRows] = useState<SectorAnalyticsRow[]>([]);
  const [fallback, setFallback] = useState<SectorItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ref, setRef] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    // 先试 sector_analytics, 没数据降级到 sector.snapshot
    sectorAnalytics.rank({ sort_by: "rank_overall", limit: topN })
      .then(r => {
        if (r.items.length >= 5) {
          setRows(r.items);
          setFallback(null);
        } else {
          // 数据稀疏, 降级
          sector.snapshot().then(snap => {
            const sorted = [...snap.items]
              .sort((a, b) => Math.abs(b.pct_chg ?? 0) - Math.abs(a.pct_chg ?? 0))
              .slice(0, topN);
            setFallback(sorted);
          }).catch(e => setErr(e.message));
        }
      })
      .catch(() => {
        sector.snapshot().then(snap => {
          const sorted = [...snap.items]
            .sort((a, b) => Math.abs(b.pct_chg ?? 0) - Math.abs(a.pct_chg ?? 0))
            .slice(0, topN);
          setFallback(sorted);
        }).catch(e => setErr(e.message));
      });
  }, [topN]);

  useEffect(() => {
    if (!ref) return;
    if (fallback) {
      if (!fallback.length) return;
      const inst = echarts.init(ref, null, { renderer: "canvas" });
      inst.setOption(buildBasicOption(fallback), true);
      const ro = new ResizeObserver(() => inst.resize());
      ro.observe(ref);
      return () => { ro.disconnect(); inst.dispose(); };
    }
    if (!rows.length) return;
    const inst = echarts.init(ref, null, { renderer: "canvas" });
    inst.setOption(buildAdvOption(rows), true);
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref);
    return () => { ro.disconnect(); inst.dispose(); };
  }, [ref, rows, fallback]);

  const count = fallback ? fallback.length : rows.length;
  const mode = fallback ? "基础模式 (无 analytics 数据)" : "完整模式";

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
      <div className="flex items-center gap-2 text-xs text-ink-mute mb-2">
        <span className="text-ink font-medium">板块热力图</span>
        <span>·</span>
        <span>红=强 / 灰=中性 / 绿=弱 (A 股惯例)</span>
        <span className="ml-auto">{count} 个板块 · {mode}</span>
      </div>
      <div ref={setRef} style={{ height: 12 + count * 16 }} />
      {err && <div className="text-down text-xs">⚠ {err}</div>}
    </div>
  );
}

// ── 高级模式: sector_analytics (7 维度) ──
function buildAdvOption(rows: SectorAnalyticsRow[]): echarts.EChartsCoreOption {
  const sectorLabels = rows.map(r => r.name ?? r.code);
  const dimLabels = ADV_DIMS.map(d => d.label);
  const seriesData: [number, number, number][] = [];
  rows.forEach((r, ri) => {
    ADV_DIMS.forEach((d, ci) => {
      const v = (r as any)[d.key] as number | null;
      if (v == null) return;
      const norm = normalize(d.key, v);
      seriesData.push([ci, ri, norm]);
    });
  });
  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: { position: "top", backgroundColor: "#1e293b", borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      formatter: tooltipFormatter(rows, ADV_DIMS) },
    grid: { top: 20, right: 20, bottom: 20, left: 100 },
    xAxis: { type: "category", data: dimLabels, splitArea: { show: true },
      axisLabel: { color: "#cbd5e1", fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: "category", data: sectorLabels.slice().reverse(), splitArea: { show: true },
      // ponytail: 板块名白字直接画在 y 轴上, 不用 hover
      axisLabel: { color: "#f1f5f9", fontSize: 10, fontWeight: 600, interval: 0 }, axisLine: { show: false }, axisTick: { show: false } },
    visualMap: { show: false, min: -1, max: 1,
      // ponytail: A 股惯例「红涨绿跌」— 红=强, 绿=弱
      inRange: { color: ["#22c55e", "#14532d", "#1e293b", "#7f1d1d", "#ef4444"] } },
    series: [{ type: "heatmap", data: seriesData, label: { show: false },
      emphasis: { itemStyle: { borderColor: "#fbbf24", borderWidth: 1 } } }],
  };
}

// ── 基础模式: sector.snapshot (4 维度) ──
function buildBasicOption(rows: SectorItem[]): echarts.EChartsCoreOption {
  const sectorLabels = rows.map(r => r.name);
  const dimLabels = BASIC_DIMS.map(d => d.label);
  const seriesData: [number, number, number][] = [];
  rows.forEach((r, ri) => {
    const total = (r.up_count ?? 0) + (r.down_count ?? 0);
    const upRatio = total > 0 ? (r.up_count ?? 0) / total : 0;
    const values: Record<string, number | null> = {
      pct_chg:    r.pct_chg ?? null,
      leader_pct: r.leader_pct ?? null,
      up_ratio:   upRatio || null,
      turnover:   r.turnover ?? null,
    };
    BASIC_DIMS.forEach((d, ci) => {
      const v = values[d.key];
      if (v == null) return;
      const norm = normalize(d.key, v);
      seriesData.push([ci, ri, norm]);
    });
  });
  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: { position: "top", backgroundColor: "#1e293b", borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      formatter: tooltipFormatter(rows as any, BASIC_DIMS) },
    grid: { top: 20, right: 20, bottom: 20, left: 100 },
    xAxis: { type: "category", data: dimLabels, splitArea: { show: true },
      axisLabel: { color: "#cbd5e1", fontSize: 10 }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: "category", data: sectorLabels.slice().reverse(), splitArea: { show: true },
      // ponytail: 板块名白字直接画在 y 轴上, 不用 hover
      axisLabel: { color: "#f1f5f9", fontSize: 10, fontWeight: 600, interval: 0 }, axisLine: { show: false }, axisTick: { show: false } },
    visualMap: { show: false, min: -1, max: 1,
      // ponytail: A 股惯例「红涨绿跌」— 红=强, 绿=弱
      inRange: { color: ["#22c55e", "#14532d", "#1e293b", "#7f1d1d", "#ef4444"] } },
    series: [{ type: "heatmap", data: seriesData, label: { show: false },
      emphasis: { itemStyle: { borderColor: "#fbbf24", borderWidth: 1 } } }],
  };
}

// ── 归一化: 不同维度用不同参考值映射到 [-1, 1] ──
function normalize(key: string, v: number): number {
  switch (key) {
    case "ret_5d": case "ret_20d":
      return clamp(v / 10, -1, 1);                  // ±10% 满格
    case "pct_chg":
      return clamp(v / 5, -1, 1);                   // ±5% 满格 (日内更小)
    case "accel_5_20":
      return clamp(v, -1, 1);                       // 已是 -1..1 量级
    case "rps_20": case "net_flow_rank":
      return clamp(v / 50 - 1, -1, 1);              // 0-100 → -1..1
    case "limit_up_density":
      return clamp(v * 2 - 1, -1, 1);               // 0-1 → -1..1
    case "max_continuous":
      return clamp(v / 5 * 2 - 1, -1, 1);           // 0-10 连板
    case "leader_pct":
      return clamp(v / 7, -1, 1);                   // ±7% 满格
    case "up_ratio":
      return clamp(v * 2 - 1, -1, 1);               // 0-1 → -1..1
    case "turnover":
      return clamp(v / 5, -1, 1);                   // ±5% 换手率
    default: return 0;
  }
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function tooltipFormatter(rows: any[], dims: readonly { key: string; label: string }[]) {
  return (p: any) => {
    const r = rows[p.value[1]];
    const d = dims[p.value[0]] as any;
    const raw = r[d.key] as number | null | undefined;
    let display = "—";
    if (raw != null) {
      if (d.key === "rps_20" || d.key === "net_flow_rank") display = raw.toFixed(0);
      else if (d.key === "limit_up_density") display = (raw * 100).toFixed(1) + "%";
      else if (d.key === "max_continuous") display = raw.toFixed(0);
      else if (d.key === "up_ratio") display = (raw * 100).toFixed(0) + "%";
      else if (d.key === "turnover") display = raw.toFixed(2) + "%";
      else display = fmtPct(raw);
    }
    return `<b>${r.name ?? r.code}</b><br/>${d.label}: ${display}`;
  };
}

function buildOption(rows: SectorAnalyticsRow[]): echarts.EChartsCoreOption {
  // 列归一化: 每个维度的值映射到 [-1, 1], -1=最弱, 1=最强
  // 排序按综合分, 直接用 rows 顺序
  const sectorLabels = rows.map(r => r.name ?? r.code);
  const dimLabels = DIMS.map(d => d.label);

  // 计算每列 max/abs max, 用于归一化
  const seriesData: [number, number, number][] = [];
  rows.forEach((r, ri) => {
    DIMS.forEach((d, ci) => {
      const v = (r as any)[d.key] as number | null;
      if (v == null) return;
      let norm = 0;
      if (d.key === "ret_5d" || d.key === "ret_20d" || d.key === "accel_5_20") {
        // 涨跌/加速度: 用 ±10% / ±1 的对称归一化
        const ref = d.key === "accel_5_20" ? 1 : 10;
        norm = Math.max(-1, Math.min(1, v / ref));
      } else if (d.key === "rps_20" || d.key === "net_flow_rank") {
        // 已经是 0-100 分位, 直接 -1..1
        norm = (v / 100) * 2 - 1;
      } else if (d.key === "limit_up_density") {
        // 0-1 密度, ×2-1
        norm = Math.max(-1, Math.min(1, v * 2 - 1));
      } else if (d.key === "max_continuous") {
        // 0-10 连板, /5 -1
        norm = Math.max(-1, Math.min(1, (v / 5) * 2 - 1));
      }
      seriesData.push([ci, ri, norm]);
    });
  });

  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      position: "top",
      backgroundColor: "#1e293b", borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      formatter: (p: any) => {
        const r = rows[p.value[1]];
        const d = DIMS[p.value[0]];
        const raw = (r as any)[d.key] as number | null;
        return `<b>${r.name ?? r.code}</b><br/>${d.label}: ${raw == null ? "—" :
          d.key === "rps_20" || d.key === "net_flow_rank" ? raw.toFixed(0)
          : d.key === "limit_up_density" ? (raw * 100).toFixed(1) + "%"
          : d.key === "max_continuous" ? raw.toFixed(0)
          : fmtPct(raw)}`;
      },
    },
    grid: { top: 20, right: 20, bottom: 20, left: 100 },
    xAxis: {
      type: "category", data: dimLabels,
      splitArea: { show: true },
      axisLabel: { color: "#cbd5e1", fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category", data: sectorLabels.slice().reverse(),
      splitArea: { show: true },
      axisLabel: { color: "#94a3b8", fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    visualMap: {
      show: false,
      min: -1, max: 1,
      inRange: { color: ["#ef4444", "#7f1d1d", "#1e293b", "#14532d", "#22c55e"] },
    },
    series: [{
      type: "heatmap",
      data: seriesData,
      label: { show: false },
      emphasis: { itemStyle: { borderColor: "#fbbf24", borderWidth: 1 } },
    }],
  };
}