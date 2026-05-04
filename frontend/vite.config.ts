import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          if (id.includes('echarts-for-react')) {
            return 'echarts-react'
          }

          if (id.includes('zrender')) {
            return 'zrender-vendor'
          }

          if (id.includes('echarts')) {
            return 'echarts-vendor'
          }

          if (id.includes('leaflet')) {
            return 'leaflet-vendor'
          }
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})
