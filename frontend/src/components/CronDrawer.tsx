// components/CronDrawer.tsx — 5 列 cron 编辑器 (移动全屏, 桌面 400px drawer)
import { useEffect, useMemo, useState } from "react";
import { parseCron, buildCron, cronPreviewNL } from "../utils/cron";
import { jobs } from "../api";

function setMultiSelect(sel: HTMLSelectElement, val: string) {
  if (val === "*") { Array.from(sel.options).forEach(o => o.selected = true); return; }
  const vals = val.split(",");
  Array.from(sel.options).forEach(o => o.selected = vals.includes(o.value));
}
function range(s: number, e: number) { return Array.from({ length: e - s + 1 }, (_, i) => s + i); }

export function CronDrawer({ jobId, initialCron, onClose, onSaved }: { jobId: string | null; initialCron: string; onClose: () => void; onSaved: () => void }) {
  const parsed = useMemo(() => jobId ? parseCron(initialCron) : null, [jobId, initialCron]);
  const [cron, setCron] = useState(initialCron);
  useEffect(() => { setCron(initialCron); }, [initialCron]);

  const update = () => {
    const f = (id: string) => (document.getElementById(id) as HTMLSelectElement | null)?.value ?? "*";
    const dow = Array.from((document.getElementById("cron-dow") as HTMLSelectElement | null)?.selectedOptions ?? []).map(o => o.value).join(",") || "*";
    setCron(buildCron({ min: f("cron-min"), hour: f("cron-hour"), dom: f("cron-dom"), month: f("cron-month"), dow }));
  };

  useEffect(() => {
    if (!parsed) return;
    const ROWS: [string, number, number][] = [["cron-min",0,59],["cron-hour",0,23],["cron-dom",1,31],["cron-month",1,12]];
    for (const [id, s, e] of ROWS) {
      const sel = document.getElementById(id) as HTMLSelectElement;
      if (!sel) continue;
      sel.innerHTML = "";
      range(s, e).forEach(v => { const o = document.createElement("option"); o.value = String(v); o.textContent = String(v); sel.appendChild(o); });
    }
    const dow = document.getElementById("cron-dow") as HTMLSelectElement;
    if (dow) {
      dow.innerHTML = "";
      ["周日(0)","周一(1)","周二(2)","周三(3)","周四(4)","周五(5)","周六(6)"].forEach((l, i) => {
        const o = document.createElement("option"); o.value = String(i); o.textContent = l; dow.appendChild(o);
      });
    }
    setMultiSelect(document.getElementById("cron-min") as HTMLSelectElement, parsed.min);
    setMultiSelect(document.getElementById("cron-hour") as HTMLSelectElement, parsed.hour);
    setMultiSelect(document.getElementById("cron-dom") as HTMLSelectElement, parsed.dom);
    setMultiSelect(document.getElementById("cron-month") as HTMLSelectElement, parsed.month);
    setMultiSelect(document.getElementById("cron-dow") as HTMLSelectElement, parsed.dow);
    setCron(initialCron);
  }, [parsed, initialCron]);

  if (!jobId) return null;

  const save = async () => {
    try {
      await jobs.patch(jobId, { cron_expr: cron });
      alert(`✓ ${jobId} cron 已更新为 ${cron}`);
      onSaved(); onClose();
    } catch (e: unknown) { alert(`保存失败: ${(e as Error).message}`); }
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-50" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 w-full md:w-[420px] bg-bg-soft border-l border-white/[0.05] p-6 overflow-y-auto z-50 animate-slidein">
        <button onClick={onClose} className="absolute top-3 right-4 text-2xl text-ink-soft hover:text-ink">×</button>
        <h3 className="text-base font-semibold mb-1">编辑刷新计划</h3>
        <div className="text-ink-mute text-xs mb-4">{jobId}</div>
        {["cron-min","cron-hour","cron-dom","cron-month"].map(id => (
          <div key={id} className="flex items-center gap-3 mb-3">
            <label className="text-ink-soft text-xs w-14 capitalize">{id.split("-")[1]}:</label>
            <select id={id} multiple onChange={update} className="flex-1 bg-bg border border-line-mid rounded text-sm h-14" />
          </div>
        ))}
        <div className="flex items-center gap-3 mb-3">
          <label className="text-ink-soft text-xs w-14">星期:</label>
          <select id="cron-dow" multiple onChange={update} className="flex-1 bg-bg border border-line-mid rounded text-sm h-24" />
        </div>
        <div className="bg-white/[0.04] rounded p-3 my-4 font-mono text-xs text-ink-soft">
          {cron} → {cronPreviewNL(cron)}
        </div>
        <button onClick={save} className="w-full bg-accent hover:bg-accent/90 text-white py-2 rounded text-sm">💾 保存</button>
      </div>
    </>
  );
}
