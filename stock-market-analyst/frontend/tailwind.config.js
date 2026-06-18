/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0f1117",
          1: "#161b22",
          2: "#1c2230",
          3: "#222b3d",
        },
        accent: {
          green: "#00d17a",
          red: "#ff4f5a",
          blue: "#4e9eff",
          gold: "#f5c842",
          purple: "#9b6dff",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
