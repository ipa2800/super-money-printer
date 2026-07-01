// hooks/useAutoRefresh.ts — 交易时段内自动轮询 fetch (5s 普通 / 3s 收盘前 30 分钟)
// 非交易时段/午休/周末: 空转 (不调 API), 等下次入段
// tab 不可见: 暂停, 切回立即补一次
// ponytail: 非交易时段以 5s 心跳空转; upgrade — 边界外切 30s 慢心跳
import { useEffect, type DependencyList } from "react";
import { marketTime } from "../utils/marketTime";

// TODO: 心跳参数可配制化 — 现在 intervalMs / closingRushMs 是默认值, 实际是 hardcode 的 5000/3000
// upgrade: 从 store / env / user setting 读取 (例如: 交易员想要 2s, 业余用户 30s)
//         收盘前/中段/开市初 三档可调, 早盘集合竞价 09:15-09:25 也可单独配置
const DEFAULT_INTERVAL = 5000;
const DEFAULT_CLOSING_RUSH = 3000;

export function useAutoRefresh(
  fetch: () => void | Promise<void>,
  deps: DependencyList,
  intervalMs: number = DEFAULT_INTERVAL,
  closingRushMs: number = DEFAULT_CLOSING_RUSH,
) {
  useEffect(() => {
    let id: number | undefined;
    // 首次无脑拉一次, 避免非交易时段页面空白 (用户期望看到上一收盘数据)
    fetch();
    const loop = async () => {
      if (!document.hidden && marketTime.inSession(new Date())) {
        await fetch();
      }
      id = window.setTimeout(loop, marketTime.closingRush(new Date()) ? closingRushMs : intervalMs);
    };
    loop();
    const onVis = () => { if (!document.hidden && marketTime.inSession(new Date())) fetch(); };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      if (id) clearTimeout(id);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
