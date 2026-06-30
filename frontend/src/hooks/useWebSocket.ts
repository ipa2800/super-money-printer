// hooks/useWebSocket.ts — WebSocket 生命周期 + 自动重连 + task chip 状态机
import { useEffect, useRef } from "react";
import { store } from "../store";

type WSMessage =
  | { type: "heartbeat" }
  | { type: "job_start";   job_id: string }
  | { type: "job_done";    job_id: string; duration_ms?: number; detail?: string }
  | { type: "job_error";   job_id: string; detail?: string }
  | { type: "job_progress"; detail?: string }
  | { action: "refresh" | "backfill" | "macro_refresh" }
  | { action: "done"; detail?: string }
  | { action: "error"; detail?: string; error?: string };

function _log(text: string, cls?: string) {
  const w = window as unknown as { appendLog?: (t: string, c?: string) => void };
  w.appendLog?.(text, cls);
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let alive = true;

    const connect = () => {
      if (!alive) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/progress`);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        let m: WSMessage;
        try { m = JSON.parse(ev.data); } catch { return; }
        if ("type" in m && m.type === "heartbeat") return;

        // 新格式
        if ("type" in m) {
          if (m.type === "job_start") {
            store.set({ taskState: "running", taskLabel: `运行中: ${m.job_id}` });
            _log(`▶ ${m.job_id} started`);
          } else if (m.type === "job_done") {
            store.set({ taskState: "done", taskLabel: `✓ ${m.job_id} 完成` });
            _log(`✓ ${m.job_id} done (${m.duration_ms ?? 0}ms): ${m.detail ?? ""}`, "ok");
            setTimeout(() => store.set({ taskState: "idle", taskLabel: "" }), 3000);
          } else if (m.type === "job_error") {
            store.set({ taskState: "failed", taskLabel: `✗ ${m.job_id} 失败` });
            _log(`✗ ${m.job_id} error: ${m.detail ?? ""}`, "err");
          } else if (m.type === "job_progress") {
            _log(`… ${m.detail ?? ""}`);
          }
          return;
        }
        // 旧格式兼容
        if ("action" in m) {
          if (m.action === "refresh" || m.action === "backfill" || m.action === "macro_refresh") {
            store.set({ taskState: "running", taskLabel: `运行中: ${m.action}` });
            _log(`▶ ${m.action}`);
          } else if (m.action === "done") {
            store.set({ taskState: "done", taskLabel: `✓ ${m.action} 完成` });
            _log(`✓ done: ${m.detail ?? ""}`, "ok");
            setTimeout(() => store.set({ taskState: "idle", taskLabel: "" }), 3000);
          } else if (m.action === "error") {
            store.set({ taskState: "failed", taskLabel: `✗ 失败` });
            _log(`✗ ${m.detail ?? m.error ?? "unknown error"}`, "err");
          }
        }
      };

      ws.onclose = () => {
        if (alive) setTimeout(connect, 3000);  // 自动重连
      };
    };

    connect();
    return () => {
      alive = false;
      wsRef.current?.close();
    };
  }, []);
}