// state.js — 全局 state + 常量 + localStorage 持久化
// 单例 state, 模块之间共享
import { $ } from "./utils.js";

export const TAB_TITLES = {
  dashboard:   "仪表盘",
  alerts:      "告警中心",
  thermometer: "温度计",
  settings:    "数据管理",
  decision:    "决策建议",
  stocks:      "自选股",
};

export const charts = {};   // 全局 ECharts 实例 — 跨模块共享 (kline + stockKl)

export const state = {
  activeTab:    "dashboard",
  currentDays:  30,
  currentAgg:   "day",
  _taskState:   "idle",     // idle | running | failed | done
  editingJobId: null,
  currentStock: null,
};

// 持久化 helpers
export function loadPersisted() {
  state.activeTab   = localStorage.getItem("activeTab")   || "dashboard";
  state.currentDays = parseInt(localStorage.getItem("currentDays") || "30", 10);
  state.currentAgg  = localStorage.getItem("currentAgg")  || "day";
}

export function saveActiveTab(tab) {
  state.activeTab = tab;
  localStorage.setItem("activeTab", tab);
}

export function saveDays(n) {
  state.currentDays = n;
  localStorage.setItem("currentDays", n);
}

export function saveAgg(a) {
  state.currentAgg = a;
  localStorage.setItem("currentAgg", a);
}