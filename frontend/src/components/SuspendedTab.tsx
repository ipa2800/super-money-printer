// components/SuspendedTab.tsx — 通用占位卡
export function SuspendedTab({ name }: { name: string }) {
  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl text-center px-8 py-16">
      <div className="text-5xl mb-4">🚧</div>
      <h3 className="text-lg mb-2">{name}</h3>
      <p className="text-ink-soft text-sm">该功能暂未上线, 将在下一轮迭代中补齐</p>
    </div>
  );
}
