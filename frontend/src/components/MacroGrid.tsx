// components/MacroGrid.tsx — 8 个宏观指标卡片 (grid 响应式: 移动 1, md 2, lg 4 列)
import { useState } from "react";
import { useEffect } from "react";
import { macro } from "../api";
import { fmtNum, changeClass } from "../utils/format";

type Card = { name: string; value: number; unit?: string; change?: number; date?: string; decimals?: number; source?: string; sparkline?: { date: string; value: number }[] };

export function MacroGrid({ cards: ext }: { cards?: Card[] }) {
  const [cards, setCards] = useState<Card[] | null>(ext ?? null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (ext) { setCards(ext); return; }
    macro.cards().then(r => setCards(r.cards)).catch(e => setErr(e.message));
  }, [ext]);

  if (err) return <div className="text-down text-sm">❌ {err}</div>;
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
  const tip = `${c.name}\n${data.length} 期: 最低 ${data.length ? Math.min(...data.map(p => p.value)).toFixed(c.decimals ?? 2) : "-"}\n最高 ${data.length ? Math.max(...data.map(p => p.value)).toFixed(c.decimals ?? 2) : "-"}\n源: ${c.source ?? "akshare"}`;
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4 overflow-hidden relative" title={tip}>
      <div className="flex justify-between text-xs text-ink-mute uppercase tracking-wider">
        <span>{c.name}</span><span>{c.date ?? ""}</span>
      </div>
      <div className="text-xl font-bold mt-1">{fmtNum(c.value, c.decimals)}<span className="text-xs ml-1 text-ink-mute">{c.unit ?? ""}</span></div>
      <div className={`text-xs mt-1 ${changeClass(c.change ?? 0)}`}>{(c.change ?? 0) > 0 ? "+" : ""}{fmtNum(c.change ?? 0, c.decimals)}</div>
      <div className="h-14 mt-2 -mx-1">
        <Sparkline values={data.map(p => p.value)} color={color} />
      </div>
    </div>
  );
}

// ponytail: 静态 sparkline, 不参与响应或重渲染, vanilla echarts 直接初始化
import * as echarts from "echarts";
import { useRef } from "react";
function Sparkline({ values, color }: { values: number[]; color: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !values.length) return;
    const inst = echarts.init(el, null, { width: el.clientWidth || 200, height: 56, renderer: "canvas" });
    inst.setOption({
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
    });
    return () => inst.dispose();
  }, [values, color]);
  return <div ref={ref} className="w-full h-full" />;
}
