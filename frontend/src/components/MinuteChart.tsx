// components/MinuteChart.tsx — 分时图 (主流 A 股风格: 红涨绿跌 / 昨收线 / 右轴百分比 / 浮动价标 / 完整交易时段)
import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import type { MinuteBar } from "../api";
import { marketTime } from "../utils/marketTime";

const UP = "#ef4444";       // 红涨 (中国惯例)
const DOWN = "#22c55e";     // 绿跌
const AVG = "#eab308";      // 均价黄
const PC_LINE = "#94a3b8";  // 昨收灰

// A 股完整交易时段: 集合竞价 09:15-09:25 + 早盘 09:30-11:30 + 午盘 13:00-15:00 (253 个分钟)
const TRADING_HOURS: readonly string[] = (() => {
  const out: string[] = [];
  const push = (h: number, m: number) => out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  for (let m = 15; m <= 25; m++) push(9, m);          // 集合竞价 09:15-09:25 (11)
  for (let m = 30; m <= 59; m++) push(9, m);          // 09:30-09:59 (30)
  for (let m = 0; m <= 59; m++) push(10, m);          // 10:00-10:59 (60)
  for (let m = 0; m <= 30; m++) push(11, m);          // 11:00-11:30 (31)
  for (let m = 0; m <= 59; m++) push(13, m);          // 13:00-13:59 (60)
  for (let m = 0; m <= 59; m++) push(14, m);          // 14:00-14:59 (60)
  push(15, 0);                                          // 15:00 (1)
  return out;
})();

// X 轴锚点 (约每 30 分钟一个, 主流软件密度)
const ANCHORS = ["09:15", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00"];

type Props = { data: MinuteBar[]; prev_close?: number };

// 顶部时间戳条: 数据时间 + 当前时间 (每秒 tick) + 延迟
// 延迟 = 当前 - 上次 fetch 时刻 (useAutoRefresh 5s 轮询, 所以 max ~5s)
// 收盘后/午休/盘前: 延迟无意义, 隐藏
function TimestampBar({ dataTime, fetchedAt }: { dataTime: string; fetchedAt: Date }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const fmt = (d: Date) => d.toTimeString().slice(0, 8);
  const inSession = marketTime.inSession(now);
  // 真正含义: 距离上次拿到这批数据过了几秒 (≈ 轮询间隔 5s)
  const delay = Math.max(0, Math.floor((now.getTime() - fetchedAt.getTime()) / 1000));
  const fmtDelay = (s: number) => s < 60 ? `${s}秒` : `${Math.floor(s / 60)}分${s % 60}秒`;
  return (
    <div className="flex gap-4 text-[11px] text-ink-mute mb-1 font-mono">
      <span>数据 <span className="text-ink">{dataTime}:00</span></span>
      <span>现在 <span className="text-ink">{fmt(now)}</span></span>
      {inSession && <span>延迟 <span className="text-warn">{fmtDelay(delay)}</span></span>}
    </div>
  );
}

export function MinuteChart({ data, prev_close }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  // ponytail: 每次 data prop 引用变 (= 轮询拿到新批) 就更新时间戳; 给 TimestampBar 算延迟
  const [fetchedAt, setFetchedAt] = useState(() => new Date());
  useEffect(() => { setFetchedAt(new Date()); }, [data]);

  // 「现在」 = 最后一个有数据的时刻 (纯函数, 提前算出供 TimestampBar 使用)
  // ponytail: 重复一次遍历 vs 共享 state, 这里数据小 (<300 点), 重复 OK
  const lastTime = (() => {
    if (!data.length) return "15:00";
    const norm = (s: string) => {
      const t = s.replace(":", "").slice(0, 4);
      return `${t.slice(0, 2)}:${t.slice(2)}`;
    };
    const have = new Set(data.map(d => norm(d.time)));
    for (let i = TRADING_HOURS.length - 1; i >= 0; i--) {
      if (have.has(TRADING_HOURS[i])) return TRADING_HOURS[i];
    }
    return "15:00";
  })();

  useEffect(() => {
    if (!ref.current || !data.length) return;
    const inst = echarts.init(ref.current);

    // 数据按 HH:MM 映射到完整 TRADING_HOURS, 缺数据点为 undefined (ECharts 自动断线)
    // 后端格式: "0930" / "09:30:SS" 兼容, 归一为 HH:MM
    const norm = (s: string) => {
      const t = s.replace(":", "").slice(0, 4);
      return `${t.slice(0, 2)}:${t.slice(2)}`;
    };
    const dataMap = new Map(data.map(d => [norm(d.time), d]));
    const prices = TRADING_HOURS.map(t => dataMap.get(t)?.price);
    const avgs   = TRADING_HOURS.map(t => dataMap.get(t)?.avg_price);
    const vols   = TRADING_HOURS.map(t => dataMap.get(t)?.volume ?? 0);

    const open = data[0].price;
    const pc = prev_close ?? open;                     // 昨收 (fallback 今开)
    let lastIdx = TRADING_HOURS.length - 1;
    while (lastIdx >= 0 && prices[lastIdx] == null) lastIdx--;
    const last = prices[lastIdx] ?? open;
    const isUp = last >= pc;
    const lineColor = isUp ? UP : DOWN;
    const fillColor = isUp ? "rgba(239,68,68,0.12)" : "rgba(34,197,94,0.12)";
    const changeAmt = last - pc;
    const changePct = (changeAmt / pc) * 100;

    // 左轴 price 范围 (跳过 undefined, 含昨收保证水平线画得出来)
    const pArr = prices.filter((v): v is number => v != null);
    const aArr = avgs.filter((v): v is number => v != null);
    const max = Math.max(...pArr, ...aArr, pc);
    const min = Math.min(...pArr, ...aArr, pc);
    const pad = (max - min) * 0.08 || 0.01;
    const yMin = min - pad;
    const yMax = max + pad;
    const pctMin = ((yMin - pc) / pc) * 100;
    const pctMax = ((yMax - pc) / pc) * 100;

    inst.setOption({
      backgroundColor: "transparent",
      animation: false,
      grid: [
        { left: 50, right: 70, top: 16, height: "60%" },
        { left: 50, right: 24, top: "78%", height: "16%" },
      ],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", lineStyle: { color: "#475569", type: "dashed" } },
        backgroundColor: "#1e293b",
        borderColor: "#334155",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        padding: [6, 10],
        formatter: (params: unknown) => {
          const arr = params as Array<{ dataIndex: number }>;
          if (!Array.isArray(arr) || !arr.length) return "";
          const i = arr[0].dataIndex;
          const p = prices[i];
          if (p == null) return "";                    // 空段不显示 tooltip
          const t = TRADING_HOURS[i];
          const a = avgs[i];
          const v = vols[i];
          const d = p - pc;
          const pct = (d / pc) * 100;
          const up = p >= pc;
          const c = up ? UP : DOWN;
          const sign = d >= 0 ? "+" : "";
          return `<div style="font-family:ui-monospace,monospace;font-size:11px;line-height:1.7;min-width:150px">
            <div style="color:#94a3b8;margin-bottom:3px">${t}</div>
            <div>价 <b style="color:${c}">${p.toFixed(2)}</b> <span style="color:${c};font-size:10px">${sign}${d.toFixed(2)} ${sign}${pct.toFixed(2)}%</span></div>
            <div style="color:${AVG}">均 ${a?.toFixed(2) ?? "-"}</div>
            <div style="color:#94a3b8">量 ${v.toLocaleString()}</div>
          </div>`;
        },
      },
      xAxis: [
        {
          type: "category", data: TRADING_HOURS, gridIndex: 0,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        {
          type: "category", data: TRADING_HOURS, gridIndex: 1,
          axisLabel: {
            color: "#64748b", fontSize: 10,
            formatter: (v: string) => ANCHORS.includes(v) ? v : "",
          },
          axisLine: { show: false },
          axisTick: { show: false },
        },
      ],
      yAxis: [
        {
          min: yMin, max: yMax, gridIndex: 0, position: "left",
          axisLabel: { color: "#64748b", fontSize: 10, formatter: (v: number) => v.toFixed(2) },
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
        },
        {
          min: pctMin, max: pctMax, gridIndex: 0, position: "right",
          axisLabel: {
            color: "#64748b", fontSize: 10,
            formatter: (v: number) => (v >= 0 ? "+" : "") + v.toFixed(2) + "%",
          },
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { show: false },
        },
        {
          gridIndex: 1, axisLabel: { show: false },
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "价格", type: "line", data: prices, smooth: false, showSymbol: false,
          connectNulls: false,                          // 集合竞价/午休/未到时间 自然断线
          lineStyle: { color: lineColor, width: 1.5 },
          areaStyle: { color: fillColor },
          markLine: {
            silent: true, symbol: "none",
            data: [
              {
                yAxis: pc,
                lineStyle: { color: PC_LINE, type: "dashed", width: 1 },
                label: {
                  position: "insideStartTop",
                  color: PC_LINE, fontSize: 10,
                  formatter: () => `昨收 ${pc.toFixed(2)}`,
                },
              },
              {
                xAxis: "11:30",                          // 午休分割线
                lineStyle: { color: "#475569", type: "dashed", width: 1 },
                label: { show: false },
              },
              {
                xAxis: lastTime,                         // «现在» 竖线
                lineStyle: { color: "#cbd5e1", type: "solid", width: 1 },
                label: {
                  position: "insideStartTop",
                  color: "#cbd5e1", fontSize: 10, fontWeight: 600,
                  formatter: () => "现在",
                },
              },
            ],
          },
          markPoint: {
            silent: true,
            symbol: "rect",
            symbolSize: [58, 30],
            symbolOffset: [44, 0],
            itemStyle: { color: lineColor },
            label: {
              color: "#fff", fontSize: 10, lineHeight: 13,
              formatter: () => `${last.toFixed(2)}\n${changeAmt >= 0 ? "+" : ""}${changePct.toFixed(2)}%`,
            },
            data: [{ coord: [lastTime, last] }],
          },
        },
        {
          name: "均价", type: "line", data: avgs, showSymbol: false,
          connectNulls: false,
          lineStyle: { color: AVG, width: 1, type: "dashed" },
        },
        {
          name: "量", type: "bar", data: vols, xAxisIndex: 1, yAxisIndex: 2,
          itemStyle: {
            color: (p: { dataIndex: number }) => {
              const idx = p.dataIndex;
              const price = prices[idx];
              return price == null ? "transparent"
                : price >= pc ? "rgba(239,68,68,0.7)" : "rgba(34,197,94,0.7)";
            },
          },
        },
      ],
    });

    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); inst.dispose(); };
  }, [data, prev_close]);

  return (
    <>
      <TimestampBar dataTime={lastTime} fetchedAt={fetchedAt} />
      <div ref={ref} className="w-full h-72 md:h-80" />
    </>
  );
}