import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f17", panel: "#121826", edge: "#1e2738",
        ink: "#e6e9ef", muted: "#8b95a6", faint: "#5b6677",
        emerald: { DEFAULT: "#34d399", dk: "#059669" },
        violet: "#a78bfa", amber: "#fbbf24", danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
        mono: ["ui-monospace", "JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
