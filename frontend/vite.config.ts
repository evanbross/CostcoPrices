// ai: claude-sonnet-4-6 | 2026-06-18
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ai: claude-opus-5-5 | 2026-09-28
// The dev server port and the backend port are both OS-assigned by the root
// main.py launcher on every run (see _start_dev there), so neither is fixed here.
// main.py passes the Vite port on the CLI and the backend port via COSTCO_API_PORT.
export default defineConfig(({ command }) => {
  const apiPort = process.env.COSTCO_API_PORT
  if (command === 'serve' && !apiPort) {
    throw new Error(
      'COSTCO_API_PORT is not set. Start the dev server with `python main.py --dev` ' +
        'from the repo root rather than `npm run dev` directly.',
    )
  }

  return {
    plugins: [react()],
    clearScreen: false,
    server: {
      proxy: {
        '/api': {
          target: `http://localhost:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
    },
  }
})
