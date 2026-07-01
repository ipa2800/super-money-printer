// components/SectorMatrixTimeline.tsx — 轮动矩阵时序版
// 2×4 网格, 每格一天 mini scatter (X=RPS_20, Y=加速度), 看板块在 8 天里的象限漂移
// 数据: 并行 fetch 所有 industry 板块的 sector_history, 每天算 RPS_20 + accel_5_20
import { useEffect, useState } from "react";
import * as echarts from "echarts";
import { sector, type SectorHistoryRow } from "../api";

const QUAD_COLORS: Record<string, string> = {
  // ponytail: A 股惯例「红涨绿跌」
  "主升浪": "#ef4444",
  "顶部":   "#eab308",
  "反弹":   "#3b82f6",
  "杀跌":   "#22c55e",
};

const GRID_DAYS = 8;       // 显示最近 8 天
const LOOKBACK  = 30;      // 算 RPS_20 / accel 需要的历史长度
const GRID_COLS = 4;

interface DailyPoint { code: string; type: string; name: string; rps: number; accel: number; }

export function SectorMatrixTimeline() {
  const [days, setDays] = useState<string[]>([]);                       // 8 个日期字符串 (旧→新)
  const [byDay, setByDay] = useState<Record<string, DailyPoint[]>>({});  // date → points
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ref, setRef] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        // 1. 拿当前所有 industry 板块 (只取 BK 前缀 — 备份源 new_xxxx 没 sector_history, 拉了会卡死)
        const snap = await sector.snapshot();
        const industries = snap.items.filter(i => i.type === "industry" && i.code.startsWith("BK"));
        // 2. 并行拉每个板块的历史 (180 天够算 20 日收益 + accel)
        const histResults = await Promise.all(
          industries.map(async i => ({
            meta: { code: i.code, type: i.type, name: i.name },
            rows: (await sector.history(`${i.type}:${i.code}`, LOOKBACK + 20, "day")).rows,
          }))
        );
        // 3. 算出所有出现过的日期, 取最近 GRID_DAYS 个
        const dateSet = new Set<string>();
        for (const h of histResults) for (const r of h.rows) dateSet.add(r.date);
        const allDates = Array.from(dateSet).sort();
        const targetDates = allDates.slice(-GRID_DAYS);                 // 旧→新
        // 4. 对每天, 算所有板块的 RPS_20 + accel_5_20
        const result: Record<string, DailyPoint[]> = {};
        for (const targetDate of targetDates) {
          const closesByCode: Record<string, number[]> = {};           // code → 该板块在 targetDate 之前 LOOKBACK 天的 closes (旧→新)
          for (const h of histResults) {
            const sliced = h.rows.filter(r => r.date <= targetDate).slice(-(LOOKBACK + 1));
            sliced.sort((a, b) => a.date.localeCompare(b.date));       // 旧→新
            closesByCode[h.meta.code] = sliced.map(r => r.close);
          }
          // ret_20d per sector
          const ret20List: { code: string; ret: number }[] = [];
          for (const [code, closes] of Object.entries(closesByCode)) {
            if (closes.length < 21) continue;
            const latest = closes[closes.length - 1];
            const past = closes[closes.length - 21];
            if (latest != null && past != null && past !== 0) {
              ret20List.push({ code, ret: (latest / past - 1) * 100 });
            }
          }
          ret20List.sort((a, b) => a.ret - b.ret);                     // 升序
          const n = ret20List.length;
          const rpsMap: Record<string, number> = {};
          ret20List.forEach((x, idx) => { rpsMap[x.code] = (idx + 1) / n * 100; });
          // accel_5_20 + name lookup
          const nameMap = Object.fromEntries(histResults.map(h => [h.meta.code, h.meta.name]));
          const typeMap  = Object.fromEntries(histResults.map(h => [h.meta.code, h.meta.type]));
          const points: DailyPoint[] = [];
          for (const { code, ret } of ret20List) {
            const closes = closesByCode[code];
            const ret5  = closes.length >= 6 && closes[closes.length - 6] !== 0
              ? (closes[closes.length - 1] / closes[closes.length - 6] - 1) * 100 : null;
            const accel = ret5 != null ? (ret5 / 5) - (ret / 20) : null;
            points.push({
              code, type: typeMap[code], name: nameMap[code] ?? code,
              rps: rpsMap[code], accel: accel ?? 0,
            });
          }
          result[targetDate] = points;
        }
        setDays(targetDates);
        setByDay(result);
      } catch (e: any) {
        setErr(e.message ?? String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!ref || !days.length) return;
    const inst = echarts.init(ref, null, { renderer: "canvas" });
    inst.setOption(buildOption(days, byDay), true);
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref);
    return () => { ro.disconnect(); inst.dispose(); };
  }, [ref, days, byDay]);

  const rows = Math.ceil(days.length / GRID_COLS) || 2;
  const H = 180, W = 320;  // 单格尺寸
  const totalH = rows * H + 20;
  const totalW = GRID_COLS * W + 40;

  return (
    <div className="bg-card-grad border border-white/[0.06] rounded-xl p-3">
      <div className="flex items-center gap-2 text-xs text-ink-mute mb-2 flex-wrap">
        <span className="text-ink font-medium">轮动矩阵时序</span>
        <span>·</span>
        <span>最近 {GRID_DAYS} 天象限漂移 · X=RPS_20 / Y=加速度</span>
        {/* ponytail: 颜色图例, 说明散点对应象限 */}
        <span className="flex items-center gap-2 ml-3">
          {(["主升浪", "顶部", "反弹", "杀跌"] as const).map(k => (
            <span key={k} className="inline-flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: QUAD_COLORS[k] }} />
              <span>{k}</span>
            </span>
          ))}
        </span>
        <span className="ml-auto">{loading ? "计算中…" : `${days.length} 天`}</span>
      </div>
      <div ref={setRef} style={{ height: totalH, width: totalW }} />
      {err && <div className="text-down text-xs">⚠ {err}</div>}
    </div>
  );
}

function buildOption(days: string[], byDay: Record<string, DailyPoint[]>): echarts.EChartsCoreOption {
  const H = 180, W = 320, GAP = 8;
  // 每个子图一个 grid + xAxis + yAxis + scatter
  const grids: any[] = [];
  const xAxes: any[] = [];
  const yAxes: any[] = [];
  const series: any[] = [];
  days.forEach((date, idx) => {
    const col = idx % GRID_COLS, row = Math.floor(idx / GRID_COLS);
    const x = 20 + col * (W + GAP);
    const y = 20 + row * (H + GAP + 16);  // 16 留日期标题
    grids.push({ left: x, top: y, width: W, height: H - 16, show: true, borderColor: "#1e293b" });
    xAxes.push({
      gridIndex: idx, type: "value", min: 0, max: 100,
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { show: col === 0, color: "#475569", fontSize: 9 },
      axisLine: { lineStyle: { color: "#334155" } },
    });
    yAxes.push({
      gridIndex: idx, type: "value", min: -1.5, max: 1.5,
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { show: false, color: "#475569", fontSize: 9 },
      axisLine: { lineStyle: { color: "#334155" } },
    });
    const pts = byDay[date] || [];
    // ponytail: 主升浪/顶部 象限全标 (RPS>=70, 关键信号) + 其他象限 top 5
    const labeled = new Set<string>();
    pts.filter(p => p.rps >= 70).forEach(p => labeled.add(p.code));  // 主升浪+顶部
    pts.filter(p => p.rps < 70).sort((a, b) => b.rps - a.rps).slice(0, 5)
       .forEach(p => labeled.add(p.code));                           // 其他象限补 5 个
    series.push({
      type: "scatter", xAxisIndex: idx, yAxisIndex: idx,
      symbolSize: (v: any) => labeled.has(v[3]) ? 11 : 7,
      data: pts.map(p => [p.rps, p.accel, p.name, p.code]),
      // ponytail: 白字直接画在点上方, 不用 hover
      label: {
        show: true, position: "top", distance: 2,
        color: "#ffffff", fontSize: 8, fontWeight: 600,
        textBorderColor: "#000000", textBorderWidth: 1,
        formatter: (p: any) => labeled.has(p.value[3]) ? p.value[2] : "",
      },
      itemStyle: {
        // ponytail: A 股惯例「红涨绿跌」— 主升浪/反弹红, 顶部/杀跌绿
        color: (p: any) => {
          const rps = p.value[0], accel = p.value[1];
          if (rps >= 70) return accel > 0 ? QUAD_COLORS["主升浪"] : QUAD_COLORS["顶部"];
          else return accel > 0 ? QUAD_COLORS["反弹"] : QUAD_COLORS["杀跌"];
        },
        opacity: 0.85,
      },
    });
    // 4 象限参考线 (RPS=70, accel=0)
    series.push({
      type: "line", xAxisIndex: idx, yAxisIndex: idx, symbol: "none",
      markLine: {
        silent: true, symbol: "none",
        data: [
          { xAxis: 70, lineStyle: { color: "#475569", type: "dashed" } },
          { yAxis: 0,  lineStyle: { color: "#475569", type: "dashed" } },
        ],
        label: { show: false },
      },
      data: [],
    });
    // 日期小标题 (用 graphic)
    series.push({
      type: "scatter", xAxisIndex: idx, yAxisIndex: idx, silent: true,
      data: [],  // 空 series, 触发不了 graphic — 用下面的 title 替代
    });
  });

  // 用 graphic 在每格左上角写日期
  const graphics: any[] = days.map((date, idx) => {
    const col = idx % GRID_COLS, row = Math.floor(idx / GRID_COLS);
    const x = 20 + col * (W + GAP) + 4;
    const y = 20 + row * (H + GAP + 16) + 2;
    return {
      type: "text", left: x, top: y,
      style: { text: date.slice(5), fill: "#94a3b8", fontSize: 10 },
    };
  });

  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      backgroundColor: "#1e293b", borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 },
      formatter: (p: any) => p.value[2]
        ? `<b>${p.value[2]}</b><br/>RPS=${p.value[0].toFixed(0)} 加速度=${p.value[1].toFixed(2)}`
        : "",
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    graphic: graphics,
  };
}