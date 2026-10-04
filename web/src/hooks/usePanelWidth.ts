import { useEffect, useState } from 'react'
import { responsivePanelWidth, PANEL_W } from '../theme'

/**
 * 右侧面板的**运行期宽度**（M4 响应式，2026-10-04）。
 *
 * 面板宽度会随视口变化（≥1440→420 / 1200–1439→360 / <1200→300），而所有浮层的
 * `right` 偏移必须与面板实际宽度**同一事实源**——否则一改宽度，顶栏/事件流/
 * 「下一回合」按钮/自动推进条四处全错位（v4.2.0 的 M5 教训）。
 *
 * 用法：App / TopBar / EventTicker / Panel 都调本 hook 取同一个值。
 */
export function usePanelWidth(): number {
  const [w, setW] = useState<number>(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1440,
  )
  useEffect(() => {
    const onResize = () => setW(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return responsivePanelWidth(w || PANEL_W)
}
