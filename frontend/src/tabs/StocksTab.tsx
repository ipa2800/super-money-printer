// tabs/StocksTab.tsx — 自选股列表 (主流股票软件风格: 代码/名称/最新价/涨跌幅/涨跌额)
import { useEffect, useState, useCallback } from "react";
import { stock, type StockItem, type StockRealtime } from "../api";
import { StockDetail } from "../components/StockDetail";

export function StocksTab() {
  const [items, setItems] = useState<StockItem[]>([]);
  const [realtime, setRealtime] = useState<Record<string, StockRealtime>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [asOf, setAsOf] = useState<string>("");

  const reloadList = () =>
    stock.list().then(r => setItems(r.stocks)).catch(e => setErr(e.message));

  const reloadRealtime = useCallback(async () => {
    setRefreshing(true);
    try {
      const r = await stock.realtime();
      setRealtime(r.items);
      setAsOf(r.as_of);
    } catch (e) {
      // 实时报价失败不影响列表
      console.warn("realtime fetch failed", e);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { reloadList(); }, []);
  useEffect(() => { reloadRealtime(); }, [reloadRealtime]);

  if (err) return <div className="text-down text-sm">❌ {err}</div>;
  if (!items.length) return <div className="text-ink-mute text-center py-12">尚未添加自选股 — 在「数据管理」tab 添加</div>;

  // 排序: 涨跌幅从高到低 (主流软件风格)
  const sorted = [...items].sort((a, b) => {
    const pa = realtime[a.code]?.change_pct ?? -999;
    const pb = realtime[b.code]?.change_pct ?? -999;
    return pb - pa;
  });

  return (
    <>
      {/* 顶部 bar: 标题 + 刷新 + 时间戳 */}
      <div className="flex items-center justify-between mb-3 text-sm">
        <span className="text-ink-mute">{sorted.length} 只自选</span>
        <div className="flex items-center gap-3">
          {asOf && <span className="text-ink-dim text-xs">{asOf}</span>}
          <button
            onClick={reloadRealtime}
            disabled={refreshing}
            className="text-xs px-3 py-1.5 rounded bg-line hover:bg-line-mid disabled:opacity-50"
          >
            {refreshing ? "刷新中…" : "🔄 刷新"}
          </button>
        </div>
      </div>

      {/* 桌面表格 */}
      <div className="hidden md:block bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
            <tr>
              {["代码","名称","最新价","涨跌额","涨跌幅","高","低","开盘","昨收","成交量","操作"].map(h =>
                <th key={h} className={`px-3 py-2 ${["最新价","涨跌额","涨跌幅","高","低","开盘","昨收","成交量"].includes(h) ? "text-right" : "text-left"}`}>{h}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map(s => {
              const rt = realtime[s.code];
              const up = rt && rt.change_pct >= 0;
              const cls = rt ? (up ? "text-up" : "text-down") : "text-ink-mute";
              return (
                <tr key={s.code} onClick={() => setSelected(s.code)} className="border-b border-white/[0.03] cursor-pointer hover:bg-white/[0.03]">
                  <td className="px-3 py-2 font-mono">{s.code}</td>
                  <td className="px-3 py-2">{s.name ?? "-"}</td>
                  <td className={`px-3 py-2 text-right font-semibold tabular-nums ${cls}`}>{rt ? rt.price.toFixed(2) : "—"}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${cls}`}>{rt ? (rt.change >= 0 ? "+" : "") + rt.change.toFixed(2) : "—"}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${cls}`}>{rt ? (rt.change_pct >= 0 ? "+" : "") + rt.change_pct.toFixed(2) + "%" : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{rt ? rt.high.toFixed(2) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{rt ? rt.low.toFixed(2) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{rt ? rt.open.toFixed(2) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{rt ? rt.prev_close.toFixed(2) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{rt ? fmtVol(rt.volume) : "—"}</td>
                  <td className="px-3 py-2">
                    <button onClick={e => { e.stopPropagation(); setSelected(s.code); }} className="text-xs px-2 py-0.5 rounded bg-line hover:bg-line-mid">详情</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 移动卡片 (主流风格: 左 代码+名, 右 价+涨幅) */}
      <div className="grid md:hidden grid-cols-1 gap-2">
        {sorted.map(s => {
          const rt = realtime[s.code];
          const up = rt && rt.change_pct >= 0;
          const cls = rt ? (up ? "text-up" : "text-down") : "text-ink-mute";
          return (
            <button key={s.code} onClick={() => setSelected(s.code)} className="bg-card-grad border border-white/[0.06] rounded-xl p-4 text-left">
              <div className="flex justify-between items-start">
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-ink text-sm">{s.code}</span>
                    <span className="text-ink-soft text-sm truncate">{s.name ?? "—"}</span>
                  </div>
                  {rt && (
                    <div className="text-ink-dim text-[11px] mt-1 tabular-nums">
                      开 {rt.open.toFixed(2)} · 高 {rt.high.toFixed(2)} · 低 {rt.low.toFixed(2)} · 量 {fmtVol(rt.volume)}
                    </div>
                  )}
                </div>
                <div className="text-right shrink-0 ml-3">
                  <div className={`text-lg font-semibold tabular-nums ${cls}`}>{rt ? rt.price.toFixed(2) : "—"}</div>
                  <div className={`text-xs tabular-nums ${cls}`}>
                    {rt ? (rt.change_pct >= 0 ? "▲" : "▼") + " " + Math.abs(rt.change_pct).toFixed(2) + "%" : "—"}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <>
          <div className="fixed inset-0 bg-black/60 z-40" onClick={() => setSelected(null)} />
          <StockDetail code={selected} realtime={realtime[selected]} onClose={() => setSelected(null)} />
        </>
      )}
    </>
  );
}

function fmtVol(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}