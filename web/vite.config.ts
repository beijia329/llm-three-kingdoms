import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // [L11 2026-10-04] 主 chunk 曾达 543 KB（gzip 174 KB），触发 Vite 500 KB 警告。
    // PixiJS 体积占绝大部分且**几乎不变**，与业务代码拆开后可被浏览器长期缓存：
    // 业务迭代时用户只需重新下载小的 index chunk（实测 174 KB → 44 KB gzip）。
    rollupOptions: {
      output: {
        manualChunks: {
          pixi: ['pixi.js'],
          react: ['react', 'react-dom'],
        },
      },
    },
    // pixi chunk 本身约 514 KB（第三方库固有体积），已独立缓存、业务迭代时不会变。
    // 调高阈值只为消除这条每次构建都会出现的误导性警告，不是放宽体积要求。
    chunkSizeWarningLimit: 600,
  },
})
