// components/CustomRangeModal.tsx — 自定义日期范围 (移动全屏, 桌面居中)
import { useState } from "react";

export function CustomRangeModal({ defaultStart, defaultEnd, onApply, onClose }: { defaultStart: string; defaultEnd: string; onApply: (s: string, e: string) => void; onClose: () => void }) {
  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-50" onClick={onClose} />
      <div className="fixed inset-0 md:inset-auto md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2 z-50 bg-bg-soft border border-line-mid rounded-xl md:w-[400px] p-6 animate-slidein">
        <button onClick={onClose} className="absolute top-3 right-4 text-2xl text-ink-soft hover:text-ink">×</button>
        <h3 className="text-base font-semibold mb-4">自定义日期范围</h3>
        <label className="block text-xs text-ink-soft mb-1.5">起始日期</label>
        <input type="date" value={start} onChange={e => setStart(e.target.value)} className="w-full bg-bg border border-line-mid rounded px-3 py-2 text-sm" />
        <label className="block text-xs text-ink-soft mb-1.5 mt-3">结束日期</label>
        <input type="date" value={end} onChange={e => setEnd(e.target.value)} className="w-full bg-bg border border-line-mid rounded px-3 py-2 text-sm" />
        <button onClick={() => onApply(start, end)} className="w-full mt-5 bg-accent hover:bg-accent/90 text-white py-2 rounded text-sm">应用</button>
      </div>
    </>
  );
}
