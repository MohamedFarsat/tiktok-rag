import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f6f2ea",
        ink: "#1f2430",
        muted: "#5f6775",
        line: "#d8d1c6",
        accent: "#2f5d62"
      },
      boxShadow: {
        soft: "0 18px 40px -24px rgba(31, 36, 48, 0.35)"
      }
    }
  },
  plugins: []
};

export default config;
