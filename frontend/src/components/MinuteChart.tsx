// components/MinuteChart.tsx — 分时图 (价格折线 + 均价线 + 成交量柱)
import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { MinuteBar } from "../api";

export function MinuteChart({ data }: { data: MinuteBar[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !data.length) return;
    const inst = echarts.init(ref.current);
    const times = data.map(d => d.time);
    const prices = data.map(d => d.price);
    const avgs = data.map(d => d.avg_price);
    const vols = data.map(d => d.volume);
    const open = prices[0];
    const max = Math.max(...prices, ...avgs);
    const min = Math.min(...prices, ...avgs);
    const pad = (max - min) * 0.1 || 0.01;
    inst.setOption({
      backgroundColor: "transparent",
      animation: false,
      grid: [
        { left: 50, right: 20, top: 10, height: "60%" },
        { left: 50, right: 20, top: "75%", height: "20%" },
      ],
      tooltip: { trigger: "axis", axisPointer: { type: "cross" }, backgroundColor: "#1e293b", borderColor: "#334155", textStyle: { color: "#e2e8f0" } },
      xAxis: [
        { type: "category", data: times, gridIndex: 0, axisLabel: { show: false }, axisLine: { lineStyle: { color: "#334155" } } },
        { type: "category", data: times, gridIndex: 1, axisLabel: { color: "#64748b", fontSize: 10, interval: 59 }, axisLine: { lineStyle: { color: "#334155" } } },
      ],
      yAxis: [
        { scale: true, min: min - pad, max: max + pad, gridIndex: 0, axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "#1e293b" } } },
        { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      series: [
        {
          name: "价格", type: "line", data: prices, smooth: false, showSymbol: false,
          lineStyle: { color: "#3b82f6", width: 1.5 }, areaStyle: { color: "rgba(59,130,246,0.1)" },
          markLine: { silent: true, symbol: "none", lineStyle: { color: "#64748b", type: "dashed" }, data: [{ yAxis: open, label: { color: "#64748b", fontSize: 10, formatter: "开 {c}" } }] },
        },
        { name: "均价", type: "line", data: avgs, showSymbol: false, lineStyle: { color: "#eab308", width: 1 } },
        {
          name: "量", type: "bar", data: vols, xAxisIndex: 1, yAxisIndex: 1,
          itemStyle: { color: (p: { dataIndex: number }) => (prices[p.dataIndex] >= open ? "#22c55e" : "#ef4444"), opacity: 0.7 },
        },
      ],
    });
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); inst.dispose(); };
  }, [data]);
  return <div ref={ref} className="w-full h-72 md:h-80" />;
}