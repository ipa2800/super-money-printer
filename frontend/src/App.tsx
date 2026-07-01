// App.tsx — 顶层响应式 layout: sidebar (md 以上常驻, 以下抽屉) + main + 全局 modal
import { useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { ProgressModal } from "./components/ProgressModal";
import { DashboardTab } from "./tabs/DashboardTab";
import { AlertsTab } from "./tabs/AlertsTab";
import { ThermometerTab } from "./tabs/ThermometerTab";
import { DecisionTab } from "./tabs/DecisionTab";
import { SettingsTab } from "./tabs/SettingsTab";
import { StocksTab } from "./tabs/StocksTab";
import { SectorTab } from "./tabs/SectorTab";
import { CustomRangeModal } from "./components/CustomRangeModal";
import { useWebSocket } from "./hooks/useWebSocket";
import { useStore, store } from "./store";

export function App() {
  const activeTab = useStore(s => s.activeTab);
  useWebSocket();
  const [showRange, setShowRange] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const fn = (e: Event) => { store.set({ activeTab: (e as CustomEvent<{ tab: string }>).detail.tab }); setDrawerOpen(false); };
    document.addEventListener("smp:switchTab", fn as EventListener);
    return () => document.removeEventListener("smp:switchTab", fn as EventListener);
  }, []);

  return (
    <div className="flex min-h-screen bg-bg text-ink">
      <Sidebar open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <main className="flex-1 min-w-0 md:ml-56">
        <Topbar onCustomRange={() => setShowRange(true)} onOpenDrawer={() => setDrawerOpen(true)} />
        <div className="p-4 md:p-6 pb-12">{renderTab(activeTab)}</div>
      </main>
      <ProgressModal />
      {showRange && (
        <CustomRangeModal
          defaultStart="2025-01-01"
          defaultEnd="2026-06-30"
          onApply={(s, e) => {
            const days = Math.max(1, Math.round((new Date(e).getTime() - new Date(s).getTime()) / 86_400_000));
            store.set({ currentDays: days });
            setShowRange(false);
          }}
          onClose={() => setShowRange(false)}
        />
      )}
    </div>
  );
}

function renderTab(tab: string) {
  switch (tab) {
    case "alerts":      return <AlertsTab />;
    case "thermometer": return <ThermometerTab />;
    case "decision":    return <DecisionTab />;
    case "settings":    return <SettingsTab />;
    case "stocks":      return <StocksTab />;
    case "sector":      return <SectorTab />;
    case "dashboard":
    default:            return <DashboardTab />;
  }
}
