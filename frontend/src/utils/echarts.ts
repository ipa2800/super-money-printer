// utils/echarts.ts — ECharts 初始化与 sparkline 配置
import * as echarts from "echarts";

export function sparkOption(values: number[], color: string) {
  return {
    backgroundColor: "transparent",
    grid: { top: 2, right: 2, bottom: 2, left: 2, containLabel: false },
    xAxis: { type: "category", show: false, data: values.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    tooltip: { show: false },
    series: [{
      type: "line", data: values, smooth: true, symbol: "none",
      lineStyle: { color, width: 1.5 },
      areaStyle: {
        color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: color + "40" }, { offset: 1, color: color + "00" }] },
      },
    }],
  };
}

// ponytail: 显式 width/height 防止 CSS grid 布局延迟导致 canvas 默认尺寸错位
export function initSpark(el: HTMLElement, opt: object) {
  const w = el.offsetWidth || 200;
  const h = el.offsetHeight || 36;
  const inst = echarts.init(el, null, { width: w, height: h, renderer: "canvas" });
  inst.setOption(opt as echarts.EChartsOption);
  return inst;
}

export function disposeChart(inst: echarts.ECharts | undefined) {
  if (inst) inst.dispose();
}