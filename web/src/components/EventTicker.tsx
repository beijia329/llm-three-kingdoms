import type { GameEvent } from '../types'

interface EventTickerProps {
  events: GameEvent[]
}

export function EventTicker({ events }: EventTickerProps) {
  const recent = events.slice(-4)

  return (
    <div style={styles.container}>
      {recent.map((evt, idx) => (
        <span key={idx} style={styles.item}>
          ▸ {evt.text}
        </span>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    bottom: '60px',
    left: '16px',
    right: '316px',
    height: '30px',
    background: 'rgba(18, 18, 34, 0.88)',
    borderTop: '1px solid #3c3c52',
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    padding: '0 12px',
    overflow: 'hidden',
    zIndex: 10,
  },
  item: {
    color: '#e8e0d0',
    fontSize: '12px',
    whiteSpace: 'nowrap',
  },
}
