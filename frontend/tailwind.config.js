/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg:    { DEFAULT: "#0f1117", soft: "#0a0f1e" },
        card:  { DEFAULT: "#1a1f35", end: "#141829" },
        ink:   { DEFAULT: "#e2e8f0", soft: "#94a3b8", mute: "#64748b", dim: "#475569" },
        line:  { DEFAULT: "#1e293b", mid: "#334155" },
        up:    "#22c55e", down: "#ef4444", warn: "#eab308",
        pos:   "#ef4444", neg: "#22c55e",              // A 股: 红涨绿跌 (区别于 up/down 语义)
        accent:{ DEFAULT: "#3b82f6", alt: "#8b5cf6", pink: "#ec4899" },
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      backgroundImage: {
        "card-grad":    "linear-gradient(135deg, #1a1f35 0%, #141829 100%)",
        "sidebar-grad": "linear-gradient(180deg, #111827 0%, #0a0f1e 100%)",
        "brand-grad":   "linear-gradient(135deg, #3b82f6, #8b5cf6)",
        "err-grad":     "linear-gradient(135deg, #1f1010, #160a0a)",
        "warn-grad":    "linear-gradient(135deg, #1f1a10, #16140a)",
        "ok-grad":      "linear-gradient(135deg, #0f1f14, #0a160c)",
      },
      keyframes: {
        "pulse-soft":  { "0%,100%": { opacity: "1" }, "50%": { opacity: ".6" } },
        slidein:       { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        spin:          { to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
        slidein:     "slidein 0.3s ease-out",
        spin:        "spin 0.8s linear infinite",
      },
    },
  },
  plugins: [],
};
