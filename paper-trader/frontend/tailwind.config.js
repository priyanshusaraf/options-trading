// ESM config ("type": "module") — tailwindcss-animate must be imported, not require()d.
import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── existing palette (every un-migrated view depends on these) ──
        bg: '#0a0b0e',
        panel: '#121419',
        panel2: '#171a21',
        edge: '#232733',
        up: '#2ebd85',
        down: '#f6465d',
        // `muted` predates shadcn and is used app-wide as `text-muted`. It is MERGED,
        // not replaced: DEFAULT stays the original grey so `text-muted` renders
        // identically everywhere, while `foreground` adds the token shadcn's
        // primitives expect (`text-muted-foreground`). Mapping DEFAULT onto
        // shadcn's dark `--muted` would turn every `text-muted` label in the app
        // dark-on-dark.
        muted: { DEFAULT: '#8b93a7', foreground: 'hsl(var(--muted-foreground))' },

        // ── shadcn/ui tokens (additive; drive src/components/ui/*) ──
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
