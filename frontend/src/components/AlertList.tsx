// components/AlertList.tsx — 告警列表 (props 注入或自取)
import { useState, useEffect } from "react";
import { alerts, type Alert } from "../api";
import { Icon } from "./icons";

export function AlertList({ items: externalItems, onAck: externalOnAck }: { items?: Alert[]; onAck?: (id: number) => void | Promise<void> }) {
  const [items, setItems] = useState<Alert[]>(externalItems ?? []);
  const [err, setErr] = useState<string | null>(null);
  const reload = () => alerts.list(false, 100).then(r => setItems(r.alerts)).catch(e => setErr(e.message));
  useEffect(() => {
    if (externalItems) { setItems(externalItems); return; }
    reload();
  }, [externalItems]);

  const onAck = async (id: number) => {
    if (externalOnAck) await externalOnAck(id);
    else { await alerts.ack(id); }
    if (externalItems) {/* parent owns reload */} else reload();
  };

  if (err) return <div className="text-down text-sm inline-flex items-center gap-1.5"><Icon.XCircle className="w-4 h-4" />{err}</div>;
  if (!items.length) return <div className="text-ink-mute text-center py-8 inline-flex items-center gap-1.5"><Icon.Dot className="w-3 h-3 text-up" />无告警</div>;

  return (
    <div className="space-y-2">
      {items.map(a => (
        <div key={a.id} className={`flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border-l-4
          ${a.severity === "red" ? "border-down" : "border-warn"}
          ${a.acknowledged ? "opacity-50" : ""}`}>
          <span className={`text-[11px] px-2 py-0.5 rounded font-medium inline-flex items-center gap-1
            ${a.severity === "red" ? "bg-down/15 text-down" : "bg-warn/15 text-warn"}`}>
            <Icon.Dot className="w-2.5 h-2.5" />
            {a.severity === "red" ? "严重" : "警告"}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-sm text-ink truncate">{a.message}</div>
            <div className="text-[11px] text-ink-mute mt-1">
              <code className="bg-white/[0.05] px-1.5 py-0.5 rounded mr-2">{a.alert_type}</code>
              {a.source} · {a.created_at}
            </div>
          </div>
          <button onClick={() => onAck(a.id)} disabled={a.acknowledged}
            className="text-xs px-3 py-1 rounded bg-line border border-line-mid hover:bg-line-mid disabled:opacity-50 shrink-0 inline-flex items-center gap-1.5">
            {a.acknowledged && <Icon.Check className="w-3 h-3" />}
            {a.acknowledged ? "已确认" : "确认"}
          </button>
        </div>
      ))}
    </div>
  );
}
