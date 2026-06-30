// tabs/SettingsTab.tsx — 数据管理 + 刷新计划 (sub-tab 切换, 移动可用 tabs 横向滚动)
import { useEffect, useState } from "react";
import { etf, indexApi, stock, type ETFItem, type IndexItem, type StockItem } from "../api";
import { CacheStatus } from "../components/CacheStatus";
import { PoolList, type PoolItem } from "../components/PoolList";
import { JobList } from "../components/JobList";
import { CronDrawer } from "../components/CronDrawer";

type ETFSearch = { code: string; name: string };

export function SettingsTab() {
  const [sub, setSub] = useState<"data" | "schedule">("data");
  const [editing, setEditing] = useState<{ id: string; cron: string } | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-line overflow-x-auto">
        {([["data","📦 数据管理"],["schedule","⏱ 刷新计划"]] as const).map(([k, l]) => (
          <button key={k} onClick={() => setSub(k)} className={`px-4 py-2 text-sm rounded-t whitespace-nowrap ${sub === k ? "bg-accent text-white" : "text-ink-soft hover:text-ink"}`}>{l}</button>
        ))}
      </div>

      {sub === "data" && <DataMgmt />}
      {sub === "schedule" && (
        <>
          <JobList
            onEdit={(id, cron) => setEditing({ id, cron })}
            onShowLog={(id) => { document.getElementById(`log-${id}`)?.scrollIntoView(); }}
          />
          {editing && (
            <CronDrawer
              jobId={editing.id}
              initialCron={editing.cron}
              onClose={() => setEditing(null)}
              onSaved={() => setEditing(null)}
            />
          )}
        </>
      )}
    </div>
  );
}

function DataMgmt() {
  const [etfs, setEtfs] = useState<PoolItem[]>([]);
  const [indexes, setIndexes] = useState<PoolItem[]>([]);
  const [stocks, setStocks] = useState<PoolItem[]>([]);
  const reload = () => {
    etf.list().then(r => setEtfs(r.etfs.map((e: ETFItem): PoolItem => ({ id: e.code, name: e.name })))).catch(() => {});
    indexApi.cacheList().then(r => setIndexes(r.indexes.map((i: IndexItem): PoolItem => ({ id: i.symbol, name: i.name ?? i.symbol })))).catch(() => {});
    stock.list().then(r => setStocks(r.stocks.map((s: StockItem): PoolItem => ({ id: s.code, name: s.name })))).catch(() => {});
  };
  useEffect(reload, []);

  return (
    <div className="space-y-4">
      <div className="bg-card-grad border border-white/[0.06] rounded-xl"><div className="p-4 md:p-5"><h3 className="text-xs uppercase tracking-wider text-ink-mute font-medium mb-3">缓存状态</h3><CacheStatus /></div></div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          <PoolList title="ETF 池" placeholder="ETF 代码或名称" items={etfs}
            onSearch={async q => (await etf.search(q)) as unknown as { results: ETFSearch[] }}
            onAdd={async (c, n) => { await etf.add(c, n); reload(); }}
            onRemove={async c => { await etf.remove(c); reload(); }}
          />
        </div>
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          <PoolList title="指数池" placeholder="指数代码 (sh.000300)" items={indexes}
            onSearch={async q => ({ results: (await indexApi.poolList()).indexes.filter(i => i.symbol.includes(q) || (i.name ?? "").includes(q)).map(i => ({ code: i.symbol, name: i.name ?? i.symbol })) })}
            onAdd={async (s, n) => { await indexApi.add(s, n); reload(); }}
            onRemove={async s => { await indexApi.remove(s); reload(); }}
          />
        </div>
        <div className="bg-card-grad border border-white/[0.06] rounded-xl p-4">
          <PoolList title="自选股" placeholder="股票代码或名称" items={stocks}
            onSearch={async q => (await stock.search(q)) as unknown as { results: ETFSearch[] }}
            onAdd={async (c, n) => { await stock.add(c, n); reload(); }}
            onRemove={async c => { await stock.remove(c); reload(); }}
          />
        </div>
      </div>
      <p className="text-ink-mute text-[11px]">🧭 ETF 池 + 指数池的更改会触发 cache backfill; 自选股切换到「自选股」tab 即可看到详情</p>
    </div>
  );
}
