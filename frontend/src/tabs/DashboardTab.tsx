// tabs/DashboardTab.tsx — 主页: 告警 banner + 宏观指标 + 指数 K线 + ETF 实时 + 最近运行
import { useEffect, useState } from "react";
import { alerts, jobs, type AlertSummary } from "../api";
import { MacroGrid } from "../components/MacroGrid";
import { KLineChart } from "../components/KLineChart";
import { ETFTable } from "../components/ETFTable";
import { AlertPanel } from "../components/AlertPanel";

export function DashboardTab() {
  const [symbol, setSymbol] = useState("sh.000300");
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null);
  useEffect(() => { alerts.summary(3).then(setAlertSummary).catch(() => setAlertSummary(null)); }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-ink-soft text-xs">指数:</label>
        <select value={symbol} onChange={e => setSymbol(e.target.value)} className="bg-line border border-line-mid rounded text-sm px-2 py-1">
          {[["sh.000300","沪深300"],["sh.000905","中证500"],["sh.000016","上证50"],["sz.399006","创业板指"],["sh.000688","科创50"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <AlertPanel summary={alertSummary} />
      <Section title="宏观指标"><MacroGrid /></Section>
      <Section title="指数走势"><div className="bg-card-grad border border-white/[0.06] rounded-xl p-4"><KLineChart symbol={symbol} freq="d" /></div></Section>
      <Section title="ETF 实时"><ETFTable /></Section>
      <Section title="最近运行"><RecentRuns /></Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-wider text-ink-mute font-medium mb-3">{title}</h3>
      {children}
    </section>
  );
}

function RecentRuns() {
  const [rows, setRows] = useState<{ job_id: string; last_status: string; last_run_at: string | null }[]>([]);
  useEffect(() => {
    jobs.list().then(r => setRows(r.jobs.map(j => ({ job_id: j.job_id, last_status: j.last_status ?? "none", last_run_at: j.last_run_at ?? null }))));
  }, []);
  if (!rows.length) return <div className="text-ink-mute text-sm p-6 text-center">暂无运行记录</div>;
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <table className="w-full text-xs min-w-[400px]">
        <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
          <tr>{["JOB","状态","最近运行"].map(h => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.job_id} className="border-b border-white/[0.03]">
              <td className="px-3 py-2"><code>{r.job_id}</code></td>
              <td className={`px-3 py-2 ${r.last_status === "success" ? "text-up" : r.last_status === "failed" ? "text-down" : "text-ink-mute"}`}>{r.last_status === "success" ? "✓ 成功" : r.last_status === "failed" ? "✗ 失败" : "—"}</td>
              <td className="px-3 py-2 text-ink-soft text-[11px]">{r.last_run_at ? r.last_run_at.replace("T", " ").slice(0, 16) : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
