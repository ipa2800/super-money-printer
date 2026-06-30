// store.ts — 全局应用状态 (activeTab + period + agg + taskState)
// 用 useSyncExternalStore + 自写 store 避免引入 Redux/Zustand
import { useSyncExternalStore } from "react";

export type TaskState = "idle" | "running" | "failed" | "done";

export type AppState = {
  activeTab: string;
  currentDays: number;
  currentAgg: "day" | "week" | "month";
  taskState: TaskState;
  taskLabel: string;
  editingJobId: string | null;
};

const KEY = "smp_state_v1";

export const defaultState: AppState = {
  activeTab: "dashboard",
  currentDays: 30,
  currentAgg: "day",
  taskState: "idle",
  taskLabel: "",
  editingJobId: null,
};

const initial: AppState = (() => {
  try {
    const s = localStorage.getItem(KEY);
    if (s) return { ...defaultState, ...JSON.parse(s) };
  } catch {}
  return defaultState;
})();

let state: AppState = initial;
const listeners = new Set<() => void>();

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify({
      activeTab: state.activeTab,
      currentDays: state.currentDays,
      currentAgg: state.currentAgg,
    }));
  } catch {}
}

export const store = {
  get(): AppState { return state; },
  set(patch: Partial<AppState>) {
    state = { ...state, ...patch };
    persist();
    listeners.forEach(l => l());
  },
  subscribe(l: () => void): () => void {
    listeners.add(l);
    return () => listeners.delete(l);
  },
};

export function useStore<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(store.subscribe, () => selector(store.get()), () => selector(defaultState));
}