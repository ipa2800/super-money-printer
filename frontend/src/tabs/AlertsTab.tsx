// tabs/AlertsTab.tsx — 告警中心 (检查 + 列表 + 确认)
import { useEffect, useMemo, useState } from "react";
import { alerts, type Alert } from "../api";
import { AlertList } from "../components/AlertList";

export function AlertsTab() {
  const [items, setItems] = useState<Alert[]>([]);
  const [onlyUnack, setOnlyUnack] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState<string | null>(null);  // ponytail: 按 alert_type 分组过滤
  const reload = () => alerts.list(onlyUnack, 100).then(r => setItems(r.alerts)).catch(e => setErr(e.message));
  useEffect(() => { reload(); }, [onlyUnack]);

  // ponytail: 统计每个 alert_type 的数量, 显示为 chip, 点 chip 过滤
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of items) m.set(a.alert_type, (m.get(a.alert_type) ?? 0) + 1);
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1]);
  }, [items]);
  const filtered = catFilter ? items.filter(a => a.alert_type === catFilter) : items;

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
      {/* ponytail: 按类型过滤 chip, 解决「12 条平铺」问题 */}
      {counts.length > 0 && (
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <button onClick={() => setCatFilter(null)}
            className={`px-2.5 py-1 rounded-full border ${catFilter === null ? "bg-accent/20 border-accent text-accent" : "border-line-mid text-ink-mute hover:text-ink"}`}>
            全部 ({items.length})
          </button>
          {counts.map(([type, n]) => (
            <button key={type} onClick={() => setCatFilter(type)}
              className={`px-2.5 py-1 rounded-full border font-mono ${catFilter === type ? "bg-accent/20 border-accent text-accent" : "border-line-mid text-ink-mute hover:text-ink"}`}>
              {type} · {n}
            </button>
          ))}
        </div>
      )}
      <AlertList items={filtered} onAck={onAck} />
    </div>
  );
}
