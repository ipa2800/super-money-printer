// components/ETFTable.tsx — ETF 实时表 (移动端横向滚动, 桌面完整显示)
import { useEffect, useState, useRef } from "react";
import * as echarts from "echarts";
import { etf, type ETFRealtime } from "../api";
import { useStore } from "../store";
import { fmtNum, fmtVol, fmtShares, changeClass } from "../utils/format";

export function ETFTable() {
  const days = useStore(s => s.currentDays);
  const [codes, setCodes] = useState<string[]>([]);
  const [realtime, setRealtime] = useState<Record<string, ETFRealtime>>({});
  const [shares, setShares] = useState<Record<string, { date: string; shares: number }[]>>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    etf.overview(days).then(r => { setCodes(r.codes); setRealtime(r.realtime); setShares(r.shares_timeseries); }).catch(e => setErr(e.message));
  }, [days]);

  if (err) return <div className="text-down text-sm">❌ {err}</div>;
  if (!codes.length) return <div className="text-ink-mute text-sm p-8 text-center">无 ETF 数据</div>;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <table className="w-full text-xs min-w-[820px]">
        <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
          <tr>
            {["代码","名称","现价","涨跌","涨跌幅","振幅","换手率","IOPV","折溢价","成交量","份额(亿)","份额趋势"].map(h =>
              <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {codes.map(code => {
            const rt = realtime[code] ?? {};
            const ts = shares[code] ?? [];
            const pct = rt.pct_chg ?? 0;
            const vals = ts.map(r => r.shares);
            const last = ts[ts.length - 1], first = ts[0];
            const color = last && first && last.shares >= first.shares ? "#ef4444" : "#22c55e";
            return (
              <tr key={code} className="border-b border-white/[0.03]">
                <td className="px-3 py-2 font-mono">{code}</td>
                <td className="px-3 py-2">{rt.name ?? "-"}</td>
                <td className="px-3 py-2">{fmtNum(rt.close, 3)}</td>
                <td className={`px-3 py-2 ${changeClass(rt.change ?? 0)}`}>{fmtNum(rt.change, 3)}</td>
                <td className={`px-3 py-2 ${pct > 0 ? "text-up" : pct < 0 ? "text-down" : "text-ink-mute"}`}>{pct > 0 ? "+" : ""}{fmtNum(pct, 2)}%</td>
                <td className="px-3 py-2">{fmtNum(rt.amplitude, 2)}%</td>
                <td className="px-3 py-2">{fmtNum(rt.turnover, 2)}%</td>
                <td className="px-3 py-2">{fmtNum(rt.iopv, 3)}</td>
                <td className="px-3 py-2">{fmtNum(rt.discount, 2)}%</td>
                <td className="px-3 py-2">{fmtVol(rt.volume)}</td>
                <td className="px-3 py-2">{fmtShares(rt.shares)}</td>
                <td className="px-3 py-2 w-[140px]"><MiniSpark values={vals} color={color} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MiniSpark({ values, color }: { values: number[]; color: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !values.length) return;
    const inst = echarts.init(el, null, { width: 140, height: 32, renderer: "canvas" });
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
  return <div ref={ref} className="w-full h-8" />;
}
