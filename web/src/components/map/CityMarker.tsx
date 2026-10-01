import { FACTION_COLORS, FACTION_GLOW } from '../../theme'

interface CityMarkerProps {
  city: {
    id: string
    name: string
    faction: string
    level: number
    garrison: number
    is_besieged: boolean
  }
  x: number
  y: number
  zoom: number
  onClick: () => void
}

export function CityMarker({ city, x, y, zoom, onClick }: CityMarkerProps) {
  const color = FACTION_COLORS[city.faction] || '#888'
  const glow = FACTION_GLOW[city.faction] || 'rgba(128,128,128,0.5)'
  const size = 18 + city.level * 4
  // [修复 2026-10-01] 反向补偿缩放：让标记的"屏幕尺寸"大致恒定（原公式按 zoom 0.3~1.2 设计，
  // 取景到整张地图（zoom≈0.09）时标记被缩得几乎不可见）。
  const scale = Math.max(0.6, Math.min(14, 0.85 / Math.max(zoom, 0.05)))

  const maxG = city.level * 1000
  const ratio = Math.min(1, city.garrison / maxG)
  const hpColor = ratio > 0.5 ? '#3cb464' : ratio > 0.2 ? '#c8a032' : '#c85046'

  // [美术 2026-10-01] 城池图标改用 game-icons（CC BY 3.0）的 castle.svg，
  // 通过 CSS mask 上势力色（game-icons 为单色 currentColor，直接用 <img> 会变黑）。
  const iconSize = size * 1.25
  const maskIcon = (url: string, color: string, s: number) => ({
    width: s,
    height: s,
    backgroundColor: color,
    WebkitMaskImage: `url(${url})`,
    maskImage: `url(${url})`,
    WebkitMaskSize: 'contain',
    maskSize: 'contain',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
    WebkitMaskPosition: 'center',
    maskPosition: 'center',
  })

  return (
    <div
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        transformOrigin: 'center bottom',
        pointerEvents: 'auto',
        cursor: 'pointer',
        zIndex: city.is_besieged ? 20 : 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {/* 城池图标 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 6px ${glow})`,
          animation: city.is_besieged ? 'city-pulse 2s ease-in-out infinite' : 'none',
        }}
      >
        <div style={{ ...maskIcon('/art/icons/castle.svg', color, iconSize), filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.6))' }} />
        {/* 等级星标 */}
        {city.level >= 3 && (
          <div style={{ position: 'absolute', top: '-5px', left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: '2px' }}>
            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#d4a84b' }} />
            {city.level >= 4 && <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#d4a84b' }} />}
            {city.level >= 5 && <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#d4a84b' }} />}
          </div>
        )}
        {/* 围城警告 */}
        {city.is_besieged && (
          <div
            style={{
              position: 'absolute',
              top: '-8px',
              right: '-8px',
              width: '14px',
              height: '14px',
              borderRadius: '50%',
              backgroundColor: '#c85046',
              border: '2px solid #1a1a2e',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'siege-blink 1s ease-in-out infinite',
            }}
          >
            <i className="fa-solid fa-exclamation" style={{ fontSize: '8px', color: '#fff' }}></i>
          </div>
        )}
      </div>

      {/* 城市名 */}
      <div
        style={{
          marginTop: '2px',
          color: '#e8e0d0',
          fontSize: '12px',
          fontWeight: 600,
          textShadow: '0 1px 3px rgba(0,0,0,0.9), 0 0 1px rgba(0,0,0,1)',
          whiteSpace: 'nowrap',
          fontFamily: 'Noto Sans SC, PingFang SC, sans-serif',
          letterSpacing: '0.5px',
        }}
      >
        {city.name}
      </div>

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
