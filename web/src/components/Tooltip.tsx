import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * 全局悬浮提示（hover popover）
 *
 * 背景（审计 §4-3「单位/城池 hover 悬浮卡」）：此前全站只有零星原生 `title`，
 * 且地图标记在**被 CSS transform 缩放**的覆盖层里 —— 若把提示直接渲染在标记内部，
 * 提示文字也会被一起缩放/裁切。故这里用 **portal 到 document.body + position: fixed**
 * 渲染，位置由 `getBoundingClientRect()` 计算，天然不受父级 transform、overflow 影响。
 *
 * 用法二选一：
 *   · 结构未知/只是想包一层：`<Hint title="…" lines={[…]}>{children}</Hint>`
 *   · 已有一个元素要直接挂事件（如地图标记 div）：`useTooltip()` + `hintProps(content)`
 */
export interface TipContent {
  title?: string
  lines: string[]
}

interface TipState extends TipContent {
  x: number
  y: number
  above: boolean
}

interface TooltipApi {
  show: (el: HTMLElement, content: TipContent) => void
  hide: () => void
}

const TooltipContext = createContext<TooltipApi | null>(null)

const TIP_HALF_WIDTH = 130

export function TooltipProvider({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<TipState | null>(null)

  const show = useCallback((el: HTMLElement, content: TipContent) => {
    const r = el.getBoundingClientRect()
    // 上方空间够就向上弹，否则向下 —— 避免顶部被裁掉
    const above = r.top > 96
    setTip({
      ...content,
      x: r.left + r.width / 2,
      y: above ? r.top - 8 : r.bottom + 8,
      above,
    })
  }, [])

  const hide = useCallback(() => setTip(null), [])
  const api = useMemo<TooltipApi>(() => ({ show, hide }), [show, hide])

  // 窗口缩放/滚动时旧坐标会失效，直接收起，避免提示"漂"在错位处
  useEffect(() => {
    if (!tip) return
    const off = () => setTip(null)
    window.addEventListener('resize', off)
    window.addEventListener('scroll', off, true)
    return () => {
      window.removeEventListener('resize', off)
      window.removeEventListener('scroll', off, true)
    }
  }, [tip])

  const clampedX = tip
    ? Math.min(Math.max(tip.x, TIP_HALF_WIDTH + 4), Math.max(TIP_HALF_WIDTH + 4, window.innerWidth - TIP_HALF_WIDTH - 4))
    : 0

  return (
    <TooltipContext.Provider value={api}>
      {children}
      {tip &&
        createPortal(
          <div
            role="tooltip"
            style={{
              position: 'fixed',
              left: clampedX,
              top: tip.y,
              transform: tip.above ? 'translate(-50%, -100%)' : 'translate(-50%, 0)',
              zIndex: 9999,
              maxWidth: '260px',
              padding: '7px 10px',
              background: 'rgba(10, 20, 26, 0.97)',
              border: '1px solid rgba(200, 168, 90, 0.45)',
              borderRadius: '6px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.55)',
              color: 'var(--text)',
              fontSize: '11px',
              lineHeight: 1.6,
              pointerEvents: 'none',
              whiteSpace: 'normal',
            }}
          >
            {tip.title && (
              <div style={{ color: 'var(--gold)', fontWeight: 600, marginBottom: tip.lines.length ? '3px' : 0 }}>
                {tip.title}
              </div>
            )}
            {tip.lines.map((l, i) => (
              <div key={i} style={{ color: '#c9c3b8' }}>{l}</div>
            ))}
          </div>,
          document.body,
        )}
    </TooltipContext.Provider>
  )
}

/** 取悬浮提示 API；未包 Provider 时返回空实现（组件不崩） */
export function useTooltip(): TooltipApi {
  const ctx = useContext(TooltipContext)
  return ctx ?? { show: () => {}, hide: () => {} }
}

/**
 * 返回可直接展开到元素上的事件处理器。
 * `content` 为函数时按需生成（避免每次渲染都构造字符串数组）。
 */
export function useHintProps(content: TipContent | (() => TipContent)) {
  const { show, hide } = useTooltip()
  return useMemo(() => {
    const resolve = () => (typeof content === 'function' ? content() : content)
    return {
      onMouseEnter: (e: React.MouseEvent<HTMLElement>) => show(e.currentTarget, resolve()),
      onMouseLeave: () => hide(),
    }
  }, [show, hide, content])
}

/** 便捷包裹组件：给任意内联内容挂一个悬浮提示 */
export function Hint({
  content,
  children,
  style,
}: {
  content: TipContent
  children: ReactNode
  style?: CSSProperties
}) {
  const handlers = useHintProps(content)
  return (
    <span {...handlers} style={{ cursor: 'help', ...style }}>
      {children}
    </span>
  )
}
