import type { GameState } from '../types'
import { FACTIONS } from '../utils/colors'

interface TopBarProps {
  state: GameState | null
  connected: boolean
}

export function TopBar({ state, connected }: TopBarProps) {
  if (!state) {
    return (
      <div style={styles.container}>
        <span style={styles.title}>LLM三国志 - 加载中...</span>
      </div>
    )
  }

  const seasonMap: Record<string, string> = {
    spring: '春',
    summer: '夏',
    autumn: '秋',
    winter: '冬',
  }
  const season = seasonMap[state.season] || ''
  const mode = state.max_turns > 9000 ? '∞' : `/${state.max_turns}`

  const topFactions = Object.entries(state.faction_stats)
    .sort((a, b) => b[1].cities - a[1].cities)
    .slice(0, 5)

  return (
    <div style={styles.container}>
      <div style={styles.left}>
        <span style={styles.title}>
          第 {state.turn}{mode} 回合 | {state.year}年 {season} | 黄巾之乱
        </span>
        <div style={styles.stats}>
          {topFactions.map(([fid, s]) => (
            <span key={fid} style={styles.statItem}>
              {FACTIONS[fid] || fid}{s.cities}城
            </span>
          ))}
        </div>
      </div>
      <div style={styles.right}>
        <span style={{ ...styles.indicator, color: connected ? '#5ab464' : '#c85046' }}>
          {connected ? '● 已连接' : '● 未连接'}
        </span>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: 'calc(100% - 300px)',
    height: '50px',
    background: 'rgba(18, 18, 34, 0.92)',
    borderBottom: '1px solid #3c3c52',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    boxSizing: 'border-box',
    zIndex: 10,
  },
  left: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
  },
  title: {
    color: '#d4a84b',
    fontSize: '16px',
    fontWeight: 600,
  },
  stats: {
    display: 'flex',
    gap: '12px',
    marginTop: '2px',
  },
  statItem: {
    color: '#96918a',
    fontSize: '12px',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
  },
  indicator: {
    fontSize: '12px',
  },
}
