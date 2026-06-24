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
  const cameraRef = useRef<Camera>({ x: -4200, y: -600, zoom: 0.45 })
  const [isDragging, setIsDragging] = useState(false)
  const isDraggingRef = useRef(false)
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

    // === 渲染层 ===
    // 构建 tileMap + coords
    const tileMap = new Map<string, { terrain: string; faction: string | null; province_id: string | null }>()
    const coords = new Set<string>()
    state.hex_map?.tiles?.forEach((t: HexCoord & { terrain: string; faction: string | null; province_id: string | null }) => {
      const key = `${t.q},${t.r}`; tileMap.set(key, { terrain: t.terrain, faction: t.faction, province_id: t.province_id }); coords.add(key)
    })
    Object.values(state.cities).forEach((c) => coords.add(`${c.position.q},${c.position.r}`))
    Object.values(state.armies).forEach((a) => { if (a.current_hex) coords.add(`${a.current_hex.q},${a.current_hex.r}`) })

    // 0. 未探索外围（中国境外灰色迷雾——无 province_id 的水域格 + 超出地图的虚拟格）
    const fogGraphics = new Graphics()
    const hw = state.hex_map?.width || 180
    const hh = state.hex_map?.height || 128
    const FOG_MARGIN = 50  // 额外虚拟格 — 大范围未探索区域
    for (let q = -FOG_MARGIN; q < hw + FOG_MARGIN; q++) {
      for (let r = -FOG_MARGIN; r < hh + FOG_MARGIN; r++) {
        const key = `${q},${r}`
        const tile = tileMap.get(key)
        // 境外 = 超出网格 或 水域且无 province
        const isOutside = q < 0 || q >= hw || r < 0 || r >= hh ||
          (tile && tile.province_id === null &&
           (tile.terrain === 'water' || tile.terrain === 'deep_water'))
        if (isOutside) {
          const { x: fx, y: fy } = axialToPixel({ q, r }, HEX_SIZE)
          fogGraphics.poly(hexPoints(fx, fy, HEX_SIZE)).fill(0x888c94)
        }
      }
    }
    camera.addChild(fogGraphics)

    // 1. 地块（势力色为主，地形微调）
    const tilesGraphics = new Graphics()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const terrain = tile?.terrain || 'plain'
      const provinceId = tile?.province_id || null
      const faction = tile?.faction || getFactionAt(state, coord)
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      const points = hexPoints(x, y, HEX_SIZE)

      // 基础色：势力色优先，无势力则用地形色
      let fill: number
      if (faction && faction !== 'neutral') {
        fill = hexToNumber(factionColor(faction))
      } else {
        fill = (TERRAIN_COLORS[terrain] || TERRAIN_COLORS.plain).fill
      }
      tilesGraphics.poly(points).fill(fill)
    })
    camera.addChild(tilesGraphics)

    // 2. 势力边界（最粗，势力色）
    const factionBorderGraphics = new Graphics()
    const drawnFactionEdges = new Set<string>()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const faction = tile?.faction || getFactionAt(state, coord)
      if (!faction || faction === 'neutral') return
      hexNeighbors(coord).forEach((nb) => {
        const nbKey = `${nb.q},${nb.r}`
        if (!coords.has(nbKey)) return
        const nbFaction = tileMap.get(nbKey)?.faction || getFactionAt(state, nb)
        if (nbFaction === faction) return
        const edgeKey = [key, nbKey].sort().join('|')
        if (drawnFactionEdges.has(edgeKey)) return
        drawnFactionEdges.add(edgeKey)
        const p1 = axialToPixel(coord, HEX_SIZE)
        const p2 = axialToPixel(nb, HEX_SIZE)
        const mx = (p1.x + p2.x) / 2; const my = (p1.y + p2.y) / 2
        const dx = p2.x - p1.x; const dy = p2.y - p1.y
        const len = Math.sqrt(dx*dx+dy*dy) || 1
        const nx = (-dy/len) * HEX_SIZE * 0.55
        const ny = (dx/len) * HEX_SIZE * 0.55
        factionBorderGraphics.moveTo(mx+nx, my+ny).lineTo(mx-nx, my-ny)
          .stroke({ color: hexToNumber(factionColor(faction)), width: 6, alpha: 0.9 })
      })
    })
    camera.addChild(factionBorderGraphics)

    // 3. 州郡边界（中等粗细，淡金色虚线感）
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
    Object.values(provinceHexes).forEach((hexList) => {
      const coordSet = new Set(hexList.map((h) => `${h.q},${h.r}`))
      hexList.forEach((c) => {
        const { x: cx, y: cy } = axialToPixel(c, HEX_SIZE)
        const hPts = hexPoints(cx, cy, HEX_SIZE)
        for (let i = 0; i < 6; i++) {
          const nbQ = c.q + [1,1,0,-1,-1,0][i]; const nbR = c.r + [0,-1,-1,0,1,1][i]
          if (!coordSet.has(`${nbQ},${nbR}`)) {
            const x1 = hPts[i*2]; const y1 = hPts[i*2+1]
            const x2 = hPts[((i+1)%6)*2]; const y2 = hPts[((i+1)%6)*2+1]
            // 虚线效果：分段绘制
            const segs = 3
            for (let s = 0; s < segs; s++) {
              const t0 = s / segs; const t1 = (s + 0.6) / segs
              provinceGraphics.moveTo(x1+(x2-x1)*t0, y1+(y2-y1)*t0)
                .lineTo(x1+(x2-x1)*t1, y1+(y2-y1)*t1)
                .stroke({ color: 0xe8d8a0, width: 2.5, alpha: 0.85 })
            }
          }
        }
      })
    })
    camera.addChild(provinceGraphics)

    // 4. 标注层次：州名（大） > 城名（中） 
    Object.entries(provinceHexes).forEach(([provId, hexList]) => {
      if (hexList.length === 0) return
      const cx = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).x, 0) / hexList.length
      const cy = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).y, 0) / hexList.length
      const provName = state.provinces?.[provId]?.name || provId
      // 州名背景底板
      const metric = new Text({ text: provName, style: new TextStyle({ fontSize: 20, fontFamily: 'Noto Sans SC', fontWeight: 'bold' }) })
      const pw = metric.width + 16; const ph = metric.height + 8
      const bg = new Graphics()
      bg.rect(-pw/2, -ph/2, pw, ph).fill({ color: 0x1a1a2e, alpha: 0.7 })
      bg.position.set(cx, cy); camera.addChild(bg)
      // 州名文字
      const label = new Text({
        text: provName,
        style: new TextStyle({
          fontSize: 20, fontFamily: 'Noto Sans SC, sans-serif',
          fill: 0xffd700, stroke: { color: 0x000000, width: 4 },
          fontWeight: 'bold', align: 'center',
        }),
      })
      label.anchor.set(0.5); label.position.set(cx, cy)
      camera.addChild(label)
    })
    // 城名（带底色）
    Object.values(state.cities).forEach((city) => {
      const { x, y } = axialToPixel(city.position, HEX_SIZE)
      const cityText = `🏯 ${city.name}`
      const label = new Text({
        text: cityText,
        style: new TextStyle({
          fontSize: 14, fontFamily: 'Noto Sans SC, sans-serif',
          fill: 0xffffff, stroke: { color: 0x000000, width: 3 },
          fontWeight: 'bold',
        }),
      })
      label.anchor.set(0.5); label.position.set(x, y + HEX_SIZE * 1.4)
      camera.addChild(label)
    })

  }, [state])

  // 地图像素边界（世界坐标）— 动态从 hex_map 读取
  const hw = state?.hex_map?.width || 180
  const hh = state?.hex_map?.height || 128
  const worldW = HEX_SIZE * (Math.sqrt(3) * (hw - 1) + Math.sqrt(3) / 2 * (hh - 1))
  const worldH = HEX_SIZE * (1.5 * (hh - 1))
  const PAD = HEX_SIZE * 60

  const clampCamera = (cam: Camera, viewW: number, viewH: number): Camera => {
    const z = Math.max(0.3, Math.min(1.2, cam.zoom))
    // 摄像机 cx 使得世界坐标 x 映射到屏幕 (x+cx)*z
    // 可见范围: world x ∈ [-cx, (viewW/z)-cx]
    // 约束: 左边界 world x = -PAD 可见 → cx ≤ PAD
    //       右边界 world x = worldW+PAD 可见 → cx ≥ viewW/z - (worldW+PAD)
    const cxMin = viewW / z - (worldW + PAD)
    const cxMax = PAD
    const cyMin = viewH / z - (worldH + PAD)
    const cyMax = PAD
    return {
      x: Math.min(cxMax, Math.max(cxMin, cam.x)),
      y: Math.min(cyMax, Math.max(cyMin, cam.y)),
      zoom: z,
    }
  }

  // 相机同步 + 约束
  const syncCamera = (next: Camera) => {
    const container = containerRef.current
    const vw = container?.clientWidth || 1200
    const vh = container?.clientHeight || 800
    const clamped = clampCamera(next, vw, vh)
    cameraRef.current = clamped
    if (pixiCameraRef.current) {
      pixiCameraRef.current.position.set(clamped.x, clamped.y)
      pixiCameraRef.current.scale.set(clamped.zoom)
    }
    if (overlayRef.current) {
      overlayRef.current.style.transform = `translate(${clamped.x}px, ${clamped.y}px) scale(${clamped.zoom})`
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
      const newZoom = Math.max(0.3, Math.min(1.2, prev.zoom * zoomFactor))
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
      isDraggingRef.current = true
      dragStartRef.current = { x: e.clientX, y: e.clientY }
      cameraStartRef.current = { x: cameraRef.current.x, y: cameraRef.current.y }
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current || !dragStartRef.current || !cameraStartRef.current) return
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
      isDraggingRef.current = false
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
  }, [])  // 只绑定一次，不依赖 isDragging

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
    zhangjiao: '#FFD700', han: '#DAA520',
    caocao: '#6b3020', liubei: '#2d7a3a',
    sunjian: '#8B2020', yuanshao: '#CC7733',
    gongsunzan: '#c4b090', mateng: '#5a3070',
    dongzhuo: '#3a3040', liubiao: '#7a6040',
    liuyan: '#5a5070', yuanshu: '#b04060',
    neutral: '#666666',
  }
  return colors[faction] || '#666666'
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
