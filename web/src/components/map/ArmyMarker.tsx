import { FACTION_COLORS, FACTION_GLOW } from '../../theme'

interface ArmyMarkerProps {
  army: {
    id: string
    faction: string
    soldiers: number
    morale: number
    status: string
  }
  x: number
  y: number
  zoom: number
}

export function ArmyMarker({ army, x, y, zoom }: ArmyMarkerProps) {
  if (army.soldiers <= 0) return null

  const color = FACTION_COLORS[army.faction] || '#888'
  const glow = FACTION_GLOW[army.faction] || 'rgba(128,128,128,0.5)'
  const isRetreat = army.status === 'retreating'
  // [LOD 2026-10-01] 屏幕尺寸随地图缩放（8~28px）
  const markerScreen = Math.max(8, Math.min(28, 64 * zoom * 1.4))
  const scale = markerScreen / (32 * Math.max(zoom, 0.02))
  const size = 14

  const moraleRatio = Math.max(0, Math.min(1, army.morale / 100))
  const moraleColor = moraleRatio > 0.5 ? '#3cb464' : moraleRatio > 0.2 ? '#c8a032' : '#c85046'

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${scale})`,
        transformOrigin: 'center center',
        pointerEvents: 'none',
        zIndex: 15,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      {/* 军队图标容器 */}
      <div
        style={{
          position: 'relative',
          filter: `drop-shadow(0 0 4px ${glow})`,
          animation: isRetreat ? 'retreat-shake 0.8s ease-in-out infinite' : 'none',
        }}
      >
        <div
          style={{
            width: size * 1.15,
            height: size * 1.15,
            backgroundColor: isRetreat ? '#c85046' : color,
            border: '1.5px solid #2a2018',
            boxSizing: 'border-box',
            transform: 'rotate(45deg)',
          }}
        />
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
