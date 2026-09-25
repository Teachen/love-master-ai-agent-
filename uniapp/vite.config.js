import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// uni-app + Vue3 + Vite 官方构建配置
// 文档：https://uniapp.dcloud.net.cn/vite/
export default defineConfig({
  plugins: [uni()],
  server: {
    port: 5173,
    // H5 开发期跨域兜底：后端已配置 CORS（cors_origins=["*"]），
    // 这里保留代理作为可选方案，默认直连后端（见 src/config/index.js）。
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
