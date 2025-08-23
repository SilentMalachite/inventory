import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

// Build to backend public directory so FastAPI + PyInstaller can serve it
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: {
    outDir: resolve(__dirname, '../src/app/public'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to FastAPI during dev if needed
      '/items': 'http://127.0.0.1:8000',
      '/stock': 'http://127.0.0.1:8000'
    }
  }
})

