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
    // [M2 修复 2026-10-04] 禁止把小于阈值的资源内联成 data URI。
    // 根因：Vite 会把 <4KB 的 SVG 内联成 `data:image/svg+xml,%3csvg ... '...'`，
    // 其中**含单引号**；而 CSS 的 `url()` 若**未加引号**则不允许内部出现引号 →
    // 声明非法 → 浏览器丢弃 mask-image → 图标只剩 background-color 变实心方块
    // （仅生产构建复现，dev 下是文件路径 URL 看不出来）。
    // 置 0 = 所有资源走独立文件 URL，从机理上消除该问题；同时源码侧 url() 已统一加引号。
    assetsInlineLimit: 0,
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
