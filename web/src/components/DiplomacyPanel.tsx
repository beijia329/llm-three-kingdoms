import type { GameState, DiplomacyMessage } from '../types'
import { FACTIONS, FACTION_COLORS, UI_COLORS } from '../theme'
import { useState } from 'react'
import {
  RelationGraph,
  RelationMatrix,
  REL_STATUS_COLOR as statusColor,
  REL_STATUS_LABEL as statusLabel,
  topRelations,
} from './DiplomacyGraph'

interface DiplomacyPanelProps {
  state: GameState
}

export function DiplomacyPanel({ state }: DiplomacyPanelProps) {
  const [activeTab, setActiveTab] = useState<'relations' | 'messages' | 'send'>('relations')
  // [M4 2026-10-04] 外交关系视图二选一：环形图 / 关系矩阵 —— 一次只渲染一个、各得满高。
  // 依据 M4-measurements.json：环形图 + 战况摘要 + 12×12 矩阵三者同屏在 300px 窄栏里
  // 纵向溢出 157px（矩阵底部被截断需滚动）。二选一后不再叠加溢出。
  const [view, setView] = useState<'ring' | 'matrix'>('ring')
  // 战况摘要默认折叠（M4 可选做强）
  const [showSummary, setShowSummary] = useState(false)
  const relations = state.faction_relations || []
  const messages = state.messages || []
  const humanFaction = state.human_faction

  // 发送消息
  const [targetFaction, setTargetFaction] = useState('')
  const [msgContent, setMsgContent] = useState('')

  // 获取 WebSocket（简单方式：从全局查找）
  const sendMessage = () => {
    if (!humanFaction || !targetFaction || !msgContent.trim()) return
    // 通过 window 上的 ws 发送（App.tsx 中暴露）
    const ws = (window as any).__gameWS
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'command',
        command: {
          type: 'message',
          faction: humanFaction,
          turn: state.turn,
          params: { to: targetFaction, content: msgContent.trim() },
        },
      }))
      setMsgContent('')
    }
  }

  // 关系矩阵：只显示当前势力与其他势力的关系
  const myRelations = humanFaction
    ? relations.filter(r => r.faction_a === humanFaction || r.faction_b === humanFaction)
    // [阶段D] 观战模式（无人类势力）下原来取 relations.slice(0,12) —— 那是**前 12 条**，
    // 实际全是「汉室↔X」，看不出战局。改成按关系强度排序的真实战况摘要。
    : topRelations(state, 8)

  return (
    <div style={{ padding: '12px', overflowY: 'auto', height: '100%' }}>
      {/* Tab 切换 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        {(['relations', 'messages', 'send'] as const).map(t => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            style={{
              flex: 1,
              padding: '6px 0',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === t ? 'rgba(200,168,90,0.2)' : 'rgba(255,255,255,0.05)',
              color: activeTab === t ? 'var(--gold)' : UI_COLORS.textSecondary,
              fontSize: '12px',
              cursor: 'pointer',
            }}
          >
            {t === 'relations' ? '关系' : t === 'messages' ? '消息' : '发送'}
          </button>
        ))}
      </div>

      {activeTab === 'relations' && (
        <div>
          <div style={{ fontSize: '13px', color: 'var(--gold)', marginBottom: '10px', fontFamily: 'var(--font-serif)' }}>
            势力外交关系
          </div>
          {/* [M4] 视图开关：环形图 / 关系矩阵 二选一（一次只渲染一个） */}
          <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
            {(['ring', 'matrix'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                style={{
                  flex: 1,
                  padding: '5px 0',
                  borderRadius: '6px',
                  border: '1px solid ' + (view === v ? 'var(--panel-border)' : 'transparent'),
                  background: view === v ? 'rgba(200,168,90,0.18)' : 'rgba(255,255,255,0.04)',
                  color: view === v ? 'var(--gold)' : UI_COLORS.textSecondary,
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                {v === 'ring' ? '环形图' : '关系矩阵'}
              </button>
            ))}
          </div>

          {/* [阶段D 2026-10-03] 关系图：README 把「外交博弈」列为头部特性，
              但原界面只有列表 + 无行列标的 24 格色块 → 卖点看不见。这里补环形关系图。
              [M4] 与矩阵二选一，各得满高；矩阵连同其读图说明一起切换。 */}
          {view === 'ring' ? (
            <RelationGraph state={state} />
          ) : (
            <>
              <RelationMatrix state={state} />
              <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>
                行/列均为势力单字徽标；格内 = 该对关系，浅色空格 = 中立。悬停可看双方名与信任度。
              </div>
            </>
          )}

          {/* [M4] 战况摘要默认折叠 */}
          <button
            onClick={() => setShowSummary((v) => !v)}
            style={{
              display: 'flex', alignItems: 'center', width: '100%', marginTop: '16px',
              padding: '6px 8px', background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--panel-border)', borderRadius: '6px',
              color: 'var(--gold)', fontSize: '13px', cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            <i className={`fa-solid fa-chevron-${showSummary ? 'down' : 'right'}`} style={{ marginRight: '6px', fontSize: '9px' }}></i>
            当前战况摘要
            <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--text-muted)' }}>
              {myRelations.length} 对 · {showSummary ? '点击折叠' : '点击展开'}
            </span>
          </button>
          {showSummary && (
            <div style={{ marginTop: '8px' }}>
              {myRelations.length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '6px 0' }}>暂无交战的势力对</div>
              )}
              {myRelations.map((rel, i) => {
                const other = rel.faction_a === humanFaction ? rel.faction_b : rel.faction_a
                // [修复 2026-10-01] 观战模式下原代码只渲染 faction_a，且关系数据多为"汉室↔X"
                // → 整列全被渲染成"汉室"。改为显示完整 A ↔ B。
                const label = humanFaction
                  ? (FACTIONS[other] || other)
                  : `${FACTIONS[rel.faction_a] || rel.faction_a} ↔ ${FACTIONS[rel.faction_b] || rel.faction_b}`
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      marginBottom: '6px',
                      background: 'rgba(255,255,255,0.03)',
                      borderRadius: '6px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: FACTION_COLORS[other] || '#888',
                          display: 'inline-block',
                        }}
                      />
                      <span style={{ fontSize: '12px', color: 'var(--text)' }}>
                        {label}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: statusColor[rel.status] + '22',
                          color: statusColor[rel.status],
                        }}
                      >
                        {statusLabel[rel.status]}
                      </span>
                      <span style={{ fontSize: '11px', color: UI_COLORS.textSecondary, width: '30px', textAlign: 'right' }}>
                        {rel.trust}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'messages' && (
        <div>
          <div style={{ fontSize: '13px', color: 'var(--gold)', marginBottom: '10px', fontFamily: 'var(--font-serif)' }}>
            外交消息
          </div>
          {messages.length === 0 && (
            <div style={{ fontSize: '12px', color: '#666', textAlign: 'center', padding: '20px 0' }}>
              暂无外交消息
            </div>
          )}
          {messages.slice().reverse().map((msg) => (
            <MessageItem key={msg.id} msg={msg} humanFaction={humanFaction} />
          ))}
        </div>
      )}

      {activeTab === 'send' && humanFaction && (
        <div>
          <div style={{ fontSize: '13px', color: 'var(--gold)', marginBottom: '10px', fontFamily: 'var(--font-serif)' }}>
            发送外交消息
          </div>
          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', color: UI_COLORS.textSecondary, display: 'block', marginBottom: '4px' }}>
              目标势力
            </label>
            <select
              value={targetFaction}
              onChange={e => setTargetFaction(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid rgba(255,255,255,0.1)',
                background: 'rgba(0,0,0,0.3)',
                color: 'var(--text)',
                fontSize: '13px',
              }}
            >
              <option value="">选择势力...</option>
              {Object.entries(FACTIONS)
                .filter(([fid]) => fid !== humanFaction)
                .map(([fid, name]) => (
                  <option key={fid} value={fid}>{name}</option>
                ))}
            </select>
          </div>
          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', color: UI_COLORS.textSecondary, display: 'block', marginBottom: '4px' }}>
              消息内容
            </label>
            <textarea
              value={msgContent}
              onChange={e => setMsgContent(e.target.value)}
              rows={4}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid rgba(255,255,255,0.1)',
                background: 'rgba(0,0,0,0.3)',
                color: 'var(--text)',
                fontSize: '13px',
                resize: 'none',
              }}
              placeholder="输入外交消息..."
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={!targetFaction || !msgContent.trim()}
            style={{
              width: '100%',
              padding: '10px',
              borderRadius: '6px',
              border: 'none',
              background: targetFaction && msgContent.trim() ? 'var(--gold)' : '#555',
              color: 'var(--bg)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: targetFaction && msgContent.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            发送消息
          </button>
        </div>
      )}

      {activeTab === 'send' && !humanFaction && (
        <div style={{ fontSize: '12px', color: '#666', textAlign: 'center', padding: '20px 0' }}>
          观战模式下无法发送外交消息
        </div>
      )}
    </div>
  )
}

function MessageItem({ msg, humanFaction }: { msg: DiplomacyMessage; humanFaction: string | null }) {
  const isIncoming = msg.to_faction === humanFaction
  const isOutgoing = msg.from_faction === humanFaction

  return (
    <div
      style={{
        padding: '10px',
        marginBottom: '8px',
        borderRadius: '6px',
        background: isIncoming ? 'rgba(90,180,100,0.08)' : isOutgoing ? 'rgba(200,168,90,0.08)' : 'rgba(255,255,255,0.03)',
        borderLeft: `3px solid ${isIncoming ? 'var(--green)' : isOutgoing ? 'var(--gold)' : '#666'}`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '11px', color: UI_COLORS.textSecondary }}>
          {isIncoming ? '← ' : ''}{FACTIONS[msg.from_faction] || msg.from_faction}
          {isOutgoing ? ' → ' : ' → '}{FACTIONS[msg.to_faction] || msg.to_faction}
        </span>
        <span style={{ fontSize: '10px', color: '#666' }}>第 {msg.turn} 回合</span>
      </div>
      <div style={{ fontSize: '13px', color: 'var(--text)', lineHeight: 1.5 }}>
        {msg.content}
      </div>
    </div>
  )
}
