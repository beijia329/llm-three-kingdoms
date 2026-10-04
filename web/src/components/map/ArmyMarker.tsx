import { FACTION_COLORS, FACTION_GLOW, FACTIONS } from '../../theme'
// [阶段A 2026-10-03] 接入 game-icons 素材（CC BY 3.0）：
// 行军→马首、进攻/围城→交叉刀剑、撤退→盾牌。原来军队只是一个旋转方块，看不出状态。
import horseIcon from '../../assets/icons/horse-head.svg'
import swordsIcon from '../../assets/icons/crossed-swords.svg'
import shieldIcon from '../../assets/icons/shield.svg'
// [交互 2026-10-03] 军队 hover 悬浮卡（审计 §4-3）：替代原来只有一行数字的原生 title。
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
  /** 点击选中军队（此前 pointerEvents:none，整支军队点不了） */
  onClick?: () => void
  /** 主将名（供 hover 悬浮卡显示；未传则只显示兵力/士气） */
  generalName?: string
  /** 出发/目标城名（供 hover 显示行军路线） */
  fromName?: string
  toName?: string
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

export function ArmyMarker({ army, x, y, zoom, selected, onClick, generalName, fromName, toName }: ArmyMarkerProps) {
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
  const icon = isRetreat ? shieldIcon : isAttack ? swordsIcon : horseIcon
  // [LOD 2026-10-01] 屏幕尺寸随地图缩放（8~28px）
  const markerScreen = Math.max(12, Math.min(30, 64 * zoom * 1.4))
  const scale = markerScreen / (32 * Math.max(zoom, 0.02))

  const moraleRatio = Math.max(0, Math.min(1, army.morale / 100))
  const moraleColor = moraleRatio > 0.5 ? '#3cb464' : moraleRatio > 0.2 ? '#c8a032' : 'var(--red)'

  return (
    <div
      {...hint}
      data-army-id={army.id}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick() } : undefined}
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
        outline: selected ? '2px solid rgba(200,168,90,0.95)' : 'none',
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
        <span aria-hidden style={maskStyle(icon, isRetreat ? 'var(--red)' : color, 18)} />
      </div>

      {/* 兵力数字 */}
      <div
        style={{
          marginTop: '1px',
          color: 'var(--text)',
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
