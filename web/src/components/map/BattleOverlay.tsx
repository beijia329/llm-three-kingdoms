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
 * ⚠️ 出发城是**复数**（设计文档 §4.3.1）：实测 **15% 的战斗**有多支来自不同城的攻方部队
 *    被合并（`battle_scheduler._group_by_target`）。所以这里对**每个出发城各画一条箭头**，
 *    多线汇聚到目标城——单起点会漏画其余进攻线、指向错误。
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
function FactionTag({ faction, size = 12 }: { faction: string; size?: number }) {
  const color = FACTION_COLORS[faction] || '#888'
  const glyph = FACTION_GLYPH[faction]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      {glyph && (
        <span
          style={{
            width: size,
            height: size,
            borderRadius: 3,
            background: color,
            color: contrastText(color),
            fontSize: size * 0.62,
            fontWeight: 700,
            lineHeight: 1,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid rgba(0,0,0,0.4)',
          }}
        >
          {glyph}
        </span>
      )}
      <span style={{ color: '#f0ece2', fontSize: size * 0.95, textShadow: '0 0 3px #000, 0 0 2px #000' }}>
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
        const active = i === activeIndex
        const meta = RESULT_META[b.result] || RESULT_META.draw
        const attColor = FACTION_COLORS[b.attacker_faction] || '#d4a84b'

        // 出发城是复数：每个出发城各一条箭头汇聚到目标城
        const fromIds = Array.isArray(b.attacker_from_cities) ? b.attacker_from_cities : []
        const origins = fromIds.map((id) => cityPixel(cities, id)).filter((p): p is { x: number; y: number } => !!p)
        const target = cityPixel(cities, b.defender_city)

        // 兵力比 → 箭头粗细（屏幕像素量级，再乘 inv 抵消地图缩放）
        const total = Math.max(1, b.attacker_soldiers + b.defender_soldiers)
        const attShare = b.attacker_soldiers / total
        const width = (4 + 5 * attShare) * inv
        const w = active ? width : width * 0.7

        // 城防（城墙耐久）剩量比例 —— 回放标签里的城防条用
        const wallRatio =
          typeof b.wall_hp_before === 'number' && b.wall_hp_before > 0 && typeof b.wall_hp_after === 'number'
            ? Math.max(0, Math.min(1, b.wall_hp_after / b.wall_hp_before))
            : null
        const wallColor =
          wallRatio === null ? '#8a86a0' : wallRatio > 0.5 ? '#3cb464' : wallRatio > 0.2 ? '#c8a032' : '#c85046'

        // 没有目标城就退化为在出发城上画爆点；有目标城但没出发城（如反击）→ 目标城爆点
        const burstAt = target || origins[0]
        const labelAt = target || origins[0]

        return (
          <div key={b.battle_id || i}>
            <svg style={{ position: 'absolute', left: 0, top: 0, width: '1px', height: '1px', overflow: 'visible' }}>
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
                  <path d="M0,0 L2.2,1.1 L0,2.2 Z" fill={attColor} />
                </marker>
              </defs>

              {/* 每个出发城 → 目标城 一条箭头（多线汇聚 = 「多路合攻」）。
                  用**二次贝塞尔**：单路带轻微弧（不死板）；多路按出发城序号在中点两侧
                  扇形错开曲率，避免几条线叠成一条看不清。 */}
              {target &&
                origins.map((o, k) => {
                  const mx = (o.x + target.x) / 2
                  const my = (o.y + target.y) / 2
                  const dx = target.x - o.x
                  const dy = target.y - o.y
                  const len = Math.hypot(dx, dy) || 1
                  const nx = -dy / len
                  const ny = dx / len
                  // 单路：固定侧偏（轻弧）；多路：以中点为中心扇形分布
                  const spread = (origins.length > 1 ? (k - (origins.length - 1) / 2) * 78 : 22) * inv
                  const cx = mx + nx * spread
                  const cy = my + ny * spread

                  let d = `M ${o.x} ${o.y} Q ${cx} ${cy} ${target.x} ${target.y}`
                  // 回放时线要「从起点长到终点」：取 t=progress 处的**子曲线**。
                  // 二次贝塞尔的子曲线仍是二次贝塞尔——De Casteljau 在 t=p 切分，左半段
                  // 控制点 = (P0, lerp(P0,C,p), lerp(lerp(P0,C,p), lerp(C,P2,p), p))。
                  // （直接截断终点画 Q 会得到一条形状不对的曲线。）
                  if (active) {
                    const ax = o.x + (cx - o.x) * progress
                    const ay = o.y + (cy - o.y) * progress
                    const bx = cx + (target.x - cx) * progress
                    const by = cy + (target.y - cy) * progress
                    const qx = ax + (bx - ax) * progress
                    const qy = ay + (by - ay) * progress
                    d = `M ${o.x} ${o.y} Q ${ax} ${ay} ${qx} ${qy}`
                  }
                  return (
                    <g key={k}>
                      {/* 深色描边：保证箭头在浅羊皮纸与深海上都读得出来 */}
                      <path
                        d={d}
                        fill="none"
                        stroke="#120c06"
                        strokeWidth={w + 2 * inv}
                        strokeOpacity={active ? 0.5 : 0.28}
                        strokeLinecap="round"
                      />
                      <path
                        d={d}
                        fill="none"
                        stroke={attColor}
                        strokeWidth={w}
                        strokeOpacity={active ? 0.98 : 0.45}
                        strokeLinecap="round"
                        strokeDasharray={active ? `${9 * inv} ${6 * inv}` : undefined}
                        markerEnd={active ? (progress > 0.85 ? `url(#arrow-${i})` : undefined) : `url(#arrow-${i})`}
                        style={active ? { strokeDashoffset: -(progress * 30 * inv) } : undefined}
                      />
                    </g>
                  )
                })}

              {/* 交战爆点：回放推进到中段时闪一下 */}
              {active && burstAt && progress > 0.35 && (
                <circle
                  cx={burstAt.x}
                  cy={burstAt.y}
                  r={(5 + 4 * Math.abs(Math.sin(progress * Math.PI * 3))) * inv}
                  fill={meta.color}
                  fillOpacity={0.35}
                />
              )}
            </svg>

            {/* 回放标签：只给正在回放的那一场显示，避免全图刷屏 */}
            {active && labelAt && (
              <div
                style={{
                  position: 'absolute',
                  left: labelAt.x,
                  top: labelAt.y,
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
                  <FactionTag faction={b.attacker_faction} />
                  {origins.length > 1 && (
                    <span style={{ color: '#8a86a0', fontSize: 10 }}>×{origins.length}路</span>
                  )}
                  <span style={{ color: '#e8e0d0', fontSize: 13, fontWeight: 700 }}>⚔</span>
                  <FactionTag faction={b.defender_faction} />
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
                {/* 城防条：把「城墙被打掉多少」也画出来（守城战的关键读数） */}
                {wallRatio !== null && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 5,
                      fontSize: 10,
                      color: '#c9c4d4',
                      background: 'rgba(14,14,26,0.85)',
                      borderRadius: 5,
                      padding: '1px 7px',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    <i className="fa-solid fa-shield-halved" style={{ fontSize: 9, color: '#8a86a0' }}></i>
                    <span>城防</span>
                    <div
                      style={{
                        width: 56,
                        height: 4,
                        background: '#282836',
                        borderRadius: 2,
                        overflow: 'hidden',
                      }}
                    >
                      <div style={{ width: `${wallRatio * 100}%`, height: '100%', background: wallColor }} />
                    </div>
                    <span>
                      {b.wall_hp_before} → {b.wall_hp_after}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
