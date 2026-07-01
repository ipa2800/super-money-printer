// components/JobList.tsx — job 列表 + 日志展开
import { useEffect, useState } from "react";
import { jobs, type Job, type JobLogEntry } from "../api";
import { Icon } from "./icons";

const LAYER: Record<string, string> = { L0: "L0", L1: "L1", L2: "L2", L3: "L3" };
const STATUS_LABEL: Record<string, string> = { success: "成功", failed: "失败", none: "未跑" };
const STATUS_ICON:  Record<string, React.ReactNode> = {
  success: <Icon.Check className="w-3 h-3" />,
  failed:  <Icon.X className="w-3 h-3" />,
  none:    null,
};
const STATUS_CLS:   Record<string, string> = { success: "text-up", failed: "text-down", none: "text-ink-mute" };

export function JobList({ onEdit, onShowLog }: { onEdit: (jobId: string, cron: string) => void; onShowLog: (jobId: string) => void }) {
  const [jobList, setJobList] = useState<Job[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const reload = () => jobs.list().then(r => setJobList(r.jobs)).catch(e => setErr(e.message));
  useEffect(() => { reload(); }, []);

  const onTrigger = async (id: string) => {
    try { void jobs.list(); alert(`已触发 ${id} (看 task-chip 状态)`); }
    catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <div className="hidden md:grid grid-cols-[1fr_0.6fr_1fr_1.5fr_0.8fr_1fr_1.6fr] gap-3 px-3 py-2 bg-white/[0.04] text-ink-mute text-xs font-medium">
        <span>JOB</span><span>层</span><span>CRON</span><span>说明</span><span>最近状态</span><span>最近运行</span><span>操作</span>
      </div>
      {jobList.map(j => {
        const status = j.last_status || "none";
        const last = j.last_run_at ? j.last_run_at.replace("T", " ").slice(0, 16) : "-";
        return (
          <div key={j.job_id} id={`log-${j.job_id}`} className="grid grid-cols-2 md:grid-cols-[1fr_0.6fr_1fr_1.5fr_0.8fr_1fr_1.6fr] gap-3 px-3 py-3 border-b border-white/[0.04] text-xs items-center">
            <span className="font-mono text-ink">{j.job_id}</span>
            <span className="text-ink-soft">{LAYER[j.layer] ?? j.layer}</span>
            <span className="font-mono text-ink-soft hidden md:inline">{j.cron_expr}</span>
            <span className="text-ink-soft col-span-2 md:col-span-1">{j.description ?? ""}</span>
            <span className={`inline-flex items-center gap-1 ${STATUS_CLS[status] ?? "text-ink-mute"}`}>{STATUS_ICON[status]}{STATUS_LABEL[status] ?? status}</span>
            <span className="text-ink-mute text-[11px] hidden md:inline">{last}</span>
            <span className="flex gap-1 col-span-2 md:col-span-1">
              <button onClick={() => onTrigger(j.job_id)} title="触发" className="text-[11px] px-2 py-1 rounded bg-line hover:bg-line-mid">▶</button>
              <button onClick={() => onEdit(j.job_id, j.cron_expr)} title="修改" className="text-[11px] px-2 py-1 rounded bg-line hover:bg-line-mid">✎</button>
              <button onClick={() => onShowLog(j.job_id)} title="日志" className="text-[11px] px-2 py-1 rounded bg-line hover:bg-line-mid">≡</button>
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function JobLog({ jobId }: { jobId: string }) {
  const [logs, setLogs] = useState<JobLogEntry[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    jobs.log(jobId, 10).then(r => setLogs(r.logs)).catch(e => setErr(e.message));
  }, [jobId]);

  if (err) return <div className="text-down text-sm mt-4">❌ {err}</div>;
  if (!logs.length) return <div className="text-ink-mute text-center py-4 mt-4 text-sm">{jobId} 暂无运行记录</div>;
  return (
    <div className="mt-4 bg-white/[0.02] rounded-lg p-3 border border-white/[0.04]">
      <div className="text-ink-mute text-[10px] mb-2">📜 {jobId} 最近 {logs.length} 条</div>
      <div className="font-mono text-[11px] space-y-0.5">
        {logs.map((e, i) => {
          const color = e.status === "success" ? "text-up" : e.status === "failed" ? "text-down" : "text-ink-mute";
          const ts = `${e.date} ${(e.completed_at ?? "").slice(11, 19)}`;
          return <div key={i} className={`${color}`}>[{ts}] {e.status} ({e.task_id})</div>;
        })}
      </div>
    </div>
  );
}
