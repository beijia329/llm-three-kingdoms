import type { BattleReport, City } from '../../types'
import { FACTION_COLORS, FACTIONS, FACTION_GLYPH, contrastText } from '../../theme'
import { HEX_SIZE, axialToPixel } from '../../utils/hex'

/**
 * 战斗回放叠加层（v4.1 · 阶段C2）
 *
 * 验收标准（`docs/design/v4.1-gameplay-gaps.md` §4.2）：
 * **单场战斗，观众只看地图、不看文字，3 秒内能复述三件事**：
 *   1. 谁在打谁        → 攻方势力色箭头 + 双方势力单字
 *   2. 打的什么结果    → 「占领／守住／溃退」徽标（三态各有配色与图标）
 *   3. 从哪来、打向哪  → 起点=攻方出发城 → 终点=目标城 的箭头
 *
 * 技术选型：**DOM + SVG**，复用 GameMap 已有的世界坐标 overlay transform，
 * 不引入 PixiJS ticker 动画系统（改动小、几场战斗无性能压力）。
 * 所有尺寸都除以 `zoom`，保证屏幕观感不随地图缩放变化。
 */
interface BattleOverlayProps {
  battles: BattleReport[]
  cities: Record<string, City>
  /** 正在回放的那一场（-1 = 无） */
  activeIndex: number
  /** 当前回放进度 0..1 */
  progress: number
  zoom: number
}

const RESULT_META: Record<string, { label: string; color: string; icon: string }> = {
  attacker_win: { label: '占领', color: '#d4a84b', icon: 'fa-flag' },
  defender_win: { label: '守住', color: '#5ab464', icon: 'fa-shield-halved' },
  retreat: { label: '溃退', color: '#b06a5a', icon: 'fa-person-running' },
  draw: { label: '相持', color: '#96918a', icon: 'fa-equals' },
}

function cityPixel(cities: Record<string, City>, id: string | null) {
  if (!id) return null
  const c = cities[id]
  if (!c) return null
  return axialToPixel(c.position, HEX_SIZE)
}

/** 势力名 + 单字（地图上认人靠「色 + 字」双线索，色盲也认得出） */
function FactionTag({ faction, size = 12, zoom }: { faction: string; size?: number; zoom: number }) {
  const color = FACTION_COLORS[faction] || '#888'
  const glyph = FACTION_GLYPH[faction]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 / zoom }}>
      {glyph && (
        <span
          style={{
            width: size / zoom,
            height: size / zoom,
            borderRadius: 3 / zoom,
            background: color,
            color: contrastText(color),
            fontSize: (size * 0.62) / zoom,
            fontWeight: 700,
            lineHeight: 1,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: `${1 / zoom}px solid rgba(0,0,0,0.4)`,
          }}
        >
          {glyph}
        </span>
      )}
      <span style={{ color: '#f0ece2', fontSize: (size * 0.95) / zoom, textShadow: '0 0 3px #000, 0 0 2px #000' }}>
        {FACTIONS[faction] || faction}
      </span>
    </span>
  )
}

export function BattleOverlay({ battles, cities, activeIndex, progress, zoom }: BattleOverlayProps) {
  if (!battles || battles.length === 0) return null
  const inv = 1 / Math.max(zoom, 0.02)

  return (
    <div style={{ position: 'absolute', left: 0, top: 0, width: '1px', height: '1px', pointerEvents: 'none' }}>
      {battles.map((b, i) => {
        const a = cityPixel(cities, b.attacker_from_city)
        const d = cityPixel(cities, b.defender_city)
        const active = i === activeIndex
        const meta = RESULT_META[b.result] || RESULT_META.draw
        const attColor = FACTION_COLORS[b.attacker_faction] || '#d4a84b'

        // 兵力比 → 箭头粗细（屏幕像素量级，再乘 inv 抵消地图缩放）
        const total = Math.max(1, b.attacker_soldiers + b.defender_soldiers)
        const attShare = b.attacker_soldiers / total
        const width = (4 + 5 * attShare) * inv
        const w = active ? width : width * 0.7
        // 箭头一律用攻方势力色（残留箭也保留颜色，方便一眼看出「谁发起的」）
        const strokeColor = attColor

        // 目标点：有箭头就画攻方向；没出发城就退化为目标城上的爆点
        const from = a && d ? a : d
        const to = d || a

        return (
          <div key={b.battle_id || i}>
            {from && to && a && d && (
              <svg
                style={{ position: 'absolute', left: 0, top: 0, width: '1px', height: '1px', overflow: 'visible' }}
              >
                <defs>
                  {/* ⚠️ markerUnits 默认 = strokeWidth：marker 尺寸会**乘以线宽**。
                      本组线宽是「屏幕像素 / 缩放」的世界量级，若用默认值箭头会被放大到几十像素
                      （实测过：出现一个巨大三角）。这里把 marker 收到 2.2 倍线宽。 */}
                  <marker
                    id={`arrow-${i}`}
                    markerWidth={2.2}
                    markerHeight={2.2}
                    refX={1.8}
                    refY={1.1}
                    orient="auto"
                    markerUnits="strokeWidth"
                  >
                    <path d="M0,0 L2.2,1.1 L0,2.2 Z" fill={strokeColor} />
                  </marker>
                </defs>
                {/* 深色描边：保证箭头在浅羊皮纸与深海上都读得出来 */}
                <line
                  x1={a.x} y1={a.y} x2={d.x} y2={d.y}
                  stroke="#120c06"
                  strokeWidth={w + 2 * inv}
                  strokeOpacity={active ? 0.5 : 0.28}
                  strokeLinecap="round"
                />
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={d.x}
                  y2={d.y}
                  stroke={strokeColor}
                  strokeWidth={w}
                  strokeOpacity={active ? 0.98 : 0.45}
                  strokeLinecap="round"
                  strokeDasharray={active ? `${9 * inv} ${6 * inv}` : undefined}
                  markerEnd={`url(#arrow-${i})`}
                  style={active ? { strokeDashoffset: -(progress * 30 * inv) } : undefined}
                />
                {/* 交战中点的爆点：回放推进到中段时闪一下 */}
                {active && progress > 0.35 && (
                  <circle
                    cx={(a.x + d.x) / 2}
                    cy={(a.y + d.y) / 2}
                    r={(5 + 4 * Math.abs(Math.sin(progress * Math.PI * 3))) * inv}
                    fill={meta.color}
                    fillOpacity={0.35}
                  />
                )}
              </svg>
            )}

            {/* 回放标签：只给正在回放的那一场显示，避免全图刷屏 */}
            {active && to && (
              <div
                style={{
                  position: 'absolute',
                  left: to.x,
                  top: to.y,
                  transform: `translate(-50%, -100%) scale(${inv})`,
                  transformOrigin: 'center bottom',
                  marginTop: -18,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 3,
                  whiteSpace: 'nowrap',
                  opacity: Math.min(1, progress * 3),
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 8px',
                    borderRadius: 7,
                    background: 'rgba(14,14,26,0.92)',
                    border: `1px solid ${meta.color}`,
                    boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                  }}
                >
                  <FactionTag faction={b.attacker_faction} zoom={1} />
                  <span style={{ color: '#e8e0d0', fontSize: 13, fontWeight: 700 }}>⚔</span>
                  <FactionTag faction={b.defender_faction} zoom={1} />
                  <span
                    style={{
                      marginLeft: 4,
                      padding: '1px 6px',
                      borderRadius: 4,
                      border: `1px solid ${meta.color}`,
                      color: meta.color,
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    <i className={`fa-solid ${meta.icon}`} style={{ marginRight: 3, fontSize: 9 }}></i>
                    {meta.label}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: '#c9c4d4',
                    background: 'rgba(14,14,26,0.85)',
                    borderRadius: 5,
                    padding: '1px 7px',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {b.attacker_general_name ? `${b.attacker_general_name}　` : ''}
                  {b.attacker_soldiers.toLocaleString()} ⚔ {b.defender_soldiers.toLocaleString()}
                  <span style={{ color: '#b06a5a' }}>
                    {'　−'}
                    {(b.attacker_casualties + b.defender_casualties).toLocaleString()}
                  </span>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
