import type { Config } from "tailwindcss";

// Design tokens live as CSS variables in src/index.css; Tailwind maps names onto them.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg-rgb) / <alpha-value>)",
        surface: "rgb(var(--surface-rgb) / <alpha-value>)",
        "surface-2": "rgb(var(--surface-2-rgb) / <alpha-value>)",
        border: "rgb(var(--border-rgb) / <alpha-value>)",
        text: "rgb(var(--text-rgb) / <alpha-value>)",
        muted: "rgb(var(--muted-rgb) / <alpha-value>)",
        accent: "rgb(var(--accent-rgb) / <alpha-value>)",
        outside: "rgb(var(--outside-rgb) / <alpha-value>)",
        private: "rgb(var(--private-rgb) / <alpha-value>)",
        sendsout: "rgb(var(--sendsout-rgb) / <alpha-value>)",
        allow: "rgb(var(--allow-rgb) / <alpha-value>)",
        ask: "rgb(var(--ask-rgb) / <alpha-value>)",
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: { base: "13px" },
      borderRadius: { DEFAULT: "6px" },
      transitionDuration: { DEFAULT: "150ms" },
      transitionTimingFunction: { DEFAULT: "ease-out" },
    },
  },
  plugins: [],
} satisfies Config;
