import { useEffect } from 'react'

/**
 * 霞鹜文楷（LXGW WenKai）**按需局部加载**（阶段B 2026-10-03）
 *
 * team-lead 决策：**不做全局字体替换**——全局保持系统衬线栈（"Songti SC","STSong",serif），
 * 理由是「零请求、零延迟、零体积」，而目标场景是本机/局域网围观。
 * 霞鹜文楷只用于**「事件流」与「决策正文」**这两处「读故事的界面」，且**按需**加载。
 *
 * 用的是 cn-font-split 生成的分包 CSS（按 unicode-range 切成上千个 woff2 分片），
 * 浏览器只会下载**实际用到汉字**所在的分片，所以只对该两处的文本生效时开销可控。
 *
 * ⚠️ 依赖公网 CDN（jsdelivr）。离线/内网部署时加载失败会**静默回退**到系统字体，
 *    不影响功能。生产分发建议改为自托管这些分片（同 `assets/` 一起发）。
 */
const HREF =
  'https://cdn.jsdelivr.net/npm/@chinese-fonts/lxgwwenkai@3.0.0/dist/LXGWWenKai-Regular/result.css'

/** 供文本元素使用的字体栈：优先霞鹜文楷，缺字回退 Noto/系统 */
export const WENKAI_STACK = '"LXGW WenKai", "Noto Sans SC", "Songti SC", serif'

let injected = false

/** 幂等地注入字体样式表（只在首次有内容时调用） */
export function ensureWenKai(): void {
  if (injected || typeof document === 'undefined') return
  injected = true
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = HREF
  link.crossOrigin = 'anonymous'
  document.head.appendChild(link)
}

/**
 * 只有当 `enabled` 为真（该组件真的有内容要显示）时才注入字体 CSS。
 * 这样首屏（还没回合内容时）不会因为字体而多请求。
 */
export function useWenKai(enabled: boolean): void {
  useEffect(() => {
    if (enabled) ensureWenKai()
  }, [enabled])
}
