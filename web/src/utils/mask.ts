import type { CSSProperties } from 'react'

/**
 * 单一 mask 工具（技术债合并，2026-10-04）。
 *
 * 背景：此前 `maskStyle()` 在 CityMarker / ArmyMarker 各写一份，另有 3 处内联写法
 * （BattleOverlay / GameOverOverlay / EventTicker）——5 处分散，导致「生产构建 mask URL
 * 未加引号」那次只修了 2 处、漏了 4 处。现收敛为唯一实现。
 *
 * 🔴 `url()` **必须带引号**：生产构建下 Vite 会把小 SVG 内联成 `data:image/svg+xml,...'...'`
 *    （URI 内含单引号），而 CSS 规定未加引号的 `url()` 不得含引号 → 声明非法 →
 *    浏览器丢弃 `mask-image` → 图标只剩 background-color，渲染成实心方块。
 *    （另在 vite.config 设 `assetsInlineLimit: 0` 做双保险。）
 *
 * @param url   SVG 资产 URL（import 得到）
 * @param color CSS 颜色（染成该色的剪影）
 * @param size  像素尺寸（宽=高）
 */
export function maskStyle(url: string, color: string, size: number): CSSProperties {
  return {
    width: `${size}px`,
    height: `${size}px`,
    backgroundColor: color,
    maskImage: `url("${url}")`,
    WebkitMaskImage: `url("${url}")`,
    maskSize: 'contain',
    WebkitMaskSize: 'contain',
    maskRepeat: 'no-repeat',
    WebkitMaskRepeat: 'no-repeat',
    maskPosition: 'center',
    WebkitMaskPosition: 'center',
    display: 'block',
  }
}
