// components/AlertPanel.tsx — 仪表盘顶部 4 状态告警摘要
import type { AlertSummary } from "../api";

const S = (summary: AlertSummary) => {
  if (summary.red > 0) return { c: "bg-err-grad border border-down/20", label: "🔴" };
  if (summary.yellow > 0) return { c: "bg-warn-grad border border-warn/20", label: "🟡" };
  return { c: "bg-ok-grad border border-up/20", label: "🟢" };
};

export function AlertPanel({ summary }: { summary: AlertSummary | null }) {
  if (!summary) return null;
  const s = S(summary);
  return (
    <div className={`rounded-xl p-4 flex items-start gap-3 ${s.c}`}>
      <span className="text-2xl">{s.label}</span>
      <div className="flex-1 min-w-0">
        <div className="font-semibold">{s.label} 告警</div>
        <div className="text-xs text-ink-soft mt-1">
          <span className={summary.red > 0 ? "text-down" : "text-ink-mute"}>{summary.red} 红</span>
          <span className="mx-2">·</span>
          <span className="text-ink-mute">{summary.yellow} 黄</span>
          {summary.top.length > 0 && summary.top.map(a => (
            <span key={a.id} className="text-ink-soft ml-2 truncate inline-block max-w-xs align-middle">
              — [{a.severity === "red" ? "严重" : "警告"}] {a.message}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
