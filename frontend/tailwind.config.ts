import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        bullish: {
          light: "#f0fdf4",
          DEFAULT: "#16a34a",
          dark: "#15803d",
        },
        bearish: {
          light: "#fef2f2",
          DEFAULT: "#dc2626",
          dark: "#b91c1c",
        },
      },
    },
  },
  plugins: [],
};
export default config;
