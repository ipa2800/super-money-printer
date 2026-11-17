// components/DataLogTab.tsx — 数据日志: 可过滤表格 + 实时滚动 + 5s 自动刷新
import { useEffect, useMemo, useState } from "react";
import { dataLog, type DataLogItem } from "../api";
import { Icon } from "./icons";

type Filter = { source: string; status: string; layer: string; q: string };

const DEFAULT_FILTER: Filter = { source: "", status: "", layer: "", q: "" };

export function DataLogTab() {
  const [items, setItems] = useState<DataLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const [applied, setApplied] = useState<Filter>(DEFAULT_FILTER);  // ponytail: 真正下发到 API 的过滤
  const [auto, setAuto] = useState(true);
  const [stats, setStats] = useState<Record<string, { ok: number; fail: number; avg_ms: number }>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fetchData = async (f: Filter) => {
    try {
      const [list, st] = await Promise.all([
        dataLog.list({ source: f.source || undefined, status: f.status || undefined, layer: f.layer || undefined, q: f.q || undefined, limit: 200 }),
        dataLog.stats(24),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setStats(st.sources);
      setErr(null);
    } catch (e: any) {
      setErr(e.message ?? String(e));
    }
  };

  // 自动刷新 (5s)
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => fetchData(applied), 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auto, applied]);

  // 初次加载 + filter 变化时刷一次
  useEffect(() => { fetchData(applied); }, [applied]);

  const sources = useMemo(() => {
    // ponytail: 源下拉按 layer 过滤 — job:* 只在 job 层显, provider:* 只在 provider 层显
    const all = Object.keys(stats).sort();
    if (applied.layer === "job")      return all.filter(s => s.startsWith("job:"));
    if (applied.layer === "provider") return all.filter(s => s.startsWith("provider:"));
    return all;
  }, [stats, applied.layer]);

  const totalOk = Object.values(stats).reduce((s, v) => s + v.ok, 0);
  const totalFail = Object.values(stats).reduce((s, v) => s + v.fail, 0);
  const succRate = totalOk + totalFail > 0 ? (totalOk / (totalOk + totalFail) * 100).toFixed(1) : "—";

  const onCleanup = async () => {
    if (!confirm("删除 30 天前的所有 data_log? 不可恢复。")) return;
    setBusy(true);
    try {
      const cutoff = new Date(Date.now() - 30 * 86400_000).toISOString();
      const r = await dataLog.delete(cutoff);
      alert(`已删除 ${r.deleted} 行`);
      await fetchData(applied);
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      {/* 顶部统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="24h 调用" value={(totalOk + totalFail).toString()} />
        <Stat label="24h 成功率" value={`${succRate}%`} ok={totalFail === 0} />
        <Stat label="数据源数" value={sources.length.toString()} />
        <Stat label="日志总数" value={total.toLocaleString()} />
      </div>

      {/* 过滤条 */}
      <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3 flex flex-wrap items-end gap-2 text-xs">
        <Select label="层"  value={applied.layer}  options={["", "provider", "job"]} onChange={v => setApplied(f => ({ ...f, layer: v, source: "" }))} />
        <Select label="源"  value={applied.source} options={["", ...sources]} onChange={v => setApplied(f => ({ ...f, source: v }))} />
        <Select label="状态" value={applied.status} options={["", "success", "fail"]} onChange={v => setApplied(f => ({ ...f, status: v }))} />
        <div className="flex flex-col">
          <label className="text-ink-mute mb-1">关键词</label>
          <input className="bg-ink/5 border border-line rounded px-2 py-1 text-ink placeholder:text-ink-mute"
                 placeholder="operation / error" value={filter.q}
                 onChange={e => setFilter(f => ({ ...f, q: e.target.value }))}
                 onKeyDown={e => { if (e.key === "Enter") setApplied(filter); }} />
        </div>
        <button onClick={() => setApplied(filter)}
                className="px-3 py-1 rounded bg-accent text-white">应用</button>
        <button onClick={() => { setFilter(DEFAULT_FILTER); setApplied(DEFAULT_FILTER); }}
                className="px-3 py-1 rounded border border-line text-ink-soft">清空</button>
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />
            <span className="text-ink-mute">5s 自动刷新</span>
          </label>
          <button onClick={onCleanup} disabled={busy}
                  className="px-3 py-1 rounded border border-down/40 text-down hover:bg-down/10 disabled:opacity-50">
            清理 30 天前
          </button>
        </div>
      </div>

      {/* 表格 */}
      <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-ink/5 text-ink-mute">
              <tr>
                <th className="px-3 py-2 text-left">时间</th>
                <th className="px-3 py-2 text-left">层</th>
                <th className="px-3 py-2 text-left">源</th>
                <th className="px-3 py-2 text-left">操作</th>
                <th className="px-3 py-2 text-right">耗时</th>
                <th className="px-3 py-2 text-right">行数</th>
                <th className="px-3 py-2 text-left">状态</th>
                <th className="px-3 py-2 text-left">错误</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-ink-mute">
                  {err ? `⚠ ${err}` : "暂无日志 — 触发一次数据刷新即可看到记录"}
                </td></tr>
              )}
              {items.map(it => (
                <tr key={it.id}
                    className={`border-t border-line ${rowClass(it)}`}>
                  <td className="px-3 py-1.5 font-mono whitespace-nowrap">{it.ts.replace("T", " ").slice(0, 19)}</td>
                  <td className="px-3 py-1.5 text-ink-soft">{it.layer}</td>
                  <td className="px-3 py-1.5 font-mono">{it.source}</td>
                  <td className="px-3 py-1.5 text-ink-mute">{it.operation ?? "—"}</td>
                  <td className={`px-3 py-1.5 text-right font-mono ${(it.latency_ms ?? 0) >= 3000 ? "text-yellow-400" : ""}`}>
                    {it.latency_ms != null ? `${it.latency_ms}ms` : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">{it.rows ?? "—"}</td>
                  <td className="px-3 py-1.5">
                    <span className={`inline-flex items-center gap-1 ${it.status === "success" ? "text-up" : "text-down"}`}>
                      <Icon.Dot size={6} />
                      {it.status}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-down max-w-xs truncate" title={it.error ?? ""}>
                    {it.error ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {total > items.length && (
          <div className="px-3 py-2 text-[11px] text-ink-mute border-t border-line">
            显示最新 {items.length} 条 / 总 {total.toLocaleString()} 条
          </div>
        )}
      </div>
    </div>
  );
}

function rowClass(it: DataLogItem): string {
  if (it.status === "fail") return "bg-down/5";
  if ((it.latency_ms ?? 0) >= 3000) return "bg-yellow-500/5";
  return "";
}

function Stat({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-mute">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${ok === false ? "text-down" : ok === true ? "text-up" : "text-ink"}`}>{value}</div>
    </div>
  );
}

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col">
      <label className="text-ink-mute mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
              className="bg-ink/5 border border-line rounded px-2 py-1 text-ink">
        {options.map(o => <option key={o} value={o}>{o || "全部"}</option>)}
      </select>
    </div>
  );
}