import { useState } from 'react'
import type { GameState } from '../types'
import { FACTION_COLORS } from '../theme'

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
  const winnerColor = winnerId ? (FACTION_COLORS[winnerId] || 'var(--gold)') : 'var(--gold)'
  const winnerCities = winnerId ? (state.faction_stats[winnerId]?.cities ?? 0) : 0

  // 最终排名：存活势力按城池数降序（已出局势力排在后）
  const ranking = Object.entries(state.faction_stats)
    .map(([fid, s]) => ({ fid, ...s }))
    .sort((a, b) => b.cities - a.cities || a.name.localeCompare(b.name, 'zh-CN'))

  // v4.3.0（D1 单一真源）：标题/副标题**verbatim 渲染后端下发的
  // `end_title` / `end_subtitle`**（真源在 game.end_copy.format_end_copy）。
  // 🔴 前端**不做任何 reason→文案映射**（含旧档回退推断）—— 否则又是三处漂移。
  // `end_reason` 仅用于**图标选择**（icon 不是文案映射）。
  const endReason = state.end_reason
  const icon = !winnerId ? '🤝' : endReason === 'unification' ? '🏆' : endReason === 'stalemate' ? '⚖️' : '⏳'

  return (
    <div style={styles.backdrop}>
      <div style={styles.card}>
        <div style={{ fontSize: '44px', lineHeight: 1 }}>{icon}</div>
        <div style={{ ...styles.headline, color: winnerColor }}>
          {state.end_title}
        </div>
        <div style={styles.sub}>
          {state.end_subtitle}
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
              <span style={{ color: row.is_alive === false ? '#6b6b80' : 'var(--text)', flex: 1, textAlign: 'left' }}>
                {row.name}
                {row.is_alive === false && <span style={styles.deadTag}>已出局</span>}
              </span>
              <span style={{ color: 'var(--text-2)' }}>{row.cities} 城</span>
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
    background: 'rgba(10, 20, 26, 0.72)',
  },
  card: {
    width: '460px',
    padding: '30px 28px',
    borderRadius: '6px',
    background: 'rgba(20, 32, 40, 0.96)',
    border: '1px solid rgba(200, 168, 90, 0.4)',
    boxShadow: '0 24px 80px rgba(0, 0, 0, 0.6)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
  },
  headline: {
    fontSize: '28px',
    fontWeight: 700,
    marginTop: '12px',
    fontFamily: 'var(--font-serif)',
  },
  sub: {
    fontSize: '12px',
    color: 'var(--text-2)',
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
    color: 'var(--gold)',
    fontWeight: 600,
    fontSize: '12px',
  },
  deadTag: {
    marginLeft: '6px',
    fontSize: '10px',
    color: 'var(--red)',
    border: '1px solid rgba(157,41,51,0.5)',
    borderRadius: '4px',
    padding: '0 4px',
  },
  btn: {
    padding: '9px 16px',
    borderRadius: '6px',
    border: '1px solid rgba(200, 168, 90, 0.5)',
    background: 'rgba(200, 168, 90, 0.15)',
    color: 'var(--gold)',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  btnGhost: {
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'transparent',
    color: 'var(--text-2)',
  },
}
