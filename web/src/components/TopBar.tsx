import type { GameState } from '../types'
import { FACTIONS, GAP_PANEL, PANEL_W } from '../theme'

interface TopBarProps {
  state: GameState | null
  connected: boolean
}

export function TopBar({ state, connected }: TopBarProps) {
  if (!state) {
    return (
      <div style={styles.container}>
        <span style={styles.title}>
          <i className="fa-solid fa-dragon" style={{ marginRight: '8px', color: '#d4a84b' }}></i>
          乱斗三国 - 加载中...
        </span>
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
        <span style={styles.title} className="font-serif">
          <i className="fa-solid fa-dragon" style={{ marginRight: '8px' }}></i>
          第 {state.turn}{mode} 回合 | {state.year}年 {season}
        </span>
        <div style={styles.stats}>
          {topFactions.map(([fid, s]) => (
            <span key={fid} style={styles.statItem}>
              <i className="fa-solid fa-chess-rook" style={{ marginRight: '3px', fontSize: '9px' }}></i>
              {FACTIONS[fid] || fid}{s.cities}城
            </span>
          ))}
        </div>
      </div>
      <div style={styles.right}>
        <span style={{ ...styles.indicator, color: connected ? '#5ab464' : '#c85046' }}>
          <i className="fa-solid fa-circle" style={{ fontSize: '8px', marginRight: '5px' }}></i>
          {connected ? '已连接' : '未连接'}
        </span>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: 'absolute',
    top: '12px',
    left: '12px',
    right: PANEL_W + GAP_PANEL, // [M5] 由面板宽度推导（原魔数 324）
    height: '50px',
    background: 'rgba(18, 18, 34, 0.82)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '10px',
    backdropFilter: 'blur(12px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    boxSizing: 'border-box',
    // [L12] 与 stats 的 overflow 配合，保证顶栏不撑破布局
    overflow: 'hidden',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
  },
  left: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
  },
  title: {
    color: '#d4a84b',
    fontSize: '15px',
    fontWeight: 600,
    display: 'flex',
    alignItems: 'center',
  },
  stats: {
    display: 'flex',
    gap: '12px',
    marginTop: '2px',
    // [L12 2026-10-04] 极窄窗口下（实测 900px 宽时顶栏仅剩 264px）5 个势力统计会被
    // flex 挤压变形。这里禁止换行 + 允许裁切：宁可少显示几个，也不要把文字压成一团。
    // 完整势力数据在右侧面板，不受影响。
    flexWrap: 'nowrap',
    minWidth: 0,
    overflow: 'hidden',
  },
  statItem: {
    color: '#a8a29a', // 阶段A：提亮，#96918a → 深底上更清晰
    fontSize: '11px',
    display: 'flex',
    alignItems: 'center',
    whiteSpace: 'nowrap',
    flexShrink: 0,
  },
  right: {
    display: 'flex',
    alignItems: 'center',
  },
  indicator: {
    fontSize: '12px',
    display: 'flex',
    alignItems: 'center',
  },
}
