// hooks/useECharts.ts — 在组件挂载时初始化 ECharts, 卸载时 dispose
import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function useECharts(option: object | null, deps: unknown[] = []) {
  const ref = useRef<HTMLDivElement>(null);
  const instRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    instRef.current = echarts.init(ref.current, null, { renderer: "canvas" });
    return () => {
      instRef.current?.dispose();
      instRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (instRef.current && option) {
      instRef.current.setOption(option as echarts.EChartsOption, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [option, ...deps]);

  useEffect(() => {
    const inst = instRef.current;
    if (!inst) return;
    const onResize = () => inst.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return ref;
}