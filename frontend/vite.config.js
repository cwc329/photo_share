import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    // 不需要 proxy：前端直接呼叫 VITE_API_BASE_URL（開發時為 http://localhost:8001）
    // 後端 CORS 已設定允許 localhost:5173，withCredentials 確保 cookie 正確傳遞
    allowedHosts: ['photo-share-beta.cwc329.com'],
  },
})
