import { useMemo } from 'react'
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
  // LOD: 远距离保持较大尺寸，近距离自然缩放
  const scale = Math.max(0.7, Math.min(1.6, 0.9 + zoom * 0.8))

  const maxG = city.level * 1000
  const ratio = Math.min(1, city.garrison / maxG)
  const hpColor = ratio > 0.5 ? '#3cb464' : ratio > 0.2 ? '#c8a032' : '#c85046'

  // 城墙 SVG path
  const castleSvg = useMemo(() => {
    const s = size * 0.5
    return (
      <svg width={size * 1.6} height={size * 1.2} viewBox={`${-size} ${-size} ${size * 2} ${size * 1.5}`} style={{ overflow: 'visible' }}>
        {/* 城墙主体 */}
        <path
          d={`
            M${-s*0.8},${s*0.4} L${-s*0.8},${-s*0.5} 
            L${-s*0.55},${-s*0.5} L${-s*0.55},${-s*0.25} 
            L${-s*0.3},${-s*0.25} L${-s*0.3},${-s*0.5} 
            L${s*0.3},${-s*0.5} L${s*0.3},${-s*0.25} 
            L${s*0.55},${-s*0.25} L${s*0.55},${-s*0.5} 
            L${s*0.8},${-s*0.5} L${s*0.8},${s*0.4} Z
            M${-s*0.22},${s*0.4} A${s*0.22},${s*0.22} 0 0,1 ${s*0.22},${s*0.4} Z
          `}
          fill={color}
          stroke="#e8e0d0"
          strokeWidth={1.5}
          filter="drop-shadow(0 2px 4px rgba(0,0,0,0.6))"
        />
        {/* 城门 */}
        <path
          d={`M${-s*0.22},${s*0.4} A${s*0.22},${s*0.22} 0 0,1 ${s*0.22},${s*0.4} Z`}
          fill="#1a1a2e"
          stroke="#e8e0d0"
          strokeWidth={0.8}
        />
        {/* 等级星标 */}
        {city.level >= 3 && (
          <>
            <circle cx={-s*0.5} cy={-s*0.65} r={s*0.12} fill="#d4a84b" />
            {city.level >= 4 && <circle cx={0} cy={-s*0.7} r={s*0.12} fill="#d4a84b" />}
            {city.level >= 5 && <circle cx={s*0.5} cy={-s*0.65} r={s*0.12} fill="#d4a84b" />}
          </>
        )}
      </svg>
    )
  }, [size, color, city.level])

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
        {castleSvg}
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
