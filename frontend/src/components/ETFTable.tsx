// components/ETFTable.tsx — ETF 实时表 (移动端横向滚动, 桌面完整显示)
import { useEffect, useState, useRef } from "react";
import * as echarts from "echarts";
import { etf, type ETFRealtime } from "../api";
import { useStore } from "../store";
import { fmtNum, fmtShares, changeClass, fmtAmt } from "../utils/format";
import { Icon } from "./icons";

export function ETFTable({ refreshKey }: { refreshKey?: number }) {
  const days = useStore(s => s.currentDays);
  const agg = useStore(s => s.currentAgg);
  const [codes, setCodes] = useState<string[]>([]);
  const [realtime, setRealtime] = useState<Record<string, ETFRealtime>>({});
  const [shares, setShares] = useState<Record<string, { date: string; shares: number }[]>>({});
  const [volumes, setVolumes] = useState<Record<string, { date: string; volume: number }[]>>({});
  const [asOf, setAsOf] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    etf.overview(days, agg).then(r => {
      setCodes(r.codes);
      setRealtime(r.realtime);
      setShares(r.shares_timeseries);
      setVolumes(r.volume_timeseries ?? {});
      setAsOf(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    }).catch(e => setErr(e.message));
  }, [days, agg, refreshKey]);

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;
  if (!codes.length) return <div className="text-ink-mute text-sm p-8 text-center">无 ETF 数据</div>;

  // 统计: 上涨 / 下跌 / 平盘 / 总成交额
  const ups = codes.filter(c => (realtime[c]?.pct_chg ?? 0) > 0).length;
  const dns = codes.filter(c => (realtime[c]?.pct_chg ?? 0) < 0).length;
  const flats = codes.length - ups - dns;
  const totalAmt = codes.reduce((s, c) => s + (realtime[c]?.amount ?? 0), 0);
  const names: Record<string, string> = Object.fromEntries(codes.map(c => [c, realtime[c]?.name ?? c]));

  return (
    <div className="space-y-2">
      {/* 顶部汇总条 */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-soft px-1">
        <span className="text-ink">{codes.length} 只</span>
        <span><span className="text-pos font-semibold">{ups}</span> 涨</span>
        <span><span className="text-neg font-semibold">{dns}</span> 跌</span>
        {flats > 0 && <span><span className="text-ink-mute">{flats}</span> 平</span>}
        <span>总成交额 <span className="text-ink">{fmtAmt(totalAmt)}</span></span>
        <span className="ml-auto text-ink-mute">截至 {asOf || "—"}</span>
      </div>

      {/* 份额趋势聚合图 (替代每行小图) */}
      <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
        <div className="text-xs text-ink-mute mb-1 px-1">ETF 份额趋势</div>
        <ShareTrendChart shares={shares} names={names} />
      </div>

      <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
        <table className="w-full text-xs min-w-[920px]">
          <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
            <tr>
              {["代码","名称","现价","涨跌","涨跌幅","振幅","换手率","IOPV","折溢价","份额(亿)","成交量走势"].map((h, i) =>
                <th key={h} className={`px-3 py-2 text-left font-medium whitespace-nowrap ${i === 10 ? "w-[324px]" : ""}`}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {codes.map(code => {
              const rt = realtime[code] ?? {};
              const pct = rt.pct_chg ?? 0;
              const volSeries = volumes[code] ?? [];
              return (
                <tr key={code} className="border-b border-white/[0.03]">
                  <td className="px-3 py-2 font-mono">{code}</td>
                  <td className="px-3 py-2">{rt.name ?? "-"}</td>
                  <td className="px-3 py-2">{fmtNum(rt.close, 3)}</td>
                  <td className={`px-3 py-2 ${changeClass(rt.change ?? 0)}`}>{fmtNum(rt.change, 3)}</td>
                  <td className={`px-3 py-2 ${pct > 0 ? "text-pos" : pct < 0 ? "text-neg" : "text-ink-mute"}`}>{pct > 0 ? "+" : ""}{fmtNum(pct, 2)}%</td>
                  <td className="px-3 py-2">{fmtNum(rt.amplitude, 2)}%</td>
                  <td className="px-3 py-2">{fmtNum(rt.turnover, 2)}%</td>
                  <td className="px-3 py-2">{fmtNum(rt.iopv, 3)}</td>
                  <td className="px-3 py-2">{fmtNum(rt.discount, 2)}%</td>
                  <td className="px-3 py-2">{fmtShares(rt.shares)}</td>
                  <td className="px-3 py-2"><VolumeSparkline series={volSeries} agg={agg} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// 8 色 (深色背景可分)
const PALETTE = ["#22c55e", "#ef4444", "#3b82f6", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

function ShareTrendChart({ shares, names }: { shares: Record<string, { date: string; shares: number }[]>; names: Record<string, string> }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const codes = Object.keys(shares);
    if (!codes.length) return;
    // 全部日期并集 (允许各 ETF 历史长度不一)
    const dateSet = new Set<string>();
    codes.forEach(c => shares[c]?.forEach(r => dateSet.add(r.date)));
    const dates = Array.from(dateSet).sort();
    const dateIdx = new Map(dates.map((d, i) => [d, i]));
    const series = codes.map((c, i) => {
      const data: (number | null)[] = new Array(dates.length).fill(null);
      shares[c]?.forEach(r => { const idx = dateIdx.get(r.date); if (idx != null) data[idx] = r.shares / 1e8; });
      return {
        name: names[c] ?? c,
        type: "line" as const,
        data,
        smooth: true,
        symbol: "none" as const,
        lineStyle: { width: 1.5, color: PALETTE[i % PALETTE.length] },
      };
    });
    const tickStep = Math.max(1, Math.floor((dates.length - 1) / 6));
    const inst = echarts.init(el, null, { width: el.clientWidth || 600, height: 220, renderer: "canvas" });
    inst.setOption({
      backgroundColor: "transparent",
      grid: { top: 12, right: 20, bottom: 42, left: 56, containLabel: false },
      tooltip: {
        trigger: "axis", backgroundColor: "#1e293b", borderColor: "#334155",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        axisPointer: { type: "cross", lineStyle: { color: "#475569" } },
        formatter: (params: { axisValue: string; marker: string; seriesName: string; data: number | null }[]) => {
          const date = params[0].axisValue;
          const rows = params.map(p => `${p.marker} ${p.seriesName}: ${(p.data ?? 0).toFixed(2)}亿`);
          return `${date}<br/>${rows.join("<br/>")}`;
        },
      },
      legend: { bottom: 4, textStyle: { color: "#94a3b8", fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
      xAxis: {
        type: "category", data: dates, boundaryGap: false,
        axisLabel: { color: "#64748b", fontSize: 9, interval: tickStep, formatter: (v: string) => v.slice(5) },
        axisLine: { lineStyle: { color: "#334155" } }, axisTick: { show: false },
      },
      yAxis: {
        scale: true,
        axisLabel: { color: "#94a3b8", fontSize: 10, formatter: (v: number) => v.toFixed(1) },
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
      },
      series,
    });
    return () => inst.dispose();
  }, [shares, names]);
  return <div ref={ref} className="w-full h-56" />;
}

// VolumeSparkline — 单行小柱图 (SVG + hover tooltip, 跟随 days+agg)
// ponytail: SVG 而非 ECharts (4 行 × 60 柱, ECharts 太重); hover 用 React state;
// 长周期 (n>60) 时均匀子采样; x 轴稀疏 5 个日期标签
function VolumeSparkline({ series, agg }: { series: { date: string; volume: number }[]; agg: "day" | "week" | "month" }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!series.length) return <span className="text-ink-mute text-[10px]">-</span>;
  const MAX_BARS = 60;
  const data = series.length > MAX_BARS
    ? Array.from({ length: MAX_BARS }, (_, i) => {
        const start = Math.floor((i * series.length) / MAX_BARS);
        const end = Math.floor(((i + 1) * series.length) / MAX_BARS);
        const slice = series.slice(start, Math.max(start + 1, end));
        const vol = slice.reduce((s, r) => s + r.volume, 0);
        return { date: slice[slice.length - 1].date, volume: vol };
      })
    : series;
  const W = 300, BAR_H = 26, AXIS_H = 12, H = BAR_H + AXIS_H, GAP = 1;
  const n = data.length;
  const barW = Math.max(1, (W - GAP * (n - 1)) / n);
  const maxV = Math.max(...data.map(r => r.volume), 1);
  // x 轴: 5 个稀疏标签 — 按位置分数插值日期, 避免节假日导致的后端桶缺失造成大跳 (例 10-11 → 11-01)
  const startMs = new Date(data[0].date).getTime();
  const endMs = new Date(data[n - 1].date).getTime();
  const tickFrac = n <= 5
    ? Array.from({ length: n }, (_, i) => n === 1 ? 0 : i / (n - 1))
    : [0, 0.25, 0.5, 0.75, 1];
  const tickDates = tickFrac.map(f => new Date(startMs + f * (endMs - startMs)).toISOString().slice(0, 10));
  const fmtTick = (d: string) => {
    if (agg === "month") return d.slice(0, 7);                    // 2026-06
    return d.slice(5);                                            // 06-29
  };
  const fmtVolShort = (v: number) => {
    if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
    if (v >= 1e4) return (v / 1e4).toFixed(0) + "万";
    return v.toFixed(0);
  };
  return (
    <div className="relative inline-block" onMouseLeave={() => setHover(null)}>
      <svg
        width={W} height={H} viewBox={`0 0 ${W} ${H}`}
        className="block"
        onMouseMove={e => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const i = Math.min(n - 1, Math.max(0, Math.floor(x / (barW + GAP))));
          setHover(i);
        }}
      >
        {data.map((r, i) => {
          const h = Math.max(1, (r.volume / maxV) * (BAR_H - 2));
          const prev = i > 0 ? data[i - 1].volume : r.volume;
          const baseColor = r.volume > prev ? "#22c55e" : r.volume < prev ? "#ef4444" : "#64748b";
          const isHover = hover === i;
          return (
            <rect
              key={r.date}
              x={i * (barW + GAP)} y={BAR_H - h}
              width={barW} height={h}
              fill={isHover ? "#e2e8f0" : baseColor}
              opacity={hover != null && !isHover ? 0.55 : 1}
            />
          );
        })}
        {tickDates.map((date, i) => {
          const x = tickFrac[i] * (W - barW) + barW / 2;
          return (
            <text key={i} x={x} y={H - 1} fontSize={8} fill="#64748b" textAnchor="middle">
              {fmtTick(date)}
            </text>
          );
        })}
        {hover != null && (
          <line
            x1={hover * (barW + GAP) + barW / 2} x2={hover * (barW + GAP) + barW / 2}
            y1={0} y2={BAR_H}
            stroke="#94a3b8" strokeWidth={0.5} strokeDasharray="2 2"
          />
        )}
      </svg>
      {hover != null && (
        <div
          className="absolute z-10 px-2 py-1 rounded bg-slate-800 border border-slate-600 text-[10px] text-slate-100 whitespace-nowrap pointer-events-none"
          style={{
            left: Math.min(W - 80, Math.max(0, hover * (barW + GAP) + barW / 2 - 40)),
            top: -30,
          }}
        >
          <div className="text-slate-400">{data[hover].date}</div>
          <div className="font-mono">{fmtVolShort(data[hover].volume)}</div>
        </div>
      )}
    </div>
  );
}
