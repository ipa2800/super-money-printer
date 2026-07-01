// components/MacroGrid.tsx — 8 个宏观指标卡片 (grid 响应式: 移动 1, md 2, lg 4 列)
// 跟随顶部 currentDays 刷新 (agg 不适用: 各指标有自身天然频率)
import { useState } from "react";
import { useEffect } from "react";
import { macro } from "../api";
import { useStore } from "../store";
import { fmtNum, changeClass } from "../utils/format";
import { Icon } from "./icons";

type Card = { name: string; value: number; unit?: string; change?: number; date?: string; decimals?: number; source?: string; sparkline?: { date: string; value: number }[] };

export function MacroGrid({ cards: ext, refreshKey }: { cards?: Card[]; refreshKey?: number }) {
  const days = useStore(s => s.currentDays);  // ponytail: /api/macro/cards 不接 days, 仅用作刷新触发
  const [cards, setCards] = useState<Card[] | null>(ext ?? null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (ext) { setCards(ext); return; }
    setCards(null);
    macro.cards().then(r => setCards(r.cards)).catch(e => setErr(e.message));
  }, [ext, refreshKey, days]);

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;
  if (!cards) return <div className="text-ink-mute text-xs">加载中...</div>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map(c => <CardEl key={c.name} c={c} />)}
    </div>
  );
}

function CardEl({ c }: { c: Card }) {
  const data = (c.sparkline ?? []).slice(-30);
  const color = (c.change ?? 0) >= 0 ? "#ef4444" : "#22c55e";
  const decimals = c.decimals ?? 2;
  const tip = `${c.name}\n${data.length} 期: 最低 ${data.length ? Math.min(...data.map(p => p.value)).toFixed(decimals) : "-"}\n最高 ${data.length ? Math.max(...data.map(p => p.value)).toFixed(decimals) : "-"}\n源: ${c.source ?? "akshare"}`;
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4 overflow-hidden relative" title={tip}>
      <div className="flex justify-between text-xs text-ink-mute uppercase tracking-wider">
        <span>{c.name}</span><span>{c.date ?? ""}</span>
      </div>
      <div className="text-xl font-bold mt-1">{fmtNum(c.value, decimals)}<span className="text-xs ml-1 text-ink-mute">{c.unit ?? ""}</span></div>
      <div className={`text-xs mt-1 ${changeClass(c.change ?? 0)}`}>{(c.change ?? 0) > 0 ? "+" : ""}{fmtNum(c.change ?? 0, decimals)}</div>
      <div className="h-16 mt-2 -mx-1">
        <Sparkline points={data} color={color} decimals={decimals} />
      </div>
    </div>
  );
}

// ponytail: 静态 sparkline, 不参与响应或重渲染, vanilla echarts 直接初始化
import * as echarts from "echarts";
import { useRef } from "react";
function Sparkline({ points, color, decimals = 2 }: { points: { date: string; value: number }[]; color: string; decimals?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !points.length) return;
    const inst = echarts.init(el, null, { width: el.clientWidth || 200, height: 64, renderer: "canvas" });
    const dates = points.map(p => p.date);
    const values = points.map(p => p.value);
    // 每 ~⅓ 处一个 tick, 30 点 → 显示 4 个日期
    const tickStep = Math.max(1, Math.floor((points.length - 1) / 3));
    inst.setOption({
      backgroundColor: "transparent",
      grid: { top: 2, right: 14, bottom: 18, left: 14, containLabel: false },
      xAxis: {
        type: "category", data: dates, boundaryGap: true,
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: "#64748b", fontSize: 9, margin: 4, interval: tickStep, hideOverlap: true, formatter: (v: string) => v.slice(5) },
      },
      yAxis: { type: "value", show: false, scale: true },
      tooltip: {
        show: true, trigger: "axis", confine: true,
        backgroundColor: "#1e293b", borderColor: "#334155",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        formatter: (params: { axisValue: string; data: number }[]) =>
          `${params[0].axisValue}<br/>${params[0].data.toFixed(decimals)}`,
      },
      series: [{
        type: "line", data: values, smooth: true, symbol: "none",
        lineStyle: { color, width: 1.5 },
        areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: color + "40" }, { offset: 1, color: color + "00" }] } },
      }],
    });
    return () => inst.dispose();
  }, [points, color, decimals]);
  return <div ref={ref} className="w-full h-full" />;
}
