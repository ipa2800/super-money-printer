// utils/marketTime.ts — A 股交易时段判定 (前端共享)
// ponytail: 单源, useAutoRefresh / MinuteChart 都用这里, 改时段只改一处

const MORNING_START = 9 * 60 + 30;   // 09:30
const MORNING_END   = 11 * 60 + 30;  // 11:30
const AFTERNOON_START = 13 * 60;     // 13:00
const AFTERNOON_END = 15 * 60;       // 15:00
const CLOSING_RUSH_START = 14 * 60 + 30;  // 14:30

const inSession = (d: Date) => {
  const dow = d.getDay();
  const t = d.getHours() * 60 + d.getMinutes();
  return dow !== 0 && dow !== 6 && (
    (t >= MORNING_START && t < MORNING_END) ||
    (t >= AFTERNOON_START && t < AFTERNOON_END)
  );
};

const closingRush = (d: Date) => {
  const dow = d.getDay();
  const t = d.getHours() * 60 + d.getMinutes();
  return dow !== 0 && dow !== 6 && (t >= CLOSING_RUSH_START && t < AFTERNOON_END);
};

export const marketTime = { inSession, closingRush };
