// components/AlertPanel.tsx — 仪表盘告警横向条 (单行, 可一键确认)
import type { AlertSummary } from "../api";
import { Icon } from "./icons";

export function AlertPanel({ summary, onAck }: { summary: AlertSummary | null; onAck?: (id: number) => void }) {
  if (!summary) return null;
  const { red, yellow, top } = summary;
  const total = red + yellow;
  const status = red > 0 ? "red" : yellow > 0 ? "yellow" : "ok";
  const cls =
    status === "red" ? "bg-err-grad border-l-4 border-down" :
    status === "yellow" ? "bg-warn-grad border-l-4 border-warn" :
    "bg-ok-grad border-l-4 border-up";
  const dotCls = status === "red" ? "text-down" : status === "yellow" ? "text-warn" : "text-up";

  return (
    <div className={`rounded-lg pl-3 pr-4 py-2 flex items-center gap-3 text-sm ${cls}`}>
      <Icon.Dot className={`w-4 h-4 ${dotCls}`} />
      <div className="flex-1 min-w-0 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-semibold">
          {status === "red" ? "严重" : status === "yellow" ? "警告" : "正常"}
        </span>
        {total > 0 ? (
          <>
            <span className={red ? "text-down font-semibold" : "text-ink-mute"}>{red} 红</span>
            <span className="text-ink-mute">·</span>
            <span className={yellow ? "text-warn font-semibold" : "text-ink-mute"}>{yellow} 黄</span>
          </>
        ) : (
          <span className="text-ink-mute">无未确认告警</span>
        )}
        {top.length > 0 && (
          <span className="text-ink-soft truncate min-w-0 flex-1">
            — [{top[0].severity === "red" ? "严重" : "警告"}] {top[0].message}
          </span>
        )}
      </div>
      {onAck && top.length > 0 && (
        <button
          onClick={() => onAck(top[0].id)}
          className="shrink-0 text-xs px-3 py-1 rounded bg-line hover:bg-line-mid border border-line-mid inline-flex items-center gap-1.5"
        >
          <Icon.Check className="w-3 h-3" />
          确认
        </button>
      )}
    </div>
  );
}
