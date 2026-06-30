// utils/cron.ts — cron 表达式解析/构建/自然语言预览

export type CronParts = { min: string; hour: string; dom: string; month: string; dow: string };

export function parseCron(cron: string): CronParts | null {
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return null;
  return { min: parts[0], hour: parts[1], dom: parts[2], month: parts[3], dow: parts[4] };
}

export function buildCron(parts: CronParts): string {
  return `${parts.min} ${parts.hour} ${parts.dom} ${parts.month} ${parts.dow}`;
}

export function cronPreviewNL(cron: string): string {
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return cron;
  const [min, hour, dom, month, dow] = parts;

  const dowDesc = (d: string): string => {
    if (d === "*") return "每天";
    if (d === "1-5") return "每个工作日";
    if (d === "6,0" || d === "0,6") return "周末";
    const map = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return d.split(",").map(x => map[parseInt(x)] || x).join(",");
  };
  const timeStr = hour === "*" ? "每分钟" : min === "0" ? `${hour}:00` : `${hour}:${min.padStart(2, "0")}`;
  const dateDesc = dom === "*" && month === "*" ? "" : `${dom === "*" ? "每天" : `${dom}日`} ${month === "*" ? "每月" : `${month}月`}`;

  let s = `${dowDesc(dow)} ${timeStr}`;
  if (dateDesc) s += ` (${dateDesc})`;
  return s;
}