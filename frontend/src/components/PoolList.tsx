// components/PoolList.tsx — 通用池 (搜索 + 添加 + 列表, 复用 ETF/指数/自选股)
import { useState } from "react";

export type PoolItem = { id: string; name?: string };

type Props<T extends PoolItem> = {
  title: string;
  items: T[];
  onSearch: (q: string) => Promise<{ results: { code: string; name: string }[] }>;
  onAdd: (id: string, name: string) => Promise<unknown>;
  onRemove: (id: string) => Promise<unknown>;
  onItemClick?: (item: T) => void;
  placeholder?: string;
};

export function PoolList<T extends PoolItem>(p: Props<T>) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ code: string; name: string }[]>([]);
  const [searching, setSearching] = useState(false);
  const doSearch = async () => {
    setSearching(true);
    try { setResults((await p.onSearch(q)).results); }
    finally { setSearching(false); }
  };
  const doAdd = async (code: string, name: string) => {
    try { await p.onAdd(code, name); alert(`✓ ${code} 已加入 ${p.title}`); }
    catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };
  const doRemove = async (id: string) => {
    if (!confirm(`从 ${p.title} 移除 ${id}?`)) return;
    try { await p.onRemove(id); }
    catch (e: unknown) { alert(`失败: ${(e as Error).message}`); }
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && doSearch()}
          placeholder={p.placeholder ?? "代码或名称"} className="flex-1 bg-bg-soft border border-line-mid rounded px-3 py-1.5 text-sm" />
        <button onClick={doSearch} disabled={searching} className="text-xs px-3 py-1.5 rounded bg-line border border-line-mid hover:bg-line-mid disabled:opacity-50">
          {searching ? "搜索中..." : "搜索"}
        </button>
      </div>
      {results.length > 0 && (
        <div className="bg-line border border-line-mid rounded mb-3 max-h-60 overflow-y-auto">
          {results.map(r => (
            <div key={r.code} onClick={() => doAdd(r.code, r.name)} className="flex items-center gap-3 px-3 py-2 border-b border-white/[0.04] cursor-pointer hover:bg-white/[0.04]">
              <span className="font-mono text-ink">{r.code}</span>
              <span className="flex-1 truncate text-ink-soft">{r.name}</span>
              <span className="text-accent text-xs">+ 加入</span>
            </div>
          ))}
        </div>
      )}
      <div className="text-[11px] text-ink-mute mb-1.5">当前 {p.title}</div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {p.items.length === 0 && <div className="col-span-full text-center text-ink-mute py-6 text-sm">空 — 添加 {p.title} 开始追踪</div>}
        {p.items.map(it => (
          <div key={it.id} className="flex items-center gap-2 p-2 bg-white/[0.02] border border-white/[0.04] rounded text-xs">
            <span className="font-mono text-ink font-medium shrink-0">{it.id}</span>
            <span className="text-ink-soft flex-1 min-w-0 truncate">{it.name ?? "-"}</span>
            <span className="flex gap-1 shrink-0">
              {p.onItemClick && <button onClick={() => p.onItemClick?.(it)} className="text-[10px] px-1.5 py-0.5 rounded bg-line hover:bg-line-mid">详情</button>}
              <button onClick={() => doRemove(it.id)} className="text-[10px] px-1.5 py-0.5 rounded bg-down hover:bg-down/80 text-white">删除</button>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
