import type { GameEvent } from '../types'
// [阶段A] 接入已下载的 game-icons 素材（scroll-quill，CC BY 3.0）。
// 用 CSS mask 着色，保留矢量 + 随字色变色。
import scrollQuill from '../assets/icons/scroll-quill.svg'
// [阶段B] 事件流用霞鹜文楷（局部按需，见 utils/wenKai.ts）
import { useWenKai, WENKAI_STACK } from '../utils/wenKai'

interface EventTickerProps {
  events: GameEvent[]
}

export function EventTicker({ events }: EventTickerProps) {
  const recent = events.slice(-4)
  // 只有真的有事件要显示时才拉字体（空态不拉）
  useWenKai(events.length > 0)

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        <span
          aria-hidden
          style={{
            width: '14px',
            height: '14px',
            flexShrink: 0,
            marginRight: '8px',
            backgroundColor: '#d4a84b',
            maskImage: `url(${scrollQuill})`,
            WebkitMaskImage: `url(${scrollQuill})`,
            maskSize: 'contain',
            WebkitMaskSize: 'contain',
            maskRepeat: 'no-repeat',
            WebkitMaskRepeat: 'no-repeat',
            maskPosition: 'center',
            WebkitMaskPosition: 'center',
            display: 'inline-block',
          }}
        />
        <div style={styles.scrollArea}>
          {recent.map((evt, idx) => (
            <span key={idx} style={styles.item}>
              <span style={{ color: '#8a86a0', marginRight: '4px' }}>[第{evt.turn}回合]</span>
              {evt.text}
            </span>
          ))}
          {recent.length === 0 && (
            <span style={{ color: '#8a86a0', fontSize: '12px' }}>等待游戏开始...</span>
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
    right: '330px',
    height: '36px',
    background: 'rgba(18, 18, 34, 0.82)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '10px',
    backdropFilter: 'blur(12px)',
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
    color: '#e8e0d0',
    fontSize: '12px',
    whiteSpace: 'nowrap',
    flexShrink: 0,
    fontFamily: WENKAI_STACK,
  },
}
