// components/KLineChart.tsx — K 线蜡烛图 (支持外部 data 或自取数)
import { useState } from "react";
import { useEffect } from "react";
import { useStore } from "../store";
import { indexApi, type KLineRow } from "../api";
import { useECharts } from "../hooks/useECharts";

const OPT = {
  backgroundColor: "transparent",
  grid: { top: 30, right: 20, bottom: 40, left: 65 },
  tooltip: { trigger: "axis", backgroundColor: "#1e293b", borderColor: "#334155",
    textStyle: { color: "#e2e8f0", fontSize: 12 }, axisPointer: { type: "cross", lineStyle: { color: "#475569" } } },
  xAxis: { type: "category", data: [] as string[], axisLine: { lineStyle: { color: "#475569" } }, axisLabel: { color: "#94a3b8", fontSize: 11 } },
  yAxis: { scale: true, axisLine: { lineStyle: { color: "#475569" } }, axisLabel: { color: "#94a3b8", fontSize: 11 }, splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } } },
  dataZoom: [
    { type: "inside", start: 70, end: 100 },
    { type: "slider", start: 70, end: 100, height: 18, bottom: 8, borderColor: "#334155",
      fillerColor: "rgba(59,130,246,0.2)", handleStyle: { color: "#3b82f6" }, textStyle: { color: "#94a3b8" } },
  ],
  series: [{ type: "candlestick", data: [] as number[][],
    itemStyle: { color: "#22c55e", color0: "#ef4444", borderColor: "#22c55e", borderColor0: "#ef4444" } }],
};

type Props = { symbol?: string; freq?: string; data?: KLineRow[] };

export function KLineChart(props: Props) {
  const controlled = props.data !== undefined;
  const days = useStore(s => s.currentDays);
  const agg  = useStore(s => s.currentAgg);
  const [fetched, setFetched] = useState<KLineRow[]>([]);
  const [status, setStatus] = useState<string>("就绪");
  const symbol = props.symbol ?? "sh.000300";
  const freq   = props.freq   ?? "d";

  useEffect(() => {
    if (controlled) return;
    setStatus(`加载中: ${symbol} ${days}d/${agg}...`);
    indexApi.data(symbol, days, agg)
      .then(p => { setFetched(p.data); setStatus(`✅ ${p.count} 条 (${p.data[0]?.date ?? "-"} → ${p.data[p.data.length-1]?.date ?? "-"})`); })
      .catch(e => setStatus(`❌ ${e.message}`));
  }, [symbol, freq, days, agg, controlled]);

  const data = controlled ? (props.data ?? []) : fetched;

  const option = {
    ...OPT,
    title: { text: `${symbol} · ${freq.toUpperCase()} · ${days}d/${agg}`, left: "center",
      textStyle: { color: "#e2e8f0", fontSize: 13, fontWeight: "normal" } },
    xAxis: { ...OPT.xAxis, data: data.map(r => r.date) },
    series: [{ ...OPT.series[0], data: data.map(r => [r.open, r.close, r.low, r.high]) }],
  };

  const chartRef = useECharts(option, [data]);
  return (
    <>
      <div ref={chartRef} className="w-full h-72 md:h-80" />
      {!controlled && <div className="text-ink-mute text-[11px] mt-2 text-right">{status}</div>}
    </>
  );
}
