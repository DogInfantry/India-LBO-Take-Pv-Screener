export const MIDNIGHT = {
  bg: "#0b0f17", panel: "#121826", edge: "#1e2738",
  ink: "#e6e9ef", muted: "#8b95a6", axis: "#5b6677",
  emerald: "#34d399", emeraldDk: "#059669", violet: "#a78bfa",
  amber: "#fbbf24", danger: "#ef4444",
  // diverging green->amber->red scale for value/risk encodings
  scale: ["#065f46", "#059669", "#34d399", "#fbbf24", "#ef4444"],
};
// Base ECharts option fragment every chart spreads in for consistent styling.
export const baseOption = {
  backgroundColor: "transparent",
  textStyle: { color: MIDNIGHT.muted, fontFamily: "ui-monospace, monospace" },
  grid: { left: 8, right: 12, top: 16, bottom: 8, containLabel: true },
  tooltip: { trigger: "item" as const, backgroundColor: MIDNIGHT.panel,
             borderColor: MIDNIGHT.edge, textStyle: { color: MIDNIGHT.ink } },
};
