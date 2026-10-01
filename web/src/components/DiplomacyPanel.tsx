import type { GameState, DiplomacyMessage } from '../types'
import { FACTIONS, FACTION_COLORS } from '../theme'
import { useState } from 'react'

interface DiplomacyPanelProps {
  state: GameState
}

export function DiplomacyPanel({ state }: DiplomacyPanelProps) {
  const [activeTab, setActiveTab] = useState<'relations' | 'messages' | 'send'>('relations')
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
    : relations.slice(0, 12)

  const statusColor: Record<string, string> = {
    war: '#c85046',
    neutral: '#96918a',
    alliance: '#5ab464',
    truce: '#d4a84b',
  }

  const statusLabel: Record<string, string> = {
    war: '战',
    neutral: '中',
    alliance: '盟',
    truce: '和',
  }

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
              background: activeTab === t ? 'rgba(212,168,75,0.2)' : 'rgba(255,255,255,0.05)',
              color: activeTab === t ? '#d4a84b' : '#96918a',
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
          <div style={{ fontSize: '13px', color: '#d4a84b', marginBottom: '10px' }}>
            势力外交关系
          </div>
          {myRelations.map((rel, i) => {
            const other = rel.faction_a === humanFaction ? rel.faction_b : rel.faction_a
            // [修复 2026-10-01] 观战模式（无人类势力）下原代码只渲染 faction_a，
            // 且关系数据多为"汉室↔X" → 整列全被渲染成"汉室"。改为显示完整 A ↔ B。
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
                  borderRadius: '8px',
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
                  <span style={{ fontSize: '12px', color: '#e8e0d0' }}>
                    {label}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '10px',
                      background: statusColor[rel.status] + '22',
                      color: statusColor[rel.status],
                    }}
                  >
                    {statusLabel[rel.status]}
                  </span>
                  <span style={{ fontSize: '11px', color: '#96918a', width: '30px', textAlign: 'right' }}>
                    {rel.trust}
                  </span>
                </div>
              </div>
            )
          })}

          {/* 全矩阵（紧凑模式） */}
          <div style={{ marginTop: '16px', fontSize: '13px', color: '#d4a84b', marginBottom: '6px' }}>
            关系矩阵
          </div>
          {/* [修复 2026-10-01] 加图例：原来满屏"中"无任何说明，完全看不懂 */}
          <div style={{ display: 'flex', gap: '10px', fontSize: '11px', color: '#96918a', marginBottom: '8px' }}>
            <span><span style={{ color: statusColor.neutral }}>中</span>中立</span>
            <span><span style={{ color: statusColor.war }}>战</span>敌对</span>
            <span><span style={{ color: statusColor.alliance }}>盟</span>同盟</span>
            <span><span style={{ color: statusColor.truce }}>和</span>停战</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '3px' }}>
            {relations.slice(0, 24).map((rel, i) => (
              <div
                key={i}
                title={`${FACTIONS[rel.faction_a] || rel.faction_a} ↔ ${FACTIONS[rel.faction_b] || rel.faction_b}: ${rel.status} (${rel.trust})`}
                style={{
                  aspectRatio: '1',
                  borderRadius: '4px',
                  background: statusColor[rel.status] + '33',
                  border: `1px solid ${statusColor[rel.status]}55`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '9px',
                  color: statusColor[rel.status],
                }}
              >
                {statusLabel[rel.status]}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'messages' && (
        <div>
          <div style={{ fontSize: '13px', color: '#d4a84b', marginBottom: '10px' }}>
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
          <div style={{ fontSize: '13px', color: '#d4a84b', marginBottom: '10px' }}>
            发送外交消息
          </div>
          <div style={{ marginBottom: '10px' }}>
            <label style={{ fontSize: '12px', color: '#96918a', display: 'block', marginBottom: '4px' }}>
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
                color: '#e8e0d0',
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
            <label style={{ fontSize: '12px', color: '#96918a', display: 'block', marginBottom: '4px' }}>
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
                color: '#e8e0d0',
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
              background: targetFaction && msgContent.trim() ? '#d4a84b' : '#555',
              color: '#1a1a2e',
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
        borderRadius: '8px',
        background: isIncoming ? 'rgba(90,180,100,0.08)' : isOutgoing ? 'rgba(212,168,75,0.08)' : 'rgba(255,255,255,0.03)',
        borderLeft: `3px solid ${isIncoming ? '#5ab464' : isOutgoing ? '#d4a84b' : '#666'}`,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '11px', color: '#96918a' }}>
          {isIncoming ? '← ' : ''}{FACTIONS[msg.from_faction] || msg.from_faction}
          {isOutgoing ? ' → ' : ' → '}{FACTIONS[msg.to_faction] || msg.to_faction}
        </span>
        <span style={{ fontSize: '10px', color: '#666' }}>第 {msg.turn} 回合</span>
      </div>
      <div style={{ fontSize: '13px', color: '#e8e0d0', lineHeight: 1.5 }}>
        {msg.content}
      </div>
    </div>
  )
}
