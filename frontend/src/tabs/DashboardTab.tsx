// tabs/DashboardTab.tsx — 主页: 市场总览 + 告警 + 宏观 + 指数 K线 + ETF 实时 + 最近运行
import { useEffect, useState, type ReactNode } from "react";
import { useStore } from "../store";
import { alerts, etf, jobs, type AlertSummary } from "../api";
import { MacroGrid } from "../components/MacroGrid";
import { KLineChart } from "../components/KLineChart";
import { ETFTable } from "../components/ETFTable";
import { AlertPanel } from "../components/AlertPanel";
import { Icon } from "../components/icons";
import { fmtAmt } from "../utils/format";

const SYMBOLS: [string, string][] = [
  ["sh.000300", "沪深300"], ["sh.000905", "中证500"], ["sh.000016", "上证50"],
  ["sz.399006", "创业板指"], ["sh.000688", "科创50"],
];

export function DashboardTab() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [symbol, setSymbol] = useState("sh.000300");
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null);

  useEffect(() => {
    alerts.summary(3).then(setAlertSummary).catch(() => setAlertSummary(null));
  }, [refreshKey]);

  const ackAlert = (id: number) =>
    alerts.ack(id).then(() => alerts.summary(3).then(setAlertSummary).catch(() => {}));

  return (
    <div className="space-y-6">
      <MarketOverview refreshKey={refreshKey} />

      <div className="flex items-stretch gap-2">
        <div className="flex-1 min-w-0">
          <AlertPanel summary={alertSummary} onAck={ackAlert} />
        </div>
        <button
          onClick={() => setRefreshKey(k => k + 1)}
          className="shrink-0 text-xs px-3 py-2 rounded-lg bg-line hover:bg-line-mid border border-line-mid text-ink-soft inline-flex items-center gap-1.5"
        >
          <Icon.Refresh className="w-3.5 h-3.5" />
          全部刷新
        </button>
      </div>

      <Section title="宏观指标"><MacroGrid refreshKey={refreshKey} /></Section>

      <Section
        title={
          <div className="flex items-center gap-3">
            <span>指数走势</span>
            <select
              value={symbol}
              onChange={e => setSymbol(e.target.value)}
              className="bg-line border border-line-mid rounded text-[11px] px-2 py-0.5 text-ink"
            >
              {SYMBOLS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        }
      >
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          <KLineChart symbol={symbol} freq="d" refreshKey={refreshKey} />
        </div>
      </Section>

      <Section title="ETF 实时"><ETFTable refreshKey={refreshKey} /></Section>

      <Section title="最近运行"><RecentRuns refreshKey={refreshKey} /></Section>
    </div>
  );
}

function Section({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-wider text-ink-mute font-medium mb-3">{title}</h3>
      {children}
    </section>
  );
}

function MarketOverview({ refreshKey }: { refreshKey: number }) {
  const days = useStore(s => s.currentDays);
  const [m, setM] = useState<{ ups: number; dns: number; flats: number; total: number } | null>(null);
  useEffect(() => {
    etf.overview(days).then(r => {
      const rts = r.codes.map(c => r.realtime[c] ?? {});
      const ups = rts.filter(x => (x.pct_chg ?? 0) > 0).length;
      const dns = rts.filter(x => (x.pct_chg ?? 0) < 0).length;
      const flats = rts.length - ups - dns;
      const total = rts.reduce((s, x) => s + (x.amount ?? 0), 0);
      setM({ ups, dns, flats, total });
    }).catch(() => {});
  }, [days, refreshKey]);
  if (!m) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Tile label="上涨" value={m.ups} cls="text-pos" />
      <Tile label="下跌" value={m.dns} cls="text-neg" />
      <Tile label="平盘" value={m.flats} cls="text-ink-mute" />
      <Tile label="总成交额" value={fmtAmt(m.total)} mono />
    </div>
  );
}

function Tile({ label, value, cls, mono }: { label: string; value: number | string; cls?: string; mono?: boolean }) {
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3 text-center">
      <div className="text-[11px] text-ink-mute">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${cls ?? ""} ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function RecentRuns({ refreshKey }: { refreshKey: number }) {
  const [rows, setRows] = useState<{ job_id: string; last_status: string; last_run_at: string | null }[]>([]);
  useEffect(() => {
    jobs.list().then(r => setRows(r.jobs.map(j => ({
      job_id: j.job_id, last_status: j.last_status ?? "none", last_run_at: j.last_run_at ?? null,
    })))).catch(() => setRows([]));
  }, [refreshKey]);
  if (!rows.length) return <div className="text-ink-mute text-sm p-6 text-center">暂无运行记录</div>;
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <table className="w-full text-xs min-w-[400px]">
        <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
          <tr>{["JOB", "状态", "最近运行"].map(h => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.job_id} className="border-b border-white/[0.03]">
              <td className="px-3 py-2"><code>{r.job_id}</code></td>
              <td className={`px-3 py-2 ${r.last_status === "success" ? "text-up" : r.last_status === "failed" ? "text-down" : "text-ink-mute"}`}>
                {r.last_status === "success" ? (
                  <span className="inline-flex items-center gap-1"><Icon.Check className="w-3 h-3" />成功</span>
                ) : r.last_status === "failed" ? (
                  <span className="inline-flex items-center gap-1"><Icon.X className="w-3 h-3" />失败</span>
                ) : "—"}
              </td>
              <td className="px-3 py-2 text-ink-soft text-[11px]">{r.last_run_at ? r.last_run_at.replace("T", " ").slice(0, 16) : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
