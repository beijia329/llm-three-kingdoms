import { FACTION_COLORS, FACTION_GLOW } from '../../theme'
// [阶段A 2026-10-03] 接入 game-icons 素材（CC BY 3.0）：
// 行军→马首、进攻/围城→交叉刀剑、撤退→盾牌。原来军队只是一个旋转方块，看不出状态。
import horseIcon from '../../assets/icons/horse-head.svg'
import swordsIcon from '../../assets/icons/crossed-swords.svg'
import shieldIcon from '../../assets/icons/shield.svg'

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
  /** 点击选中军队（此前 pointerEvents:none，整支军队点不了） */
  onClick?: () => void
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

export function ArmyMarker({ army, x, y, zoom, selected, onClick }: ArmyMarkerProps) {
  if (army.soldiers <= 0) return null

  const color = FACTION_COLORS[army.faction] || '#888'
  const glow = FACTION_GLOW[army.faction] || 'rgba(128,128,128,0.5)'
  const isRetreat = army.status === 'retreating'
  const isAttack = /attack|siege|besie|assault/i.test(army.status)
  const icon = isRetreat ? shieldIcon : isAttack ? swordsIcon : horseIcon
  // [LOD 2026-10-01] 屏幕尺寸随地图缩放（8~28px）
  const markerScreen = Math.max(12, Math.min(30, 64 * zoom * 1.4))
  const scale = markerScreen / (32 * Math.max(zoom, 0.02))

  const moraleRatio = Math.max(0, Math.min(1, army.morale / 100))
  const moraleColor = moraleRatio > 0.5 ? '#3cb464' : moraleRatio > 0.2 ? '#c8a032' : '#c85046'

  return (
    <div
      onClick={onClick ? (e) => { e.stopPropagation(); onClick() } : undefined}
      title={`军队 · ${army.soldiers} 兵 · 士气 ${army.morale}`}
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
        outline: selected ? '2px solid rgba(212,168,75,0.95)' : 'none',
        outlineOffset: '3px',
        borderRadius: '6px',
      }}
    >
      {/* 军队图标：状态决定剪影，势力色着色 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 1px #2a2018) drop-shadow(0 1px 2px rgba(0,0,0,0.5)) drop-shadow(0 0 4px ${glow})`,
          animation: isRetreat ? 'retreat-shake 0.8s ease-in-out infinite' : 'none',
        }}
      >
        <span aria-hidden style={maskStyle(icon, isRetreat ? '#c85046' : color, 18)} />
      </div>

      {/* 兵力数字 */}
      <div
        style={{
          marginTop: '1px',
          color: '#e8e0d0',
          fontSize: '10px',
          fontWeight: 700,
          textShadow: '0 1px 3px rgba(0,0,0,0.9)',
          fontFamily: 'sans-serif',
        }}
      >
        {army.soldiers}
      </div>

      {/* 士气条 */}
      <div
        style={{
          width: '22px',
          height: '3px',
          backgroundColor: '#282836',
          borderRadius: '2px',
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
            borderRadius: '2px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
