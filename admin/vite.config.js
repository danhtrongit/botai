import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// SPA admin phục vụ dưới /admin/ (FastAPI serve admin/dist).
export default defineConfig({
  base: '/admin/',
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5174,
    proxy: {
      // Dev: chuyển API + auth về backend FastAPI.
      '/admin/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/admin/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
