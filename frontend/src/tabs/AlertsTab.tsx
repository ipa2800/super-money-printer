// tabs/AlertsTab.tsx — 告警中心 (检查 + 列表 + 确认)
import { useEffect, useState } from "react";
import { alerts, type Alert } from "../api";
import { AlertList } from "../components/AlertList";

export function AlertsTab() {
  const [items, setItems] = useState<Alert[]>([]);
  const [onlyUnack, setOnlyUnack] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const reload = () => alerts.list(onlyUnack, 100).then(r => setItems(r.alerts)).catch(e => setErr(e.message));
  useEffect(() => { reload(); }, [onlyUnack]);

  const onCheck = async () => {
    try { const r = await alerts.check(); alert(`✓ ${r.triggered} 条新告警`); reload(); }
    catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };
  const onAck = async (id: number) => {
    try { await alerts.ack(id); reload(); }
    catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };

  return (
    <div className="space-y-4">
      {err && <div className="text-down text-sm">❌ {err}</div>}
      <div className="flex flex-wrap gap-3 items-center">
        <button onClick={onCheck} className="bg-accent hover:bg-accent/90 text-white px-4 py-2 rounded text-sm">🔍 立即检查</button>
        <label className="text-ink-soft text-sm flex items-center gap-2 ml-auto">
          <input type="checkbox" checked={onlyUnack} onChange={e => setOnlyUnack(e.target.checked)} /> 仅未确认
        </label>
      </div>
      <AlertList items={items} onAck={onAck} />
    </div>
  );
}
