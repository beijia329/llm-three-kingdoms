import { useState } from 'react'
import { FACTION_COLORS, FACTION_GLOW, FACTIONS, armyMarkerSize, CITY_MARKER_SIZE, ARMY_VS_CITY_RATIO, FS, UI_COLORS } from '../../theme'
// [阶段A 2026-10-03] 接入 game-icons 素材（CC BY 3.0）：
// 行军→马首、进攻/围城→交叉刀剑、撤退→盾牌、驻守/待命→盾牌。
// [D3 2026-10-04] 三档尺寸（12/16/20 屏幕px，由兵力决定）+ 状态剪影 + 行军方向箭头
// + 城池:军队 比例锁定（军队 ≤ 同格城池 ×0.80）。见 docs/art/2026-10-04-战棋视觉元素规范.md §4.5。
import horseIcon from '../../assets/icons/horse-head.svg'
import swordsIcon from '../../assets/icons/crossed-swords.svg'
import shieldIcon from '../../assets/icons/shield.svg'
import { useHintProps } from '../Tooltip'

interface ArmyMarkerProps {
  army: {
    id: string
    faction: string
    general_id?: string
    soldiers: number
    morale: number
    status: string
    from_city?: string
    to_city?: string
  }
  x: number
  y: number
  zoom: number
  /** 是否被选中（高亮描边） */
  selected?: boolean
  /** 点击选中军队 */
  onClick?: () => void
  generalName?: string
  fromName?: string
  toName?: string
  /** 行军目标的世界像素坐标（画方向箭头用；缺省则不画） */
  toPos?: { x: number; y: number } | null
  /** 同格城池等级（比例锁定用：军队 ≤ 城池 ×0.80；缺省则不锁定） */
  cityLevel?: number
}

function maskStyle(url: string, color: string, size: number) {
  return {
    width: `${size}px`,
    height: `${size}px`,
    backgroundColor: color,
    maskImage: `url(${url})`,
    WebkitMaskImage: `url(${url})`,
    maskSize: 'contain',
    WebkitMaskSize: 'contain',
    maskRepeat: 'no-repeat' as const,
    WebkitMaskRepeat: 'no-repeat' as const,
    maskPosition: 'center',
    WebkitMaskPosition: 'center',
    display: 'block',
  }
}

const STATUS_LABELS: Record<string, string> = {
  marching: '行军中', attacking: '进攻中', besieging: '围城中',
  retreating: '撤退中', defending: '驻守中', idle: '待命',
}

/** 棋子内部参考框（缩放前世界量级） */
const INTERNAL = 32

export function ArmyMarker({ army, x, y, zoom, selected, onClick, generalName, fromName, toName, toPos, cityLevel }: ArmyMarkerProps) {
  const [hovered, setHovered] = useState(false)
  const hint = useHintProps(() => ({
    title: `${generalName || '未知将领'} 的部队${army.faction ? ` · ${FACTIONS[army.faction] || army.faction}` : ''}`,
    lines: [
      `兵力 ${army.soldiers.toLocaleString()} · 士气 ${army.morale}`,
      `状态 ${STATUS_LABELS[army.status] || army.status || '—'}`,
      fromName || toName ? `${fromName ? `自 ${fromName}` : ''}${toName ? ` → ${toName}` : ''}` : '',
      '单击查看详情',
    ].filter(Boolean),
  }))
  if (army.soldiers <= 0) return null

  const color = FACTION_COLORS[army.faction] || '#888'
  const glow = FACTION_GLOW[army.faction] || 'rgba(128,128,128,0.5)'
  const isRetreat = army.status === 'retreating'
  const isAttack = /attack|siege|besie|assault/i.test(army.status)
  const isMarching = army.status === 'marching'
  const icon = isRetreat ? shieldIcon : isAttack ? swordsIcon : isMarching ? horseIcon : shieldIcon

  // [D3 §4.5①] 兵力 → 尺寸档（屏幕 px）：12/16/20
  let markerScreen = armyMarkerSize(army.soldiers)
  // [D3 §4.5④] 比例锁定：同格有城时，军队 ≤ 城池 ×0.80
  if (cityLevel != null && CITY_MARKER_SIZE[Math.min(Math.max(cityLevel, 1), 5)]) {
    markerScreen = Math.min(markerScreen, CITY_MARKER_SIZE[Math.min(Math.max(cityLevel, 1), 5)] * ARMY_VS_CITY_RATIO)
  }
  const scale = markerScreen / (INTERNAL * Math.max(zoom, 0.02))
  const s = (screenPx: number) => (screenPx * INTERNAL) / markerScreen
  const iconSize = s(markerScreen * 0.85)
  const showNumber = markerScreen >= 12

  const moraleRatio = Math.max(0, Math.min(1, army.morale / 100))
  const moraleColor = moraleRatio > 0.5 ? '#3CB464' : moraleRatio > 0.2 ? '#C8A032' : UI_COLORS.red

  // 行军方向箭头（§4.5③）：由标记中心指向目标城
  let dir: { dx: number; dy: number } | null = null
  if (isMarching && toPos) {
    const dx = toPos.x - x
    const dy = toPos.y - y
    const len = Math.hypot(dx, dy) || 1
    dir = { dx: dx / len, dy: dy / len }
  }

  return (
    <div
      {...hint}
      data-army-id={army.id}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick() } : undefined}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        transformOrigin: 'center center',
        pointerEvents: onClick ? 'auto' : 'none',
        cursor: onClick ? 'pointer' : 'default',
        zIndex: selected ? 25 : 15,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        outline: selected ? `${s(2)}px solid ${UI_COLORS.gold}` : 'none',
        outlineOffset: `${s(3)}px`,
        borderRadius: `${s(4)}px`,
        filter: hovered && !selected ? 'brightness(1.12)' : undefined,
        transition: 'filter 0.12s ease',
      }}
    >
      {/* 军队图标：状态决定剪影（行军=马 / 进攻|围城=刀剑 / 撤退|驻守=盾），势力色着色；撤退固定朱砂红 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 1px #2a2018) drop-shadow(0 1px 2px rgba(0,0,0,0.5)) drop-shadow(0 0 4px ${glow})`,
          animation: isRetreat ? 'retreat-shake 0.8s ease-in-out infinite' : 'none',
        }}
      >
        <span aria-hidden style={maskStyle(icon, isRetreat ? UI_COLORS.red : color, iconSize)} />
        {/* 行军方向：2px 短箭头，长 10 屏幕px */}
        {dir && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              width: `${s(10)}px`,
              height: `${s(2)}px`,
              backgroundColor: color,
              transformOrigin: 'left center',
              transform: `translate(0, -50%) rotate(${Math.atan2(dir.dy, dir.dx)}rad)`,
              boxShadow: '0 0 1px #2a2018',
            }}
          />
        )}
      </div>

      {/* 兵力数字：10 屏幕px 粗体 + 深描边；<12px 隐藏 */}
      {showNumber && (
        <div
          style={{
            marginTop: '1px',
            color: UI_COLORS.textPrimary,
            fontSize: `${s(FS.caption)}px`,
            fontWeight: 700,
            textShadow: '0 1px 3px rgba(0,0,0,0.9)',
          }}
        >
          {army.soldiers}
        </div>
      )}

      {/* 士气条：宽 = 标记×0.7、高 3 屏幕px */}
      <div
        style={{
          width: `${s(markerScreen * 0.7)}px`,
          height: `${s(3)}px`,
          backgroundColor: '#282836',
          borderRadius: `${s(2)}px`,
          marginTop: '1px',
          overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(0,0,0,0.5)',
        }}
      >
        <div
          style={{
            width: `${moraleRatio * 100}%`,
            height: '100%',
            backgroundColor: moraleColor,
            borderRadius: `${s(2)}px`,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
