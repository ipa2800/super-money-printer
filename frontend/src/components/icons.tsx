// components/icons.tsx — 24×24 heroicons-style SVG (stroke=currentColor, stroke-width=2)
import type { SVGProps } from "react";

const base = "w-4 h-4";

type Props = SVGProps<SVGSVGElement> & { size?: number };

function svg(d: string, p: Props = {}) {
  const { size = 16, className = base, ...rest } = p;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...rest}
    >
      <path d={d} />
    </svg>
  );
}

function svgPaths(paths: string[], p: Props = {}) {
  const { size = 16, className = base, ...rest } = p;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...rest}
    >
      {paths.map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
}

export const Icon = {
  Check:  (p?: Props) => svg("M5 13l4 4L19 7", p),
  X:      (p?: Props) => svg("M6 18L18 6M6 6l12 12", p),
  Plus:   (p?: Props) => svg("M12 4v16m8-8H4", p),
  Refresh:(p?: Props) => svgPaths([
    "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
  ], p),
  Menu:   (p?: Props) => svg("M4 6h16M4 12h16M4 18h16", p),
  Warning:(p?: Props) => svgPaths([
    "M12 9v4",
    "M12 17h.01",
    "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z",
  ], p),
  XCircle:(p?: Props) => svgPaths([
    "M10 14l2-2m0 0l2-2m-2 2l-2-2m2-2l2 2m9 2a9 9 0 11-18 0 9 9 0 0118 0z",
  ], p),
  Dot:    (p?: Props) => {
    const { size = 16, className = base, ...rest } = p ?? {};
    return (
      <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" className={className} fill="currentColor" {...rest}>
        <circle cx="12" cy="12" r="6" />
      </svg>
    );
  },
  // ── Sidebar nav ──
  ChartBar: (p?: Props) => svgPaths([
    "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6z",
    "M14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z",
    "M4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2z",
    "M14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z",
  ], p),
  Bell:  (p?: Props) => svgPaths([
    "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
  ], p),
  Thermometer: (p?: Props) => svgPaths([
    "M12 3v10",
    "M12 22a4 4 0 100-8 4 4 0 000 8z",
    "M10 3a2 2 0 114 0v10.083a6 6 0 11-4 0V3z",
  ], p),
  Cog:   (p?: Props) => svgPaths([
    "M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947z",
    "M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  ], p),
  Target:(p?: Props) => svgPaths([
    "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z",
    "M12 18a6 6 0 100-12 6 6 0 000 12z",
    "M12 14a2 2 0 100-4 2 2 0 000 4z",
  ], p),
  TrendingUp: (p?: Props) => svgPaths([
    "M2 17l4-4 4 4 6-6",
    "M16 7h6v6",
  ], p),
  Grid: (p?: Props) => svgPaths([
    "M3 3h7v7H3z",
    "M14 3h7v7h-7z",
    "M14 14h7v7h-7z",
    "M3 14h7v7H3z",
  ], p),
};
