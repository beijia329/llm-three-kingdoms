import type { GameEvent } from '../types'

interface EventTickerProps {
  events: GameEvent[]
}

export function EventTicker({ events }: EventTickerProps) {
  const recent = events.slice(-4)

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        <i className="fa-solid fa-bullhorn" style={{ color: '#d4a84b', fontSize: '11px', marginRight: '8px', flexShrink: 0 }}></i>
        <div style={styles.scrollArea}>
          {recent.map((evt, idx) => (
            <span key={idx} style={styles.item}>
              <span style={{ color: '#5a5a72', marginRight: '4px' }}>[第{evt.turn}回合]</span>
              {evt.text}
            </span>
          ))}
          {recent.length === 0 && (
            <span style={{ color: '#5a5a72', fontSize: '12px' }}>等待游戏开始...</span>
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
  },
}
