import { FACTION_COLORS, FACTION_GLOW, FACTION_GLYPH, contrastText } from '../../theme'
// [阶段A 2026-10-03] 接入已下载的 game-icons 素材（CC BY 3.0，见 assets/art/ATTRIBUTION.md）。
// 原来城池只是一个纯色圆点，看不出「这是城」；现按等级换宫门/堡垒/城堡剪影，
// 用 CSS mask 着色，颜色仍随势力。
import gateIcon from '../../assets/icons/gate.svg'
import fortIcon from '../../assets/icons/military-fort.svg'
import castleIcon from '../../assets/icons/castle.svg'
import hillFortIcon from '../../assets/icons/hill-fort.svg'
import crownIcon from '../../assets/icons/crown.svg'
import siegeTowerIcon from '../../assets/icons/siege-tower.svg'
// [交互 2026-10-03] hover 悬浮卡（审计 §4-3）：地图标记在被 transform 缩放的覆盖层里，
// 用 portal 悬浮提示不会跟着缩放，位置由 getBoundingClientRect 计算。
import { useHintProps } from '../Tooltip'
import { FACTIONS } from '../../theme'

interface CityMarkerProps {
  city: {
    id: string
    name: string
    faction: string
    level: number
    garrison: number
    wall_hp?: number
    wall_max_hp?: number
    morale?: number
    is_besieged: boolean
  }
  x: number
  y: number
  zoom: number
  onClick: () => void
  /** 是否为当前选中的城池（金色环形高亮 + 放大） */
  selected?: boolean
}

// 等级 → 城池剪影（1 级小城 → 4/5 级大城/都城）
const CITY_ICONS = [gateIcon, fortIcon, castleIcon, hillFortIcon, hillFortIcon]
function cityIcon(level: number): string {
  const i = Math.min(Math.max(level, 1), 5) - 1
  return CITY_ICONS[i]
}

/** 生成「单色剪影 + 深描边」的 mask 样式（用于把 SVG 染成任意色） */
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

export function CityMarker({ city, x, y, zoom, onClick, selected }: CityMarkerProps) {
  const color = FACTION_COLORS[city.faction] || '#888'
  const glow = FACTION_GLOW[city.faction] || 'rgba(128,128,128,0.5)'
  const hint = useHintProps(() => ({
    title: `${city.name} · ${FACTIONS[city.faction] || city.faction}`,
    lines: [
      `等级 ${city.level} · 守军 ${city.garrison.toLocaleString()}`,
      city.wall_max_hp ? `城墙 ${city.wall_hp?.toLocaleString() ?? '?'} / ${city.wall_max_hp.toLocaleString()}` : '',
      typeof city.morale === 'number' ? `民心 ${city.morale}` : '',
      city.is_besieged ? '⚠ 被围困中' : '单击查看详情',
    ].filter(Boolean),
  }))
  // [LOD 2026-10-01] 标记屏幕尺寸随地图缩放（13~30px）；过小时隐藏城名。
  // [阶段A] 下限由 13→16：剪影图标比圆点更需要像素，否则糊成一团。
  const markerScreen = Math.max(16, Math.min(32, 64 * zoom * 1.6))
  const scale = markerScreen / (34 * Math.max(zoom, 0.02))
  const showName = markerScreen > 18
  // 剪影尺寸（内部像素，乘 scale 后为屏幕尺寸）
  const iconSize = 11 + Math.min(city.level, 5) * 2.2
  const isCapital = city.level >= 5

  const maxG = city.level * 1000
  const ratio = Math.min(1, city.garrison / maxG)
  const hpColor = ratio > 0.5 ? '#3cb464' : ratio > 0.2 ? '#c8a032' : '#c85046'

  return (
    <div
      {...hint}
      data-city-id={city.id}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale * (selected ? 1.18 : 1)})`,
        transformOrigin: 'center bottom',
        pointerEvents: 'auto',
        cursor: 'pointer',
        zIndex: selected ? 30 : city.is_besieged ? 20 : 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {/* 选中高亮：金色脉冲环（此前点城市只切 tab，地图毫无反馈 —— 审计 §3-4） */}
      {selected && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            top: '48%',
            left: '50%',
            width: '46px',
            height: '46px',
            transform: 'translate(-50%, -50%)',
            border: '2px solid #d4a84b',
            borderRadius: '50%',
            boxShadow: '0 0 14px rgba(212, 168, 75, 0.85), inset 0 0 8px rgba(212, 168, 75, 0.4)',
            animation: 'city-select-pulse 1.6s ease-in-out infinite',
            pointerEvents: 'none',
          }}
        />
      )}
      {/* 城池标记：等级剪影（势力色），外加深描边保证在羊皮纸与势力色块上都能读 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 1px #2a2018) drop-shadow(0 1px 2px rgba(0,0,0,0.45)) drop-shadow(0 0 5px ${glow})`,
          animation: city.is_besieged ? 'city-pulse 2s ease-in-out infinite' : 'none',
        }}
      >
        <span aria-hidden style={maskStyle(cityIcon(city.level), color, iconSize)} />

        {/* 势力单字（非颜色线索，色盲也认得出是谁）——与图标一同放大，
            只在放大到一定程度时显示，避免全图视角糊成一团 */}
        {markerScreen > 18 && FACTION_GLYPH[city.faction] && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              bottom: '-3px',
              right: '-5px',
              width: `${Math.round(iconSize * 0.72)}px`,
              height: `${Math.round(iconSize * 0.72)}px`,
              borderRadius: '3px',
              backgroundColor: color,
              color: contrastText(color),
              fontSize: `${Math.round(iconSize * 0.5)}px`,
              fontWeight: 700,
              lineHeight: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid #2a2018',
              boxSizing: 'border-box',
            }}
          >
            {FACTION_GLYPH[city.faction]}
          </span>
        )}

        {/* 都城：右上角加冕（crown 剪影） */}
        {isCapital && !city.is_besieged && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              top: '-5px',
              right: '-6px',
              padding: '1px',
              filter: 'drop-shadow(0 0 1px #2a2018)',
              ...maskStyle(crownIcon, '#d4a84b', 11),
            }}
          />
        )}

        {/* 围城警告：右上角攻城塔标记 */}
        {city.is_besieged && (
          <span
            style={{
              position: 'absolute',
              top: '-7px',
              right: '-8px',
              width: '13px',
              height: '13px',
              borderRadius: '50%',
              backgroundColor: '#c85046',
              border: '1.5px solid #2a2018',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'siege-blink 1s ease-in-out infinite',
            }}
          >
            <span
              aria-hidden
              style={{ ...maskStyle(siegeTowerIcon, '#fff', 8), display: 'block' }}
            />
          </span>
        )}
      </div>

      {/* 城市名（缩得太小时隐藏，避免糊成一团） */}
      {showName && (
        <div
          style={{
            marginTop: '2px',
            color: '#2f2418',
            fontSize: '12px',
            fontWeight: 600,
            textShadow: '0 0 3px rgba(255,250,235,0.9), 0 0 2px rgba(255,250,235,0.9)',
            whiteSpace: 'nowrap',
            fontFamily: 'Noto Sans SC, PingFang SC, sans-serif',
            letterSpacing: '0.5px',
          }}
        >
          {city.name}
        </div>
      )}

      {/* 兵力条 */}
      <div
        style={{
          width: '28px',
          height: '4px',
          backgroundColor: '#282836',
          borderRadius: '2px',
          marginTop: '2px',
          overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(0,0,0,0.5)',
        }}
      >
        <div
          style={{
            width: `${ratio * 100}%`,
            height: '100%',
            backgroundColor: hpColor,
            borderRadius: '2px',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
