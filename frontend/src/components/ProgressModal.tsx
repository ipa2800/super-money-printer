// components/ProgressModal.tsx — 全局任务进度 modal (基于 taskState 自动开合)
import { useEffect, useRef } from "react";
import { store, useStore } from "../store";
import { Icon } from "./icons";

export function ProgressModal() {
  const taskState = useStore(s => s.taskState);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (window as unknown as { appendLog?: (t: string, c?: string) => void }).appendLog = (text, cls) => {
      const log = logRef.current; if (!log) return;
      const div = document.createElement("div");
      div.className = "line " + (cls ?? "");
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    };
    return () => { delete (window as unknown as { appendLog?: unknown }).appendLog; };
  }, []);

  const close = () => store.set({ taskState: "idle", taskLabel: "" });
  const open = taskState === "running" || taskState === "failed" || taskState === "done";

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 transition-opacity ${open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}>
      <div className="bg-line border border-line-mid rounded-xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <h3 className="text-base font-semibold mb-4 inline-flex items-center gap-2">
          {taskState === "running" && "运行中..."}
          {taskState === "failed"  && <><Icon.X className="w-5 h-5 text-down" />失败</>}
          {taskState === "done"    && <><Icon.Check className="w-5 h-5 text-up" />完成</>}
        </h3>
        <div ref={logRef} className="progress-log flex-1 overflow-y-auto bg-bg border border-line-mid rounded p-3 font-mono text-[11px] text-ink-soft min-h-[200px] max-h-[60vh]" />
        <button onClick={close} className="mt-3 self-end px-4 py-1.5 rounded bg-line-mid border border-line text-ink-soft hover:bg-line text-sm">关闭</button>
      </div>
    </div>
  );
}
