// components/SectorDataStatus.tsx — 板块/概念 tab 顶部数据新鲜度条
// 拉 sector.snapshot + sectorAnalytics.rank, 从响应里提取 fetched_at / date, 显示给用户
import { useEffect, useState } from "react";
import { sector, sectorAnalytics } from "../api";

function fmtAgo(iso: string | undefined | null): string {
  if (!iso) return "—";
  const t = new Date(iso.replace(" ", "T")).getTime();
  if (isNaN(t)) return iso;
  const diff = Math.floor((Date.now() - t) / 1000);
  if (diff < 60) return `${diff} 秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

function isStale(iso: string | undefined | null, thresholdH = 6): "fresh" | "warn" | "stale" | "unknown" {
  if (!iso) return "unknown";
  const t = new Date(iso.replace(" ", "T")).getTime();
  if (isNaN(t)) return "unknown";
  const hours = (Date.now() - t) / 3600000;
  if (hours < thresholdH) return "fresh";
  if (hours < thresholdH * 4) return "warn";
  return "stale";
}

const STATUS_COLOR: Record<string, string> = {
  fresh:   "text-pos",
  warn:    "text-amber-400",
  stale:   "text-down",
  unknown: "text-ink-mute",
};

const STATUS_LABEL: Record<string, string> = {
  fresh:   "●",
  warn:    "▲",
  stale:   "✕",
  unknown: "?",
};

export function SectorDataStatus() {
  const [snapAt, setSnapAt] = useState<string | null>(null);
  const [anaDate, setAnaDate] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      sector.snapshot().then(r => {
        const items = r.items || [];
        // 取最新 fetched_at
        const latest = items.reduce((m, it) => {
          const t = it.fetched_at;
          if (!t) return m;
          return !m || t > m ? t : m;
        }, "");
        setSnapAt(latest || null);
      }).catch(e => setErr(`快照: ${e.message}`)),
      sectorAnalytics.rank({ limit: 1 }).then(r => {
        setAnaDate(r.date || null);
      }).catch(() => {}),   // analytics 可选失败
    ]);
  }, []);

  const sCls = STATUS_COLOR[isStale(snapAt)];
  const aCls = STATUS_COLOR[isStale(anaDate)];
  const today = new Date().toISOString().slice(0, 10);
  const isFutureAna = anaDate && anaDate > today;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl px-3 py-2 text-xs flex flex-wrap items-center gap-x-4 gap-y-1">
      <div className="flex items-center gap-1.5">
        <span className="text-ink-mute">🕐 数据状态</span>
      </div>

      <div className="flex items-center gap-1.5">
        <span className={sCls}>{STATUS_LABEL[isStale(snapAt)]}</span>
        <span className="text-ink-mute">板块快照:</span>
        <span className={sCls}>{snapAt ? fmtAgo(snapAt) : "—"}</span>
        {snapAt && <span className="text-ink-dim">({snapAt.slice(0, 19).replace("T", " ")})</span>}
      </div>

      <div className="flex items-center gap-1.5">
        <span className={aCls}>{STATUS_LABEL[isStale(anaDate)]}</span>
        <span className="text-ink-mute">板块分析:</span>
        <span className={aCls}>{anaDate ?? "—"}</span>
        {isFutureAna && <span className="text-amber-400">(今日数据未生成, 显示最近)</span>}
      </div>

      {err && <span className="text-down">{err}</span>}

      <div className="ml-auto text-ink-mute text-[10px]">
        ● 新鲜 &lt; 6h · ▲ 过期 &lt; 24h · ✕ 失效
      </div>
    </div>
  );
}