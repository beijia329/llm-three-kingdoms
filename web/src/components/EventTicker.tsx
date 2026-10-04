import type { GameEvent } from '../types'
// [H2 2026-10-04] 事件正文是否自带回合号
import { hasTurnInText } from '../utils/eventTurn'
import { GAP_PANEL } from '../theme'
import { usePanelWidth } from '../hooks/usePanelWidth'
// [阶段A] 接入已下载的 game-icons 素材（scroll-quill，CC BY 3.0）。
// 用 CSS mask 着色，保留矢量 + 随字色变色。
import scrollQuill from '../assets/icons/scroll-quill.svg'
// [阶段B] 事件流用霞鹜文楷（局部按需，见 utils/wenKai.ts）
import { useWenKai, WENKAI_STACK } from '../utils/wenKai'
// 技术债合并：mask 样式走单一实现（见 utils/mask.ts）
import { maskStyle } from '../utils/mask'

interface EventTickerProps {
  events: GameEvent[]
}

export function EventTicker({ events }: EventTickerProps) {
  const recent = events.slice(-4)
  // [M4] 与面板同一事实源的右偏移（面板宽度响应式）
  const panelW = usePanelWidth()
  // 只有真的有事件要显示时才拉字体（空态不拉）
  useWenKai(events.length > 0)

  return (
    <div style={{ ...styles.container, right: panelW + GAP_PANEL }}>
      <div style={styles.inner}>
        <span
          aria-hidden
          style={{
            ...maskStyle(scrollQuill, 'var(--gold)', 14),
            flexShrink: 0,
            marginRight: '8px',
            display: 'inline-block',
          }}
        />
        <div style={styles.scrollArea}>
          {recent.map((evt, idx) => (
            <span key={idx} style={styles.item}>
              {/* [H2 2026-10-04] 正文自带回合号时不再补前缀（同 Panel.tsx） */}
              {!hasTurnInText(evt.text) && (
                <span style={{ color: 'var(--text-muted)', marginRight: '4px' }}>[第{evt.turn}回合]</span>
              )}
              {evt.text}
            </span>
          ))}
          {recent.length === 0 && (
            <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>等待游戏开始...</span>
          )}
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    bottom: '14px',
    left: '14px',
    // right 由 usePanelWidth() 在渲染时注入（[M4] 面板宽度响应式）
    height: '36px',
    background: 'rgba(20, 32, 40, 0.82)',
    border: '1px solid var(--panel-border)',
    borderRadius: '6px',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
    display: 'flex',
    alignItems: 'center',
    padding: '0 12px',
  },
  inner: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    overflow: 'hidden',
  },
  scrollArea: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    overflow: 'hidden',
    whiteSpace: 'nowrap',
  },
  item: {
    color: 'var(--text)',
    fontSize: '12px',
    whiteSpace: 'nowrap',
    flexShrink: 0,
    fontFamily: WENKAI_STACK,
  },
}
