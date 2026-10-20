import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, /api is proxied to FastAPI so the browser sees one origin.
// In production, nginx does the same (see frontend/nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
