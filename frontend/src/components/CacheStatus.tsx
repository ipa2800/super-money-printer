// components/CacheStatus.tsx — 缓存状态表 (4 状态: success/stale/never/failed)
import { useEffect, useState } from "react";
import { cache, type CacheItem } from "../api";

const LABEL: Record<string, string> = {
  success: "✓ 正常", stale: "⏰ 过期", never: "⊘ 无数据", failed: "✗ 失败",
};
const CLS: Record<string, string> = {
  success: "text-up", stale: "text-ink-mute", never: "text-ink-mute", failed: "text-down",
};

export function CacheStatus() {
  const [items, setItems] = useState<CacheItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const reload = () => cache.status().then(r => setItems(r.items)).catch(e => setErr(e.message));
  useEffect(() => { reload(); }, []);

  const onClear = async (scope: string, key: string) => {
    if (!confirm(`确认清空 ${scope}/${key}?`)) return;
    try {
      const r = await cache.clear(scope, key);
      alert(`已删除 ${r.deleted} 行`);
      reload();
    } catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };

  if (err) return <div className="text-down text-sm">❌ {err}</div>;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl overflow-x-auto">
      <table className="w-full text-xs min-w-[480px]">
        <thead className="bg-white/[0.04] text-ink-mute text-[10px] uppercase">
          <tr>{["指标 / 代码","状态","最后成功","TTL(秒)","行数","操作"].map(h => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr><td colSpan={6} className="text-ink-mute text-center py-8">暂无缓存数据</td></tr>
          ) : items.map(it => (
            <tr key={`${it.scope}/${it.key}`} className="border-b border-white/[0.03]">
              <td className="px-3 py-2"><code>{it.key}</code> <span className="text-ink-mute text-[10px] ml-1">{it.scope}</span></td>
              <td className={`px-3 py-2 ${CLS[it.status] ?? "text-ink-mute"}`}>{LABEL[it.status] ?? it.status}</td>
              <td className="px-3 py-2 text-ink-soft text-[11px]">{it.last_success ?? "-"}</td>
              <td className="px-3 py-2 text-ink-soft">{it.ttl_seconds}</td>
              <td className="px-3 py-2">{it.row_count}</td>
              <td className="px-3 py-2"><button onClick={() => onClear(it.scope, it.key)} className="text-xs px-2 py-1 rounded bg-line border border-line-mid hover:bg-line-mid">清</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
