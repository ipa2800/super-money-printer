// components/SectorAnalyticsCharts.tsx — 轮动矩阵散点图 + 选中板块 5 维雷达
// ponytail: 单一文件装两图, 共享 sectorAnalytics 接口, 内部各自 fetch
import { useEffect, useState } from "react";
import { sectorAnalytics, type SectorMatrix, type SectorAnalyticsRow } from "../api";
import { useECharts } from "../hooks/useECharts";

const QUAD_COLORS: Record<string, string> = {
  "主升浪": "#ef4444",   // 红 — A 股惯例红涨
  "顶部":   "#eab308",   // 黄
  "反弹":   "#3b82f6",   // 蓝
  "杀跌":   "#22c55e",   // 绿 — A 股惯例绿跌
};

export function SectorAnalyticsCharts({ selected }: { selected: string | null }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <RotationMatrix />
      <SectorRadar selected={selected} />
    </div>
  );
}

// ── 轮动矩阵: X=RPS_20, Y=加速度, 4 象限配色 ──
function RotationMatrix() {
  const [matrix, setMatrix] = useState<SectorMatrix | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    sectorAnalytics.matrix()
      .then(r => setMatrix(r.matrix))
      .catch(e => setErr(e.message));
  }, []);
  const ref = useECharts(matrix ? buildMatrixOption(matrix) : null, [matrix]);
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
      <div className="flex items-center gap-2 text-xs text-ink-mute mb-2 flex-wrap">
        <span className="text-ink font-medium">轮动矩阵</span>
        <span>X=强度 RPS_20 · Y=加速度</span>
        {/* ponytail: 颜色图例 */}
        <span className="flex items-center gap-2 ml-3">
          {(["主升浪", "顶部", "反弹", "杀跌"] as const).map(k => (
            <span key={k} className="inline-flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: QUAD_COLORS[k] }} />
              <span>{k}</span>
            </span>
          ))}
        </span>
      </div>
      <div ref={ref} style={{ height: 320 }} />
      {err && <div className="text-down text-xs">⚠ {err}</div>}
    </div>
  );
}

function buildMatrixOption(matrix: SectorMatrix) {
  const series = Object.entries(matrix).map(([quad, rows]) => ({
    name: `${quad} (${rows.length})`,
    type: "scatter",
    symbolSize: (v: number[]) => Math.max(8, Math.min(28, 8 + Math.abs(v[1] || 0) * 40)),
    itemStyle: { color: QUAD_COLORS[quad] || "#94a3b8", opacity: 0.85 },
    data: rows.map(r => [
      r.rps_20 ?? 0,
      r.accel_5_20 ?? 0,
      r.name ?? r.code,
      `${r.type}:${r.code}`,
    ]),
  }));
  return {
    grid: { top: 30, right: 20, bottom: 40, left: 50 },
    tooltip: {
      trigger: "item",
      backgroundColor: "#1e293b", borderColor: "#334155",
      formatter: (p: { value: [number, number, string, string] }) =>
        `<b>${p.value[2]}</b><br/>RPS=${p.value[0].toFixed(0)} 加速度=${p.value[1].toFixed(3)}<br/>${p.value[3]}`,
    },
    legend: { top: 0, textStyle: { color: "#cbd5e1", fontSize: 10 } },
    xAxis: {
      type: "value", name: "RPS_20", min: 0, max: 100,
      nameTextStyle: { color: "#94a3b8" },
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    yAxis: {
      type: "value", name: "加速度", nameTextStyle: { color: "#94a3b8" },
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    // RPS=70 中位参考线 (强/弱分界)
    series: [
      ...series,
      {
        name: "强/弱分界",
        type: "line", symbol: "none",
        markLine: {
          silent: true, symbol: "none",
          data: [
            { xAxis: 70, lineStyle: { color: "#475569", type: "dashed" }, label: { show: false } },
            { yAxis: 0,  lineStyle: { color: "#475569", type: "dashed" }, label: { show: false } },
          ],
        },
        data: [],
      },
    ],
  };
}

// ── 雷达: 选中板块 5 维水平条 (用 bar 替代 radar — 更稳, 同信息密度) ──
function SectorRadar({ selected }: { selected: string | null }) {
  const [row, setRow] = useState<SectorAnalyticsRow | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) { setRow(null); return; }
    sectorAnalytics.rank({ limit: 500 })
      .then(r => {
        const hit = r.items.find(x => `${x.type}:${x.code}` === selected);
        setRow(hit ?? null);
      })
      .catch(e => setErr(e.message));
  }, [selected]);

  const ref = useECharts(row ? buildBarOption(row) : null, [row]);

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
      <div className="text-xs text-ink-mute mb-2">
        板块热度 5 维 {row ? `· ${row.name}` : "· 选中板块后显示"}
      </div>
      {/* ponytail: 占位浮在 ref 外面 — ref div 不能有条件子节点, 否则 ECharts 改 DOM 跟 React 打架 removeChild */}
      <div className="relative">
        <div ref={ref} style={{ height: 320 }} />
        {!selected && (
          <div className="absolute inset-0 flex items-center justify-center text-ink-mute text-xs pointer-events-none">
            ↑ 点上方表格任一行
          </div>
        )}
      </div>
      {err && <div className="text-down text-xs">⚠ {err}</div>}
    </div>
  );
}

function buildBarOption(r: SectorAnalyticsRow) {
  // 全部归一到 0-100; 加速度 50±50, 涨停密度 ×300 (一般 <30%)
  const accelN = Math.max(0, Math.min(100, 50 + (r.accel_5_20 ?? 0) * 50));
  const lupN   = Math.max(0, Math.min(100, (r.limit_up_density ?? 0) * 300));
  const dims = [
    { name: "RPS_20",     value: r.rps_20 ?? 0,         raw: r.rps_20 ?? 0 },
    { name: "加速度",     value: accelN,                raw: r.accel_5_20 ?? 0 },
    { name: "资金分位",   value: r.net_flow_rank ?? 0,   raw: r.net_flow_rank ?? 0 },
    { name: "涨停密度",   value: lupN,                  raw: (r.limit_up_density ?? 0) * 100 },
    { name: "综合分",     value: r.rank_overall ?? 0,   raw: r.rank_overall ?? 0 },
  ];
  return {
    grid: { top: 10, right: 50, bottom: 10, left: 70 },
    tooltip: {
      trigger: "axis", axisPointer: { type: "shadow" },
      backgroundColor: "#1e293b", borderColor: "#334155",
      formatter: () => `<b>${r.name}</b><br/>` + dims.map(d =>
        `${d.name}: ${typeof d.raw === "number" ? d.raw.toFixed(2) : "—"}`).join("<br/>"),
    },
    xAxis: {
      type: "value", min: 0, max: 100,
      axisLine:  { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
    },
    yAxis: {
      type: "category", data: dims.map(d => d.name).reverse(),
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#cbd5e1", fontSize: 11 },
    },
    series: [{
      type: "bar",
      data: dims.map(d => d.value).reverse(),
      barWidth: 14,
      itemStyle: {
        color: (p: { value: number }) =>
          p.value >= 80 ? "#22c55e" : p.value >= 50 ? "#3b82f6" : p.value >= 30 ? "#eab308" : "#64748b",
        borderRadius: [0, 4, 4, 0],
      },
      label: {
        show: true, position: "right", color: "#cbd5e1", fontSize: 10,
        formatter: (p: { value: number }) => p.value.toFixed(0),
      },
    }],
  };
}