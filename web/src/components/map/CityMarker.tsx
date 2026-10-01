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
  // [LOD 2026-10-01] 标记屏幕尺寸随地图缩放（13~30px）；过小时隐藏城名。
  const markerScreen = Math.max(13, Math.min(30, 64 * zoom * 1.6))
  const scale = markerScreen / (34 * Math.max(zoom, 0.02))
  const showName = markerScreen > 17
  // [美术 2026-10-01] 不用图标：小圆点（势力色）+ 城名；等级用点径表示（参考三国志极简标记）。
  const dot = 9 + Math.min(city.level, 5) * 1.8

  const maxG = city.level * 1000
  const ratio = Math.min(1, city.garrison / maxG)
  const hpColor = ratio > 0.5 ? '#3cb464' : ratio > 0.2 ? '#c8a032' : '#c85046'

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
      {/* 城池标记：小圆点（势力色），点径表示等级，不用图标 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 5px ${glow})`,
          animation: city.is_besieged ? 'city-pulse 2s ease-in-out infinite' : 'none',
        }}
      >
        <div
          style={{
            width: `${dot}px`,
            height: `${dot}px`,
            borderRadius: '50%',
            backgroundColor: color,
            border: '1.5px solid #2a2018',
            boxSizing: 'border-box',
          }}
        />
        {/* 围城警告 */}
        {city.is_besieged && (
          <div
            style={{
              position: 'absolute',
              top: '-6px',
              right: '-8px',
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: '#c85046',
              border: '2px solid #2a2018',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              animation: 'siege-blink 1s ease-in-out infinite',
            }}
          >
            <i className="fa-solid fa-exclamation" style={{ fontSize: '7px', color: '#fff' }}></i>
          </div>
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
