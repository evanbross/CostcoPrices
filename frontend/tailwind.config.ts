// ai: claude-sonnet-4-6 | 2026-06-18
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        costco: {
          red: '#E31837',
          'red-dark': '#B8122D',
          blue: '#003087',
          'blue-dark': '#00205B',
          gold: '#B8860B',
          'light-gray': '#F5F5F5',
          'border-gray': '#E0E0E0',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
