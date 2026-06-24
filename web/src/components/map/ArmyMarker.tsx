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
  // LOD: 远距离保持可读，近距离自然缩放
  const scale = Math.max(0.6, Math.min(1.4, 0.8 + zoom * 0.8))
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
        <svg width={size * 2} height={size * 2} viewBox={`${-size} ${-size} ${size * 2} ${size * 2}`} style={{ overflow: 'visible' }}>
          {isRetreat ? (
            // 撤退：散开的士兵 + 向左箭头
            <>
              <circle cx={-size * 0.3} cy={-size * 0.2} r={size * 0.25} fill={color} stroke="#e8e0d0" strokeWidth={1} />
              <circle cx={size * 0.2} cy={-size * 0.3} r={size * 0.2} fill={color} stroke="#e8e0d0" strokeWidth={1} />
              <circle cx={0} cy={size * 0.2} r={size * 0.22} fill={color} stroke="#e8e0d0" strokeWidth={1} />
              <circle cx={size * 0.35} cy={size * 0.1} r={size * 0.18} fill={color} stroke="#e8e0d0" strokeWidth={1} />
              {/* 撤退箭头 */}
              <path d={`M${-size * 0.6},0 L${-size * 0.3},${-size * 0.25} L${-size * 0.3},${size * 0.25} Z`} fill="#c85046" />
              <line x1={-size * 0.3} y1={0} x2={size * 0.3} y2={0} stroke="#c85046" strokeWidth={2} />
            </>
          ) : (
            // 进攻：盾牌/旗帜形状
            <>
              <path
                d={`
                  M0,${-size} 
                  L${size * 0.5},${-size * 0.3} 
                  L${size * 0.35},${size * 0.5} 
                  L0,${size * 0.75} 
                  L${-size * 0.35},${size * 0.5} 
                  L${-size * 0.5},${-size * 0.3} 
                  Z
                `}
                fill={color}
                stroke="#e8e0d0"
                strokeWidth={1.5}
              />
              {/* 中心装饰 */}
              <circle cx={0} cy={0} r={size * 0.2} fill="#1a1a2e" stroke="#e8e0d0" strokeWidth={0.8} />
              <path
                d={`M0,${-size * 0.1} L${size * 0.08},${size * 0.05} L${-size * 0.08},${size * 0.05} Z`}
                fill="#d4a84b"
              />
            </>
          )}
        </svg>
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
