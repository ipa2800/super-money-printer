// components/Sidebar.tsx — 左侧导航, md 以上常驻, 以下抽为 drawer (汉堡按钮触发)
import { store, useStore } from "../store";
import { Icon } from "./icons";

const NAV = [
  { id: "dashboard",   label: "仪表盘",   Icon: Icon.ChartBar },
  { id: "alerts",      label: "告警中心", Icon: Icon.Bell },
  { id: "thermometer", label: "温度计",   Icon: Icon.Thermometer },
  { id: "settings",    label: "数据管理", Icon: Icon.Cog },
  { id: "decision",    label: "决策建议", Icon: Icon.Target },
  { id: "stocks",      label: "自选股",   Icon: Icon.TrendingUp },
  { id: "sector",      label: "板块/概念", Icon: Icon.Grid },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const active = useStore(s => s.activeTab);
  return (
    <>
      {/* 移动端 backdrop */}
      <div
        className={`fixed inset-0 bg-black/60 z-30 md:hidden transition-opacity ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        onClick={onClose}
      />
      <aside className={`fixed inset-y-0 left-0 w-56 bg-sidebar-grad border-r border-white/[0.05] p-4 flex flex-col z-40 transition-transform
        ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}>
        <div className="flex items-center gap-3 px-2 mb-8">
          <div className="w-9 h-9 rounded-lg bg-brand-grad flex items-center justify-center text-white font-bold text-xs">SMP</div>
          <div>
            <div className="font-semibold text-sm">宏观经济监控</div>
            <div className="text-[10px] text-ink-mute">v0.2 · React+TW</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(n => {
            const NIcon = n.Icon;
            return (
              <button
                key={n.id}
                onClick={() => { store.set({ activeTab: n.id }); onClose(); }}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition text-left
                  ${active === n.id
                    ? "bg-white/[0.06] text-white"
                    : "text-ink-soft hover:bg-white/[0.04] hover:text-ink"}`}
              >
                <NIcon className="w-4 h-4" />{n.label}
              </button>
            );
          })}
        </nav>
        <div className="mt-auto px-3 py-2 rounded-lg bg-line/50 border border-line text-[10px] text-ink-mute">
          数据源 · akshare · 天天基金 · SSE
        </div>
      </aside>
    </>
  );
}