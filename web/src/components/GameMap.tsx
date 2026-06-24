import { useEffect, useRef, useState } from 'react'
import { Application, Container, Graphics } from 'pixi.js'
import type { GameState, HexCoord } from '../types'
import { TERRAIN_COLORS, UI_COLORS, hexToNumber } from '../theme'
import { HEX_SIZE, axialToPixel, hexNeighbors, hexPoints } from '../utils/hex'
import { computeTiles, createTileSprite, preloadTiles } from '../utils/tiles'
import { CityMarker } from './map/CityMarker'
import { ArmyMarker } from './map/ArmyMarker'
import type { TileInfo } from '../utils/tiles'

interface GameMapProps {
  state: GameState | null
  onSelectCity: (cityId: string) => void
}

interface Camera {
  x: number
  y: number
  zoom: number
}

export function GameMap({ state, onSelectCity }: GameMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<Application | null>(null)
  const pixiCameraRef = useRef<Container | null>(null)
  const overlayRef = useRef<HTMLDivElement>(null)

  // 相机状态用 ref（不触发 React 重渲染，通过 DOM 操作同步）
  const cameraRef = useRef<Camera>({ x: -960, y: -230, zoom: 0.6 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartRef = useRef<{ x: number; y: number } | null>(null)
  const cameraStartRef = useRef<{ x: number; y: number } | null>(null)

  const [tilesReady, setTilesReady] = useState(false)
  const tilesRef = useRef<TileInfo[]>([])

  // 初始化 Pixi Application
  useEffect(() => {
    const container = containerRef.current
    if (!container || appRef.current) return

    let app: Application | null = null
    let cancelled = false

    const init = async () => {
      app = new Application()
      const width = container.clientWidth
      const height = container.clientHeight
      await app.init({
        background: UI_COLORS.bg,
        width,
        height,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      })
      if (cancelled) {
        app.destroy(true, { children: true, texture: true })
        return
      }
      container.appendChild(app.canvas)
      appRef.current = app

      const camera = new Container()
      pixiCameraRef.current = camera
      app.stage.addChild(camera)

      const c = cameraRef.current
      camera.position.set(c.x, c.y)
      camera.scale.set(c.zoom)

      // 预加载瓦片
      const tiles = computeTiles(6)
      tilesRef.current = tiles
      preloadTiles(tiles).then(() => {
        if (!cancelled) setTilesReady(true)
      })
    }

    init()

    return () => {
      cancelled = true
      if (app) {
        app.destroy(true, { children: true, texture: true })
        app = null
      }
      appRef.current = null
      pixiCameraRef.current = null
    }
  }, [])

  // 渲染 PixiJS 层（地形 + 边界 + 瓦片底图）
  useEffect(() => {
    if (!state || !pixiCameraRef.current) return

    const camera = pixiCameraRef.current
    camera.removeChildren()

    // 0. 瓦片底图
    if (tilesReady) {
      const tileContainer = new Container()
      tilesRef.current.forEach((tile) => {
        const sprite = createTileSprite(tile)
        if (sprite) tileContainer.addChild(sprite)
      })
      camera.addChild(tileContainer)
    }

    // 1. 绘制地块
    const tilesGraphics = new Graphics()
    const tileMap = new Map<string, { terrain: string; faction: string | null; province_id: string | null }>()
    const coords = new Set<string>()

    state.hex_map?.tiles?.forEach((t: HexCoord & { terrain: string; faction: string | null; province_id: string | null }) => {
      const key = `${t.q},${t.r}`
      tileMap.set(key, { terrain: t.terrain, faction: t.faction, province_id: t.province_id })
      coords.add(key)
    })

    Object.values(state.cities).forEach((c) => coords.add(`${c.position.q},${c.position.r}`))
    Object.values(state.armies).forEach((a) => {
      if (a.current_hex) coords.add(`${a.current_hex.q},${a.current_hex.r}`)
    })

    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      const tile = tileMap.get(key)
      const terrain = tile?.terrain || 'plain'
      const colors = TERRAIN_COLORS[terrain] || TERRAIN_COLORS.plain
      const points = hexPoints(x, y, HEX_SIZE)

      const faction = tile?.faction || getFactionAt(state, coord)
      let fill = colors.fill
      if (faction && faction !== 'neutral') {
        fill = blendColor(colors.fill, hexToNumber(factionColor(faction)), 0.20)
      }

      tilesGraphics.poly(points).fill(fill).stroke({ color: 0x3a3a3a, width: 2 })
    })

    camera.addChild(tilesGraphics)

    // 2. 绘制势力边界
    const borderGraphics = new Graphics()
    const drawnEdges = new Set<string>()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const faction = tile?.faction || getFactionAt(state, coord)
      if (!faction || faction === 'neutral') return

      const neighbors = hexNeighbors(coord)
      neighbors.forEach((nb) => {
        const nbKey = `${nb.q},${nb.r}`
        if (!coords.has(nbKey)) return
        const nbTile = tileMap.get(nbKey)
        const nbFaction = nbTile?.faction || getFactionAt(state, nb)
        if (nbFaction === faction) return

        const edgeKey = [key, nbKey].sort().join('|')
        if (drawnEdges.has(edgeKey)) return
        drawnEdges.add(edgeKey)

        const p1 = axialToPixel(coord, HEX_SIZE)
        const p2 = axialToPixel(nb, HEX_SIZE)
        const mx = (p1.x + p2.x) / 2
        const my = (p1.y + p2.y) / 2
        const dx = p2.x - p1.x
        const dy = p2.y - p1.y
        const len = Math.sqrt(dx * dx + dy * dy) || 1
        const nx = (-dy / len) * HEX_SIZE * 0.55
        const ny = (dx / len) * HEX_SIZE * 0.55

        borderGraphics
          .moveTo(mx + nx, my + ny)
          .lineTo(mx - nx, my - ny)
          .stroke({ color: hexToNumber(factionColor(faction)), width: 3 })
      })
    })
    camera.addChild(borderGraphics)

    // 3. 绘制 Province 边界
    const provinceGraphics = new Graphics()
    const provinceHexes: Record<string, HexCoord[]> = {}
    coords.forEach((key) => {
      const tile = tileMap.get(key)
      if (tile?.province_id) {
        provinceHexes[tile.province_id] = provinceHexes[tile.province_id] || []
        const [q, r] = key.split(',').map(Number)
        provinceHexes[tile.province_id].push({ q, r })
      }
    })

    const provinceColor = 0xb4aa8c // 淡金色
    Object.values(provinceHexes).forEach((hexList) => {
      const coordSet = new Set(hexList.map((h) => `${h.q},${h.r}`))
      hexList.forEach((c) => {
        const { x: cx, y: cy } = axialToPixel(c, HEX_SIZE)
        const hPoints = hexPoints(cx, cy, HEX_SIZE)
        for (let i = 0; i < 6; i++) {
          const nbQ = c.q + [1, 1, 0, -1, -1, 0][i]
          const nbR = c.r + [0, -1, -1, 0, 1, 1][i]
          if (!coordSet.has(`${nbQ},${nbR}`)) {
            const x1 = hPoints[i * 2]
            const y1 = hPoints[i * 2 + 1]
            const x2 = hPoints[((i + 1) % 6) * 2]
            const y2 = hPoints[((i + 1) % 6) * 2 + 1]
            provinceGraphics
              .moveTo(x1, y1)
              .lineTo(x2, y2)
              .stroke({ color: provinceColor, width: 2 })
          }
        }
      })
    })
    camera.addChild(provinceGraphics)

    // 4. 绘制水域（空白 hex）
    const waterGraphics = new Graphics()
    const waterColor = 0x1a2a4a
    const hw = state.hex_map?.width || 120
    const hh = state.hex_map?.height || 90
    for (let q = 0; q < hw; q++) {
      for (let r = 0; r < hh; r++) {
        const key = `${q},${r}`
        if (!coords.has(key)) {
          const { x: wx, y: wy } = axialToPixel({ q, r }, HEX_SIZE)
          const wPoints = hexPoints(wx, wy, HEX_SIZE)
          waterGraphics.poly(wPoints).fill(waterColor)
        }
      }
    }
    camera.addChild(waterGraphics)
  }, [state, tilesReady])

  // 相机同步：统一更新 PixiJS + DOM Overlay
  const syncCamera = (next: Camera) => {
    cameraRef.current = next
    if (pixiCameraRef.current) {
      pixiCameraRef.current.position.set(next.x, next.y)
      pixiCameraRef.current.scale.set(next.zoom)
    }
    if (overlayRef.current) {
      overlayRef.current.style.transform = `translate(${next.x}px, ${next.y}px) scale(${next.zoom})`
    }
  }

  // 鼠标/滚轮事件
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = container.getBoundingClientRect()
      const mouseX = e.clientX - rect.left
      const mouseY = e.clientY - rect.top

      const prev = cameraRef.current
      const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
      const newZoom = Math.max(0.08, Math.min(1.5, prev.zoom * zoomFactor))
      const wx = (mouseX - prev.x) / prev.zoom
      const wy = (mouseY - prev.y) / prev.zoom
      syncCamera({
        x: mouseX - wx * newZoom,
        y: mouseY - wy * newZoom,
        zoom: newZoom,
      })
    }

    const handleMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return
      setIsDragging(true)
      dragStartRef.current = { x: e.clientX, y: e.clientY }
      cameraStartRef.current = { x: cameraRef.current.x, y: cameraRef.current.y }
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !dragStartRef.current || !cameraStartRef.current) return
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      syncCamera({
        ...cameraRef.current,
        x: cameraStartRef.current.x + dx,
        y: cameraStartRef.current.y + dy,
      })
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      dragStartRef.current = null
      cameraStartRef.current = null
    }

    container.addEventListener('wheel', handleWheel, { passive: false })
    container.addEventListener('mousedown', handleMouseDown)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      container.removeEventListener('wheel', handleWheel)
      container.removeEventListener('mousedown', handleMouseDown)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  // 计算城市/军队的世界像素坐标
  const cityMarkers = state
    ? Object.values(state.cities).map((city) => {
        const pos = axialToPixel(city.position, HEX_SIZE)
        return { city, pos }
      })
    : []

  const armyMarkers = state
    ? Object.values(state.armies)
        .filter((a) => a.soldiers > 0 && a.current_hex)
        .map((army) => {
          const pos = axialToPixel(army.current_hex!, HEX_SIZE)
          return { army, pos }
        })
    : []

  const cam = cameraRef.current

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        cursor: isDragging ? 'grabbing' : 'grab',
        backgroundColor: UI_COLORS.bg,
      }}
    >
      {/* PixiJS Canvas 由 useEffect 插入 */}

      {/* DOM Overlay 层：城市 + 军队标记 */}
      <div
        ref={overlayRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '1px',
          height: '1px',
          transform: `translate(${cam.x}px, ${cam.y}px) scale(${cam.zoom})`,
          transformOrigin: '0 0',
          pointerEvents: 'none',
        }}
      >
        {cityMarkers.map(({ city, pos }) => (
          <CityMarker
            key={city.id}
            city={city}
            x={pos.x}
            y={pos.y}
            zoom={cam.zoom}
            onClick={() => onSelectCity(city.id)}
          />
        ))}
        {armyMarkers.map(({ army, pos }) => (
          <ArmyMarker key={army.id} army={army} x={pos.x} y={pos.y} zoom={cam.zoom} />
        ))}
      </div>

      {/* CSS 动画定义 */}
      <style>{`
        @keyframes city-pulse {
          0%, 100% { filter: drop-shadow(0 0 4px rgba(200,80,70,0.6)); }
          50% { filter: drop-shadow(0 0 12px rgba(200,80,70,0.9)); }
        }
        @keyframes siege-blink {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(0.85); }
        }
        @keyframes retreat-shake {
          0%, 100% { transform: translate(0, 0); }
          25% { transform: translate(-2px, 1px); }
          50% { transform: translate(2px, -1px); }
          75% { transform: translate(-1px, 2px); }
        }
      `}</style>
    </div>
  )
}

// ---- 辅助函数 ----

function getFactionAt(state: GameState, coord: HexCoord): string | null {
  const city = Object.values(state.cities).find((c) => {
    const dq = Math.abs(c.position.q - coord.q)
    const dr = Math.abs(c.position.r - coord.r)
    const ds = Math.abs(-c.position.q - c.position.r + coord.q + coord.r)
    return Math.max(dq, dr, ds) <= cityRadius(c.level)
  })
  return city?.faction || null
}

function cityRadius(level: number): number {
  if (level <= 1) return 1
  if (level <= 3) return 2
  return 3
}

function factionColor(faction: string): string {
  const colors: Record<string, string> = {
    han: '#FFD700',
    zhangjiao: '#FFFF00',
    dongzhuo: '#8B0000',
    yuanshao: '#FF6600',
    caocao: '#0055A4',
    liubei: '#00AA55',
    sunjian: '#CC0000',
    liubiao: '#8B4513',
    liuyan: '#9370DB',
    gongsunzan: '#FFFFFF',
    mateng: '#4B0082',
    yuanshu: '#FF1493',
    neutral: '#888888',
  }
  return colors[faction] || '#888888'
}

function blendColor(base: number, tint: number, alpha: number): number {
  const br = (base >> 16) & 0xff
  const bg = (base >> 8) & 0xff
  const bb = base & 0xff
  const tr = (tint >> 16) & 0xff
  const tg = (tint >> 8) & 0xff
  const tb = tint & 0xff
  const r = Math.round(br * (1 - alpha) + tr * alpha)
  const g = Math.round(bg * (1 - alpha) + tg * alpha)
  const b = Math.round(bb * (1 - alpha) + tb * alpha)
  return (r << 16) | (g << 8) | b
}
