import { useEffect, useRef, useState } from 'react'
import { Application, Container, Graphics, Text, TextStyle } from 'pixi.js'
import type { GameState, HexCoord } from '../types'
import { TERRAIN_COLORS, UI_COLORS, FACTION_COLORS, hexToNumber } from '../theme'
import { HEX_SIZE, axialToPixel, hexNeighbors, hexPoints } from '../utils/hex'
import { CityMarker } from './map/CityMarker'
import { ArmyMarker } from './map/ArmyMarker'

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
      // 补偿 pointy-topped 六角格斜向偏移，让中国版图摆正
      camera.rotation = -0.15
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
      const provinceId = tile?.province_id || null
      const points = hexPoints(x, y, HEX_SIZE)

      // 基础色：州郡颜色（统一板块），无州郡则用地形色
      let fill: number
      if (provinceId && state.provinces?.[provinceId]?.color) {
        fill = hexToNumber(state.provinces[provinceId].color)
        // 地形微调：亮度偏移（保持州郡统一感）
        const terrainBrightness = getTerrainBrightness(terrain)
        fill = adjustBrightness(fill, terrainBrightness)
      } else {
        const colors = TERRAIN_COLORS[terrain] || TERRAIN_COLORS.plain
        fill = colors.fill
      }

      // 势力着色
      const faction = tile?.faction || getFactionAt(state, coord)
      if (faction && faction !== 'neutral') {
        fill = blendColor(fill, hexToNumber(factionColor(faction)), 0.35)
      }

      tilesGraphics.poly(points).fill(fill)
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

    const provinceColor = 0xd4c090 // 亮金色（更明显）
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
              .stroke({ color: provinceColor, width: 3 })
          }
        }
      })
    })
    camera.addChild(provinceGraphics)

    // 3.5 州郡名称标注
    const labelGraphics = new Graphics()
    const labelTexts: { x: number; y: number; text: string; isCity: boolean }[] = []
    // 州名：计算每个 province 的中心
    Object.entries(provinceHexes).forEach(([provId, hexList]) => {
      if (hexList.length === 0) return
      const cx = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).x, 0) / hexList.length
      const cy = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).y, 0) / hexList.length
      const provName = state.provinces?.[provId]?.name || provId
      labelTexts.push({ x: cx, y: cy, text: provName, isCity: false })
    })
    // 城名
    Object.values(state.cities).forEach((city) => {
      const { x, y } = axialToPixel(city.position, HEX_SIZE)
      labelTexts.push({ x, y: y + HEX_SIZE * 1.2, text: city.name, isCity: true })
    })
    // 渲染标注
    labelTexts.forEach(({ x, y, text, isCity }) => {
      const fontSize = isCity ? 10 : 13
      const label = new Text({
        text,
        style: new TextStyle({
          fontSize,
          fontFamily: 'Noto Sans SC, sans-serif',
          fill: isCity ? 0xe8d8b0 : 0xfff8e0,
          stroke: { color: 0x1a1a2e, width: isCity ? 2 : 3 },
          fontWeight: isCity ? 'normal' : 'bold',
          align: 'center',
        }),
      })
      label.anchor.set(0.5)
      label.position.set(x, y)
      camera.addChild(label)
    })
    camera.addChild(labelGraphics)

  }, [state])

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

function getTerrainBrightness(terrain: string): number {
  // 地形亮度偏移：山/林=暗，平原/沙漠=亮
  const bright: Record<string, number> = {
    grass: 0.05, grassland: 0.08, plain: 0.10, desert: 0.12,
    snow: 0.15, tundra: 0.05,
    forest: -0.05, dense_forest: -0.10,
    hill: -0.02, mountain: -0.08, peak: -0.12,
    marsh: -0.03,
    water: -0.05, deep_water: -0.10, river: 0.0,
  }
  return bright[terrain] || 0.0
}

function adjustBrightness(color: number, amount: number): number {
  const r = Math.min(255, Math.max(0, ((color >> 16) & 0xff) + Math.round(amount * 255)))
  const g = Math.min(255, Math.max(0, ((color >> 8) & 0xff) + Math.round(amount * 255)))
  const b = Math.min(255, Math.max(0, (color & 0xff) + Math.round(amount * 255)))
  return (r << 16) | (g << 8) | b
}
