import { useState } from 'react'
import type { GameState } from '../types'
import { FACTION_COLORS, FACTIONS } from '../theme'

interface GameOverOverlayProps {
  state: GameState
  /** 关闭结算层回到棋盘（棋盘本身仍可查看） */
  onDismiss: () => void
}

/**
 * 胜负结算界面。
 *
 * 🔴 为什么必须有：后端一直返回 `game_over` / `winner`，但前端**零处引用**
 * （审计 §1），对局结束后界面纹丝不动继续显示棋盘 —— 观众根本不知道谁赢了。
 * 本组件把这两个字段接成真功能：明确显示胜者、其城池数、以及各势力最终排名。
 */
export function GameOverOverlay({ state, onDismiss }: GameOverOverlayProps) {
  const [showBoard, setShowBoard] = useState(false)
  if (showBoard) return null

  const winnerId = state.winner
  const winnerName = winnerId ? (FACTIONS[winnerId] || winnerId) : null
  const winnerColor = winnerId ? (FACTION_COLORS[winnerId] || '#d4a84b') : '#d4a84b'
  const winnerCities = winnerId ? (state.faction_stats[winnerId]?.cities ?? 0) : 0

  // 最终排名：存活势力按城池数降序（已出局势力排在后）
  const ranking = Object.entries(state.faction_stats)
    .map(([fid, s]) => ({ fid, ...s }))
    .sort((a, b) => b.cities - a.cities || a.name.localeCompare(b.name, 'zh-CN'))

  const reason = state.turn >= state.max_turns ? '回合耗尽' : '一统天下'

  return (
    <div style={styles.backdrop}>
      <div style={styles.card}>
        <div style={{ fontSize: '44px', lineHeight: 1 }}>{winnerId ? '🏆' : '🤝'}</div>
        <div style={{ ...styles.headline, color: winnerColor }}>
          {winnerName ? `${winnerName} 一统天下` : '天下未定 · 平局'}
        </div>
        <div style={styles.sub}>
          第 {state.turn} / {state.max_turns} 回合 · {reason}
          {winnerId && ` · 坐拥 ${winnerCities} 城`}
        </div>

        <div style={styles.rankList}>
          {ranking.slice(0, 6).map((row, i) => (
            <div key={row.fid} style={styles.rankRow}>
              <span style={styles.rankNo}>{i + 1}</span>
              <span
                style={{
                  width: '9px', height: '9px', borderRadius: '50%',
                  background: FACTION_COLORS[row.fid] || '#888', flexShrink: 0,
                }}
              />
              <span style={{ color: row.is_alive === false ? '#6b6b80' : '#e8e0d0', flex: 1, textAlign: 'left' }}>
                {row.name}
                {row.is_alive === false && <span style={styles.deadTag}>已出局</span>}
              </span>
              <span style={{ color: '#a8a29a' }}>{row.cities} 城</span>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '10px', marginTop: '18px' }}>
          <button style={styles.btn} onClick={() => setShowBoard(true)}>
            <i className="fa-solid fa-chess-board" style={{ marginRight: '6px' }}></i>
            查看棋盘
          </button>
          <button style={{ ...styles.btn, ...styles.btnGhost }} onClick={onDismiss}>
            <i className="fa-solid fa-xmark" style={{ marginRight: '6px' }}></i>
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: 'absolute',
    inset: 0,
    zIndex: 100,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(10, 10, 22, 0.72)',
    backdropFilter: 'blur(6px)',
  },
  card: {
    width: '380px',
    padding: '28px 26px',
    borderRadius: '16px',
    background: 'rgba(24, 24, 40, 0.96)',
    border: '1px solid rgba(212, 168, 75, 0.4)',
    boxShadow: '0 24px 80px rgba(0, 0, 0, 0.6)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
  },
  headline: {
    fontSize: '24px',
    fontWeight: 700,
    marginTop: '12px',
  },
  sub: {
    fontSize: '12px',
    color: '#a8a29a',
    marginTop: '6px',
  },
  rankList: {
    width: '100%',
    marginTop: '18px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  rankRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    padding: '5px 8px',
    borderRadius: '6px',
    background: 'rgba(255,255,255,0.03)',
  },
  rankNo: {
    width: '16px',
    color: '#d4a84b',
    fontWeight: 600,
    fontSize: '12px',
  },
  deadTag: {
    marginLeft: '6px',
    fontSize: '10px',
    color: '#c85046',
    border: '1px solid rgba(200,80,70,0.5)',
    borderRadius: '4px',
    padding: '0 4px',
  },
  btn: {
    padding: '9px 16px',
    borderRadius: '8px',
    border: '1px solid rgba(212, 168, 75, 0.5)',
    background: 'rgba(212, 168, 75, 0.15)',
    color: '#d4a84b',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  btnGhost: {
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'transparent',
    color: '#a8a29a',
  },
}
