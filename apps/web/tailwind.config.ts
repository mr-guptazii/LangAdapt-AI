import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#05070d",
          900: "#0a0e1a",
          800: "#0f1524",
          700: "#161d31",
          600: "#212a42",
        },
        cyan: {
          400: "#5eead4",
          500: "#2dd4bf",
          600: "#14b8a6",
        },
        gold: {
          300: "#f5d896",
          400: "#eec267",
          500: "#dba43e",
        },
        cream: "#f4ecd8",
      },
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        sans: ["var(--font-sans)", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(45, 212, 191, 0.25)",
        "glow-gold": "0 0 24px rgba(238, 194, 103, 0.2)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(94,234,212,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(94,234,212,0.06) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      keyframes: {
        "pulse-soft": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.55" } },
        float: { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: {
        "pulse-soft": "pulse-soft 2.4s ease-in-out infinite",
        float: "float 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
