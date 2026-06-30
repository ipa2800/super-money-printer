// components/StockDetail.tsx — 自选股详情 (分时/K线/资金流/新闻 四 tab)
import { useEffect, useState } from "react";
import { stock, type KLineRow, type MinuteBar, type StockRealtime } from "../api";
import { KLineChart } from "./KLineChart";
import { MinuteChart } from "./MinuteChart";

type FlowRow = { date: string; main_net: number; super_net: number; big_net: number; mid_net: number; small_net: number };
type News = { title: string; url: string; time?: string; source?: string };

export function StockDetail({ code, realtime, onClose }: { code: string; realtime?: StockRealtime; onClose: () => void }) {
  const [kline, setKline] = useState<KLineRow[]>([]);
  const [freq, setFreq] = useState("d");
  const [minute, setMinute] = useState<MinuteBar[]>([]);
  const [flow, setFlow] = useState<FlowRow[]>([]);
  const [news, setNews] = useState<News[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<"minute" | "kline" | "flow" | "news">("minute");

  // 实时报价: 父组件已传入 realtime
  const rt = realtime;
  const price = rt?.price;
  const change = rt?.change;
  const changePct = rt?.change_pct;
  const up = (changePct ?? 0) >= 0;
  const colorCls = rt ? (up ? "text-up" : "text-down") : "text-ink";

  useEffect(() => {
    setErr(null);
    setMinute([]);
    stock.minute(code).then(r => setMinute(r.data)).catch(() => setMinute([]));
  }, [code]);

  useEffect(() => {
    setKline([]);
    stock.kline(code, freq).then(r => setKline(r.data)).catch(e => setErr(e.message));
  }, [code, freq]);

  useEffect(() => {
    setFlow([]);
    stock.fundFlow(code).then(r => setFlow(r.rows as unknown as FlowRow[])).catch(() => setFlow([]));
    stock.news(code).then(r => setNews(r.news as unknown as News[])).catch(() => setNews([]));
  }, [code]);

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[720px] bg-bg-soft border-l border-white/[0.05] overflow-y-auto z-50 p-6 animate-slidein">
      <button onClick={onClose} className="absolute top-3 right-4 text-2xl text-ink-soft hover:text-ink">×</button>

      {/* 头部: 名称 + 价格 + 涨幅 (主流股票软件) */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2">
          <h3 className="text-base font-semibold">{rt?.name ?? code}</h3>
          <span className="text-ink-mute text-xs font-mono">{code}</span>
        </div>
        {rt ? (
          <div className="mt-2 flex items-baseline gap-4">
            <span className={`text-3xl font-semibold tabular-nums ${colorCls}`}>{price?.toFixed(2)}</span>
            <span className={`text-sm tabular-nums ${colorCls}`}>
              {change !== undefined && (change >= 0 ? "+" : "")}{change?.toFixed(2)}
            </span>
            <span className={`text-sm tabular-nums ${colorCls}`}>
              {changePct !== undefined && (changePct >= 0 ? "+" : "")}{changePct?.toFixed(2)}%
            </span>
          </div>
        ) : (
          <div className="text-ink-mute text-sm mt-2">实时报价加载中…</div>
        )}
      </div>

      {err && <div className="text-down text-sm mb-3">⚠ {err}</div>}

      {/* 关键数据网格 (主流软件布局) */}
      {rt && (
        <div className="grid grid-cols-4 gap-3 mb-4 text-xs">
          <KV label="今开" v={rt.open.toFixed(2)} colorCls={rt.open >= rt.prev_close ? "text-up" : "text-down"} />
          <KV label="昨收" v={rt.prev_close.toFixed(2)} colorCls="" />
          <KV label="最高" v={rt.high.toFixed(2)} colorCls="text-up" />
          <KV label="最低" v={rt.low.toFixed(2)} colorCls="text-down" />
          <KV label="成交量" v={fmtVol(rt.volume)} colorCls="" />
          <KV label="成交额" v={fmtVol(rt.amount)} colorCls="" />
          <KV label="涨跌额" v={(rt.change >= 0 ? "+" : "") + rt.change.toFixed(2)} colorCls={colorCls} />
          <KV label="涨跌幅" v={(rt.change_pct >= 0 ? "+" : "") + rt.change_pct.toFixed(2) + "%"} colorCls={colorCls} />
        </div>
      )}

      {/* Tab 切换 */}
      <div className="flex flex-wrap gap-2 mb-3 items-center border-b border-line">
        {(["minute","kline","flow","news"] as const).map(k => (
          <button key={k} onClick={() => setTab(k)} className={`text-xs px-4 py-2 -mb-px border-b-2 ${tab === k ? "border-accent text-accent" : "border-transparent text-ink-soft hover:text-ink"}`}>
            {k === "minute" ? "分时" : k === "kline" ? "K线" : k === "flow" ? "资金流" : "新闻"}
          </button>
        ))}
        {tab === "kline" && (
          <select value={freq} onChange={e => setFreq(e.target.value)} className="ml-auto bg-bg border border-line-mid rounded text-xs px-2 py-1">
            <option value="d">日</option><option value="w">周</option><option value="m">月</option>
          </select>
        )}
      </div>

      {/* Tab 内容 */}
      {tab === "minute" && (
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          {minute.length === 0 ? <div className="text-ink-mute text-center py-6">暂无分时数据 (非交易时段)</div> : <MinuteChart data={minute} />}
        </div>
      )}

      {tab === "kline" && (
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          <KLineChart symbol={code} freq={freq} data={kline} />
        </div>
      )}

      {tab === "flow" && (
        <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
          <table className="w-full text-xs min-w-[480px]">
            <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
              <tr>{["日期","主力净流入","超大单","大单","中单","小单"].map(h => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr>
            </thead>
            <tbody>
              {flow.length === 0 ? <tr><td colSpan={6} className="text-ink-mute text-center py-6">无资金流数据</td></tr> :
                flow.map((f, i) => (
                  <tr key={i} className="border-b border-white/[0.03]">
                    <td className="px-3 py-2">{f.date}</td>
                    <td className={`px-3 py-2 ${f.main_net >= 0 ? "text-up" : "text-down"}`}>{(f.main_net / 1e8).toFixed(2)} 亿</td>
                    <td className="px-3 py-2">{(f.super_net / 1e8).toFixed(2)} 亿</td>
                    <td className="px-3 py-2">{(f.big_net / 1e8).toFixed(2)} 亿</td>
                    <td className="px-3 py-2">{(f.mid_net / 1e8).toFixed(2)} 亿</td>
                    <td className="px-3 py-2">{(f.small_net / 1e8).toFixed(2)} 亿</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "news" && (
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
          {news.length === 0 ? <div className="text-ink-mute text-center py-6">暂无新闻</div> :
            news.map((n, i) => (
              <a key={i} href={n.url} target="_blank" rel="noreferrer" className="flex justify-between items-center py-2 border-b border-white/[0.04] text-ink-soft hover:text-accent text-sm">
                <span className="truncate">{n.title}</span>
                <span className="text-ink-mute text-[11px] ml-2 shrink-0">{n.time ?? n.source ?? ""}</span>
              </a>
            ))}
        </div>
      )}
    </div>
  );
}

function KV({ label, v, colorCls }: { label: string; v: string; colorCls: string }) {
  return (
    <div>
      <div className="text-ink-mute text-[11px]">{label}</div>
      <div className={`mt-1 tabular-nums ${colorCls || "text-ink"}`}>{v}</div>
    </div>
  );
}

function fmtVol(v: number): string {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}