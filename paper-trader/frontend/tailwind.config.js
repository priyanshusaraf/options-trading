/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0b0e',
        panel: '#121419',
        panel2: '#171a21',
        edge: '#232733',
        up: '#2ebd85',
        down: '#f6465d',
        muted: '#8b93a7',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
