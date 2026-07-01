// components/Topbar.tsx — 标题 + 周期/聚合 (移动端抽屉式) + 任务状态 chip + 移动端汉堡
import { useStore, store } from "../store";
import { Icon } from "./icons";

const PERIODS: { d: number; l: string }[] = [
  { d: 7,   l: "一周" }, { d: 30,  l: "一月" }, { d: 90,  l: "三月" },
  { d: 182, l: "半年" }, { d: 365, l: "一年" }, { d: 730, l: "两年" },
];
const AGGS = [{ a: "day" as const, l: "日" }, { a: "week" as const, l: "周" }, { a: "month" as const, l: "月" }];

const TITLES: Record<string, string> = {
  dashboard: "仪表盘", alerts: "告警中心", thermometer: "温度计",
  settings: "数据管理", decision: "决策建议", stocks: "自选股",
};

type Props = { onCustomRange: () => void; onOpenDrawer: () => void };

export function Topbar({ onCustomRange, onOpenDrawer }: Props) {
  const active = useStore(s => s.activeTab);
  const days   = useStore(s => s.currentDays);
  const agg    = useStore(s => s.currentAgg);
  const taskS  = useStore(s => s.taskState);
  const taskL  = useStore(s => s.taskLabel);
  const showPeriod = active === "dashboard";

  return (
    <header className="sticky top-0 z-20 backdrop-blur bg-bg/85 border-b border-white/[0.05] px-4 md:px-6 py-3 flex items-center gap-3">
      <button onClick={onOpenDrawer} className="md:hidden w-9 h-9 rounded-lg bg-line hover:bg-line-mid inline-flex items-center justify-center">
        <Icon.Menu className="w-5 h-5" />
      </button>
      <div className="min-w-0 flex-1">
        <h1 className="text-base md:text-lg font-semibold truncate">{TITLES[active] ?? active}</h1>
        <p className="hidden md:block text-[11px] text-ink-mute mt-0.5">ETF 份额 · 北向资金 · 国债 · 汇率 · PMI 宏观指标</p>
      </div>

      {showPeriod && (
        <>
          {/* 桌面端并排显示; 移动端折叠, 鼠标移开自动消失简化: 直接 always show, 横向 scroll */}
          <div className="hidden lg:flex items-center gap-3">
            <Segment items={PERIODS.map(p => ({ key: String(p.d), active: days === p.d, onClick: () => store.set({ currentDays: p.d }), label: p.l }))} />
            <Segment items={AGGS.map(a => ({ key: a.a, active: agg === a.a, onClick: () => store.set({ currentAgg: a.a }), label: a.l }))} variant="alt" />
          </div>
          <div className="flex lg:hidden items-center gap-1 bg-line rounded-lg p-1 border border-line-mid overflow-x-auto">
            {PERIODS.map(p => (
              <button key={p.d} onClick={() => store.set({ currentDays: p.d })}
                className={`px-2 py-1 rounded text-[11px] whitespace-nowrap
                  ${days === p.d ? "bg-accent/30 text-accent" : "text-ink-mute hover:text-ink"}`}>
                {p.l}
              </button>
            ))}
          </div>
          <select value={agg} onChange={e => store.set({ currentAgg: e.target.value as "day" | "week" | "month" })}
            className="lg:hidden bg-line border border-line-mid rounded text-xs px-2 py-1 text-ink">
            {AGGS.map(a => <option key={a.a} value={a.a}>{a.l}</option>)}
          </select>
          <button onClick={onCustomRange} className="text-xs px-2 py-1 text-ink-mute hover:text-ink border border-line-mid rounded">自定义</button>
        </>
      )}

      <div className={`hidden md:inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px]
        ${taskS === "idle" ? "invisible" :
          taskS === "running" ? "bg-accent/20 text-accent animate-pulse-soft" :
          taskS === "failed"  ? "bg-down/20 text-down animate-pulse-soft" :
                                "bg-up/20 text-up"}`}>
        {taskS !== "idle" && (taskL || "空闲")}
      </div>
    </header>
  );
}

function Segment({ items, variant }: { items: { key: string; active: boolean; onClick: () => void; label: string }[]; variant?: "alt" }) {
  const active = variant === "alt" ? "bg-accent-alt/30 text-accent-alt" : "bg-accent/30 text-accent";
  return (
    <div className="flex items-center gap-1 bg-line rounded-lg p-1 border border-line-mid">
      {items.map(it => (
        <button key={it.key} onClick={it.onClick}
          className={`px-2 py-1 rounded text-[11px] transition ${it.active ? active : "text-ink-mute hover:text-ink hover:bg-white/[0.04]"}`}>
          {it.label}
        </button>
      ))}
    </div>
  );
}
