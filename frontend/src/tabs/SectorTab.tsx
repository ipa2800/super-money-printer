// tabs/SectorTab.tsx — 板块/概念 (行业 + 概念) 历史走势
// 顶部搜索/筛选表 (合并显示), 选中后下方图表 (归一化/原始/K线 三档切换)
import { useEffect, useState, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { sector, type SectorItem, type SectorHistoryRow } from "../api";
import { useStore, store } from "../store";
import { Icon } from "../components/icons";
import { fmtNum } from "../utils/format";
import { SectorRankTable } from "../components/SectorRankTable";
import { SectorAnalyticsCharts } from "../components/SectorAnalyticsCharts";
import { SectorHeatmap } from "../components/SectorHeatmap";
import { SectorMatrixTimeline } from "../components/SectorMatrixTimeline";
import { SectorDataStatus } from "../components/SectorDataStatus";

type ChartMode = "normalized" | "raw" | "kline";
type TypeFilter = "all" | "industry" | "concept";

const DAYS_OPTIONS = [
  { v: 7,    l: "一周" },
  { v: 30,   l: "一月" },
  { v: 90,   l: "三月" },
  { v: 180,  l: "半年" },
  { v: 365,  l: "一年" },
  { v: 730,  l: "两年" },
];

export function SectorTab() {
  const days = useStore(s => s.currentDays);
  const agg = useStore(s => s.currentAgg);
  const [items, setItems] = useState<SectorItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<TypeFilter>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);  // 'industry:BK0473'
  const [history, setHistory] = useState<SectorHistoryRow[]>([]);
  const [histLoading, setHistLoading] = useState(false);
  const [histErr, setHistErr] = useState<string | null>(null);
  const [mode, setMode] = useState<ChartMode>("normalized");

  // ── 拉快照 (启动时一次, 不自动刷新) ──
  useEffect(() => {
    sector.snapshot().then(r => setItems(r.items)).catch(e => setErr(e.message));
  }, []);

  // ── 选中板块 → 拉历史 ──
  useEffect(() => {
    if (!selected) { setHistory([]); return; }
    setHistLoading(true);
    setHistErr(null);
    sector.history(selected, days, agg)
      .then(r => setHistory(r.rows))
      .catch(e => setHistErr(e.message))
      .finally(() => setHistLoading(false));
  }, [selected, days, agg]);

  // ── 过滤 + 搜索 ──
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter(it => {
      if (filterType !== "all" && it.type !== filterType) return false;
      if (!q) return true;
      return it.name.toLowerCase().includes(q) || it.code.toLowerCase().includes(q)
          || (it.leader?.toLowerCase().includes(q) ?? false);
    });
  }, [items, filterType, search]);

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;

  const selectedItem = items.find(i => selected === `${i.type}:${i.code}`);

  return (
    <div className="space-y-3">
      {/* ── 数据状态条 (snapshot 时间 + analytics 日期) ── */}
      <SectorDataStatus />

      {/* ── 轮动矩阵时序 (2×4 mini scatter, 看 8 天象限漂移) ── */}
      <SectorMatrixTimeline />

      {/* ── 板块分析热力图 (top 30 一图看完多维度强弱) ── */}
      <SectorHeatmap topN={30} />

      {/* ── 板块分析排名表 (4 维度) ── */}
      <SectorRankTable onSelect={setSelected} />

      {/* ── 轮动矩阵 + 雷达 (选中板块联动雷达) ── */}
      <SectorAnalyticsCharts selected={selected} />

      {/* ── 顶部 bar: 标题 + 类型切换 + 搜索 + 汇总 ── */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-ink font-medium">板块/概念</span>
        <span className="text-ink-mute text-xs">{items.length} 个</span>
        {/* 类型切换 */}
        <div className="flex gap-0.5 ml-2 text-xs">
          {([["all","全部"],["industry","行业"],["concept","概念"]] as [TypeFilter,string][]).map(([k,l]) => (
            <button key={k} onClick={() => setFilterType(k)}
              className={`px-2.5 py-1 rounded ${filterType===k ? "bg-pos text-white" : "bg-line text-ink-soft hover:bg-line-mid"}`}>
              {l}
            </button>
          ))}
        </div>
        {/* 搜索 */}
        <div className="ml-auto flex items-center gap-2">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索名称/代码/领涨股"
            className="w-56 px-2.5 py-1 rounded bg-line border border-line-mid text-xs text-ink placeholder-ink-mute focus:outline-none focus:border-pos"
          />
        </div>
      </div>

      {/* ── 板块列表 (桌面表格) ── */}
      <div className="hidden md:block bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto max-h-[420px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-card-grad/95 backdrop-blur text-ink-mute text-[10px] uppercase">
            <tr>
              {["类型","代码","名称","最新价","涨跌幅","涨跌额","换手率","领涨股","领涨%","上涨/下跌"].map(h =>
                <th key={h} className={`px-3 py-2 text-left font-medium whitespace-nowrap ${["最新价","涨跌幅","涨跌额","换手率","领涨%","上涨/下跌"].includes(h) ? "text-right" : ""}`}>{h}</th>
              )}
            </tr>
          </thead>
          <tbody>
            {filtered.map(it => {
              const sym = `${it.type}:${it.code}`;
              const isSel = sym === selected;
              const pct = it.pct_chg ?? 0;
              const cls = pct > 0 ? "text-pos" : pct < 0 ? "text-neg" : "text-ink-mute";
              return (
                <tr key={sym} onClick={() => setSelected(sym)}
                  className={`border-b border-white/[0.03] cursor-pointer hover:bg-white/[0.04] ${isSel ? "bg-white/[0.06]" : ""}`}>
                  <td className="px-3 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${it.type === "industry" ? "bg-blue-500/20 text-blue-300" : "bg-purple-500/20 text-purple-300"}`}>
                      {it.type === "industry" ? "行业" : "概念"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-ink-dim">{it.code}</td>
                  <td className="px-3 py-2 text-ink">{it.name}</td>
                  <td className={`px-3 py-2 text-right tabular-nums font-semibold ${cls}`}>{fmtNum(it.price, 2)}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${cls}`}>{pct > 0 ? "+" : ""}{fmtNum(pct, 2)}%</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${cls}`}>{fmtNum(it.change, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-soft">{fmtNum(it.turnover, 2)}%</td>
                  <td className="px-3 py-2 text-ink-soft">{it.leader ?? "-"}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${(it.leader_pct ?? 0) >= 0 ? "text-pos" : "text-neg"}`}>
                    {it.leader_pct != null ? (it.leader_pct > 0 ? "+" : "") + fmtNum(it.leader_pct, 2) + "%" : "-"}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-xs">
                    <span className="text-pos">{it.up_count ?? "-"}</span>
                    <span className="text-ink-mute mx-1">/</span>
                    <span className="text-neg">{it.down_count ?? "-"}</span>
                  </td>
                </tr>
              );
            })}
            {!filtered.length && (
              <tr><td colSpan={10} className="text-center text-ink-mute py-8">无匹配板块</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 移动卡片 */}
      <div className="grid md:hidden grid-cols-1 gap-2">
        {filtered.map(it => {
          const sym = `${it.type}:${it.code}`;
          const pct = it.pct_chg ?? 0;
          const cls = pct > 0 ? "text-pos" : pct < 0 ? "text-neg" : "text-ink-mute";
          return (
            <button key={sym} onClick={() => setSelected(sym)} className="bg-card-grad border border-white/[0.06] rounded-xl p-3 text-left">
              <div className="flex items-baseline justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${it.type === "industry" ? "bg-blue-500/20 text-blue-300" : "bg-purple-500/20 text-purple-300"}`}>
                      {it.type === "industry" ? "行业" : "概念"}
                    </span>
                    <span className="font-medium text-sm">{it.name}</span>
                  </div>
                  <div className="text-ink-dim text-[11px] mt-1 font-mono">{it.code} · 领涨 {it.leader ?? "-"}</div>
                </div>
                <div className="text-right shrink-0 ml-3">
                  <div className={`text-base font-semibold tabular-nums ${cls}`}>{fmtNum(it.price, 2)}</div>
                  <div className={`text-xs tabular-nums ${cls}`}>{pct > 0 ? "+" : ""}{fmtNum(pct, 2)}%</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* ── 选中板块: 时间范围 + 模式切换 + 图表 ── */}
      {selected && selectedItem && (
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3 space-y-2">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${selectedItem.type === "industry" ? "bg-blue-500/20 text-blue-300" : "bg-purple-500/20 text-purple-300"}`}>
              {selectedItem.type === "industry" ? "行业" : "概念"}
            </span>
            <span className="font-medium">{selectedItem.name}</span>
            <span className="font-mono text-xs text-ink-dim">{selectedItem.code}</span>
            <div className="ml-auto flex gap-2 items-center">
              {/* 时间范围 */}
              <div className="flex gap-0.5 text-xs">
                {DAYS_OPTIONS.map(o => (
                  <button key={o.v} onClick={() => store.set({ currentDays: o.v })}
                    className={`px-2 py-1 rounded ${days===o.v ? "bg-pos text-white" : "bg-line text-ink-soft hover:bg-line-mid"}`}>
                    {o.l}
                  </button>
                ))}
              </div>
              {/* 模式切换 */}
              <div className="flex gap-0.5 text-xs ml-2">
                {([["normalized","归一化"],["raw","原始"],["kline","K线"]] as [ChartMode,string][]).map(([k,l]) => (
                  <button key={k} onClick={() => setMode(k)}
                    className={`px-2 py-1 rounded ${mode===k ? "bg-pos text-white" : "bg-line text-ink-soft hover:bg-line-mid"}`}>
                    {l}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {histErr && <div className="text-down text-xs">{histErr}</div>}
          {histLoading && <div className="text-ink-mute text-xs py-8 text-center">加载历史数据…</div>}
          {!histLoading && !histErr && history.length > 0 && (
            <SectorChart rows={history} mode={mode} />
          )}
          {!histLoading && !histErr && history.length === 0 && (
            <div className="text-ink-mute text-xs py-8 text-center">无历史数据 (l4_sector 隔夜跑)</div>
          )}
        </div>
      )}

      {!selected && !err && (
        <div className="text-ink-mute text-xs text-center py-6">↑ 选择上方任一板块/概念查看历史走势</div>
      )}
    </div>
  );
}

// ── 图: 归一化/原始/K 线 ──
// ponytail: 归一化 = 起点 100 (所有 close / first_close * 100); 原始 = close 折线; K 线 = OHLC 蜡烛
function SectorChart({ rows, mode }: { rows: SectorHistoryRow[]; mode: ChartMode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const inst = echarts.init(ref.current);
    const dates = rows.map(r => r.date);
    const closes = rows.map(r => r.close);
    const first = closes[0] ?? 1;
    const normalized = closes.map(c => (c / first) * 100);

    const option: echarts.EChartsCoreOption = {
      backgroundColor: "transparent",
      animation: false,
      grid: { top: 24, right: 56, bottom: 36, left: 60 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1e293b",
        borderColor: "#334155",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        axisPointer: { type: "cross", lineStyle: { color: "#475569" } },
      },
      xAxis: {
        type: "category", data: dates, boundaryGap: mode === "kline",
        axisLabel: { color: "#64748b", fontSize: 10 },
        axisLine: { lineStyle: { color: "#334155" } },
      },
      yAxis: {
        scale: true,
        axisLabel: { color: "#64748b", fontSize: 10 },
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
      },
      series: [],
    };
    if (mode === "kline") {
      // 蜡烛图: 用 echarts candlestick 数据格式 [open, close, low, high]
      const candle = rows.map(r => [r.open, r.close, r.low, r.high]);
      option.series = [{
        type: "candlestick",
        data: candle,
        itemStyle: {
          color:        "#ef4444",  // 红涨
          color0:       "#22c55e",  // 绿跌
          borderColor:  "#ef4444",
          borderColor0: "#22c55e",
        },
      }];
    } else if (mode === "raw") {
      option.series = [{
        type: "line",
        data: closes,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: "#3b82f6", width: 1.5 },
        areaStyle: { color: "rgba(59,130,246,0.1)" },
      }];
    } else {
      // 归一化
      option.series = [{
        type: "line",
        data: normalized,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: "#22c55e", width: 1.5 },
        areaStyle: { color: "rgba(34,197,94,0.1)" },
        markLine: {
          silent: true, symbol: "none",
          data: [{ yAxis: 100, lineStyle: { color: "#475569", type: "dashed" } }],
        },
      }];
    }
    inst.setOption(option);
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); inst.dispose(); };
  }, [rows, mode]);
  return <div ref={ref} className="w-full h-72 md:h-80" />;
}

// ponytail: 时间范围/聚合粒度跟其他 tab 共享 store (Topbar/自定义范围都改这里)