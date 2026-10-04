import { useState } from 'react'
import { FACTION_COLORS, FACTION_GLOW, FACTION_GLYPH, FACTIONS, contrastText, CITY_MARKER_SIZE, FS, UI_COLORS } from '../../theme'
// [阶段A 2026-10-03] 接入已下载的 game-icons 素材（CC BY 3.0，见 assets/art/ATTRIBUTION.md）。
// [D3 2026-10-04] 五档尺寸（14/16/19/22/26 屏幕px，恒定）+ 四重编码（守军/城墙/民心/围城）
// + 显示条件（<18px 只留剪影+势力字）。见 docs/art/2026-10-04-战棋视觉元素规范.md §4.4。
import gateIcon from '../../assets/icons/gate.svg'
import fortIcon from '../../assets/icons/military-fort.svg'
import castleIcon from '../../assets/icons/castle.svg'
import hillFortIcon from '../../assets/icons/hill-fort.svg'
import crownIcon from '../../assets/icons/crown.svg'
import siegeTowerIcon from '../../assets/icons/siege-tower.svg'
// [交互 2026-10-03] hover 悬浮卡（审计 §4-3）
import { useHintProps } from '../Tooltip'
// 技术债合并：mask 样式走单一实现（见 utils/mask.ts）
import { maskStyle } from '../../utils/mask'

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

/** 棋子内部参考框（px，缩放前的世界量级；配合 scale 让屏幕尺寸 = markerScreen） */
const INTERNAL = 34

export function CityMarker({ city, x, y, zoom, onClick, selected }: CityMarkerProps) {
  const [hovered, setHovered] = useState(false)
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

  const level = Math.min(Math.max(city.level, 1), 5)
  // [D3 §4.4①] 等级 → 尺寸档（屏幕 px，恒定）：14/16/19/22/26
  const markerScreen = CITY_MARKER_SIZE[level]
  const scale = markerScreen / (INTERNAL * Math.max(zoom, 0.02))
  // 屏幕 px → 内部 px，保证子元素屏幕尺寸恒定
  const s = (screenPx: number) => (screenPx * INTERNAL) / markerScreen
  // [D3 §4.4③] 显示条件：≥18px 才显示城名/兵力条/城墙盾/民心点
  const showDetails = markerScreen >= 18
  const iconSize = s(markerScreen * 0.82)
  const isCapital = level >= 5

  const maxG = level * 1000
  const ratio = Math.min(1, city.garrison / maxG)
  const hpColor = ratio > 0.5 ? '#3CB464' : ratio > 0.2 ? '#C8A032' : UI_COLORS.red

  // 城墙（wall_hp）编码：左上角盾形竖条
  const wallRatio =
    city.wall_max_hp && city.wall_max_hp > 0 && typeof city.wall_hp === 'number'
      ? Math.max(0, Math.min(1, city.wall_hp / city.wall_max_hp))
      : null
  // 民心（morale）编码：左下角小方点
  const morale = typeof city.morale === 'number' ? city.morale : null
  const moraleColor = morale === null ? UI_COLORS.green : morale > 50 ? UI_COLORS.green : morale > 20 ? '#C8A032' : UI_COLORS.red

  return (
    <div
      {...hint}
      data-city-id={city.id}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
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
        // 悬停提亮 12%（§4.6）
        filter: hovered && !selected ? 'brightness(1.12)' : undefined,
        transition: 'filter 0.12s ease',
      }}
    >
      {/* 选中高亮：金色脉冲环（§4.6 统一为「金」） */}
      {selected && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            top: '48%',
            left: '50%',
            width: s(46),
            height: s(46),
            transform: 'translate(-50%, -50%)',
            border: `${s(2)} solid ${UI_COLORS.gold}`,
            borderRadius: '50%',
            boxShadow: `0 0 ${s(8)} ${UI_COLORS.goldGlow}`,
            animation: 'city-select-pulse 1.6s ease-in-out infinite',
            pointerEvents: 'none',
          }}
        />
      )}
      {/* 城池标记：等级剪影（势力色） */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 1px #2a2018) drop-shadow(0 1px 2px rgba(0,0,0,0.45)) drop-shadow(0 0 5px ${glow})`,
          animation: city.is_besieged ? 'city-pulse 2s ease-in-out infinite' : 'none',
        }}
      >
        <span aria-hidden style={maskStyle(cityIcon(level), color, iconSize)} />

        {/* 城墙（左上角盾形竖条）：满时古金、破损 >50% 转朱砂；未定义不显示 */}
        {showDetails && wallRatio !== null && (
          <span
            aria-hidden
            title={`城墙 ${Math.round(wallRatio * 100)}%`}
            style={{
              position: 'absolute',
              left: '-4px',
              top: '0px',
              width: `${s(3)}px`,
              height: `${s(markerScreen * 0.6)}px`,
              borderRadius: `${s(2)}px`,
              backgroundColor: wallRatio > 0.5 ? UI_COLORS.gold : UI_COLORS.red,
              border: '1px solid #2a2018',
              boxSizing: 'border-box',
            }}
          />
        )}

        {/* 民心（左下角小方点）：三档色；未定义不显示 */}
        {showDetails && morale !== null && (
          <span
            aria-hidden
            title={`民心 ${morale}`}
            style={{
              position: 'absolute',
              left: '-4px',
              bottom: '2px',
              width: `${s(6)}px`,
              height: `${s(6)}px`,
              borderRadius: `${s(1)}px`,
              backgroundColor: moraleColor,
              border: '1px solid #2a2018',
              boxSizing: 'border-box',
            }}
          />
        )}

        {/* 势力单字（非颜色线索，色盲也认得出是谁）—— 只在放大到一定程度显示 */}
        {showDetails && FACTION_GLYPH[city.faction] && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              bottom: '-3px',
              right: '-5px',
              width: `${Math.round(iconSize * 0.72)}px`,
              height: `${Math.round(iconSize * 0.72)}px`,
              borderRadius: `${s(2)}px`,
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

        {/* 都城：右上角加冕（crown 剪影，古金） */}
        {isCapital && !city.is_besieged && (
          <span
            aria-hidden
            style={{
              position: 'absolute',
              top: '-5px',
              right: '-6px',
              padding: '1px',
              filter: 'drop-shadow(0 0 1px #2a2018)',
              ...maskStyle(crownIcon, UI_COLORS.gold, 11),
            }}
          />
        )}

        {/* 围城警告：右上角攻城塔标记（朱砂） */}
        {city.is_besieged && (
          <span
            style={{
              position: 'absolute',
              top: '-7px',
              right: '-8px',
              width: `${s(13)}px`,
              height: `${s(13)}px`,
              borderRadius: '50%',
              backgroundColor: UI_COLORS.red,
              border: '1.5px solid #2a2018',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'siege-blink 1s ease-in-out infinite',
            }}
          >
            <span aria-hidden style={{ ...maskStyle(siegeTowerIcon, '#fff', 8), display: 'block' }} />
          </span>
        )}
      </div>

      {/* 城市名（缩得太小时隐藏；字号走标尺 FS.body=12 屏幕px） */}
      {showDetails && (
        <div
          style={{
            marginTop: '2px',
            color: '#2f2418',
            fontSize: `${s(FS.body)}px`,
            fontWeight: 600,
            textShadow: '0 0 3px rgba(255,250,235,0.9), 0 0 2px rgba(255,250,235,0.9)',
            whiteSpace: 'nowrap',
            letterSpacing: '0.5px',
          }}
        >
          {city.name}
        </div>
      )}

      {/* 守军兵力条：宽 = 标记宽×0.85、高 4 屏幕px */}
      {showDetails && (
        <div
          style={{
            width: `${s(markerScreen * 0.85)}px`,
            height: `${s(4)}px`,
            backgroundColor: '#282836',
            borderRadius: `${s(2)}px`,
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
              borderRadius: `${s(2)}px`,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      )}
    </div>
  )
}
