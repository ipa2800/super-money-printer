// tabs/StocksTab.tsx — 自选股列表 (主流股票软件风格: 代码/名称/最新价/涨跌幅)
import { useEffect, useState, useCallback } from "react";
import { stock, type StockItem, type StockRealtime, type StockSearchResult } from "../api";
import { StockDetail } from "../components/StockDetail";
import { Icon } from "../components/icons";
import { useAutoRefresh } from "../hooks/useAutoRefresh";

export function StocksTab() {
  const [items, setItems] = useState<StockItem[]>([]);
  const [realtime, setRealtime] = useState<Record<string, StockRealtime>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [asOf, setAsOf] = useState<string>("");
  const [adding, setAdding] = useState(false);

  const reloadList = () =>
    stock.list().then(r => setItems(r.stocks)).catch(e => setErr(e.message));

  // silent=true: 自动刷新, 不切换 refreshing 状态 (避免按钮/UI 抖动)
  const reloadRealtime = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    try {
      const r = await stock.realtime();
      setRealtime(r.items);
      setAsOf(r.as_of);
    } catch (e) {
      // 实时报价失败不影响列表
      console.warn("realtime fetch failed", e);
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, []);

  useEffect(() => { reloadList(); }, []);
  // 静默自动刷新: 交易时段 5s / 收盘前 30 分钟 3s, 切 tab 即停
  useAutoRefresh(() => reloadRealtime(true), [reloadRealtime]);

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;
  if (!items.length && !adding) {
    return (
      <>
        <div className="text-ink-mute text-center py-12">
          <div className="mb-3">尚未添加自选股</div>
          <button
            onClick={() => setAdding(true)}
            className="text-sm px-4 py-2 rounded-lg bg-pos hover:opacity-90 text-white inline-flex items-center gap-1.5"
          >
            <Icon.Plus className="w-4 h-4" />添加第一只
          </button>
        </div>
        {adding && <AddStockPanel existing={items.map(i => i.code)} onClose={() => setAdding(false)} onAdded={() => { reloadList(); reloadRealtime(); }} />}
      </>
    );
  }

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
            onClick={() => setAdding(true)}
            className="text-xs px-3 py-1.5 rounded bg-line hover:bg-line-mid inline-flex items-center gap-1.5"
          >
            <Icon.Plus className="w-3.5 h-3.5" />添加
          </button>
          <button
            onClick={() => reloadRealtime()}
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
              {["代码","名称","最新价","涨跌幅","高","低","开盘","昨收","成交量","操作"].map(h =>
                <th key={h} className={`px-3 py-2 ${["最新价","涨跌幅","高","低","开盘","昨收","成交量"].includes(h) ? "text-right" : "text-left"}`}>{h}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map(s => {
              const rt = realtime[s.code];
              const up = rt && rt.change_pct >= 0;
              const cls = rt ? (up ? "text-pos" : "text-neg") : "text-ink-mute";
              return (
                <tr key={s.code} onClick={() => setSelected(s.code)} className="border-b border-white/[0.03] cursor-pointer hover:bg-white/[0.03]">
                  <td className="px-3 py-2 font-mono">{s.code}</td>
                  <td className="px-3 py-2">{s.name ?? "-"}</td>
                  <td className={`px-3 py-2 text-right font-semibold tabular-nums ${cls}`}>{rt ? rt.price.toFixed(2) : "—"}</td>
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
          const cls = rt ? (up ? "text-pos" : "text-neg") : "text-ink-mute";
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
      {adding && (
        <AddStockPanel
          existing={items.map(i => i.code)}
          onClose={() => setAdding(false)}
          onAdded={() => { reloadList(); reloadRealtime(); }}
        />
      )}
    </>
  );
}

// 添加自选股: 搜索 → 点击添加 (同主流股票软件)
function AddStockPanel({ existing, onClose, onAdded }: {
  existing: string[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [adding, setAdding] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // ponytail: 300ms 防抖, 简单 setTimeout 而非 lodash
  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    const id = setTimeout(() => {
      stock.search(q.trim())
        .then(r => setResults(r.results))
        .catch(e => setErr(e.message));
    }, 300);
    return () => clearTimeout(id);
  }, [q]);

  const handleAdd = async (r: StockSearchResult) => {
    setAdding(r.code);
    setErr(null);
    try {
      await stock.add(r.code, r.name);
      onAdded();
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAdding(null);
    }
  };

  const exSet = new Set(existing);
  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-40" onClick={onClose} />
      <div className="fixed inset-x-0 top-12 md:inset-auto md:left-1/2 md:top-1/3 md:-translate-x-1/2 md:-translate-y-1/2 z-50
                      md:w-[420px] bg-card-grad border border-white/[0.08] rounded-xl shadow-2xl p-4 mx-4 md:mx-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">添加自选股</h3>
          <button onClick={onClose} className="text-ink-mute hover:text-ink"><Icon.X className="w-4 h-4" /></button>
        </div>
        <input
          autoFocus
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="输入代码或名称 (例: 000001 或 平安银行)"
          className="w-full px-3 py-2 rounded-lg bg-line border border-line-mid text-sm text-ink placeholder-ink-mute focus:outline-none focus:border-pos"
        />
        {err && <div className="text-down text-xs mt-2">{err}</div>}
        <div className="mt-2 max-h-80 overflow-y-auto">
          {!q.trim() && <div className="text-ink-mute text-xs px-2 py-6 text-center">输入关键词开始搜索</div>}
          {q.trim() && !results.length && <div className="text-ink-mute text-xs px-2 py-6 text-center">无匹配结果</div>}
          {results.map(r => {
            const added = exSet.has(r.code);
            const busy = adding === r.code;
            return (
              <button
                key={r.code}
                onClick={() => !added && !busy && handleAdd(r)}
                disabled={added || busy}
                className="w-full flex items-center justify-between px-3 py-2 rounded hover:bg-white/[0.04] disabled:opacity-50 disabled:hover:bg-transparent text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-sm text-ink">{r.code}</div>
                  <div className="text-xs text-ink-soft truncate">{r.name}</div>
                </div>
                <span className="text-xs shrink-0 ml-2">
                  {added ? <span className="text-ink-mute">已添加</span>
                    : busy ? <span className="text-warn">添加中…</span>
                    : <span className="text-pos">+ 添加</span>}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

function fmtVol(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}