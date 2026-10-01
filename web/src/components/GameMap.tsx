import { useEffect, useRef, useState } from 'react'
import { Application, Container, Graphics, Text, TextStyle } from 'pixi.js'
import type { GameState, HexCoord } from '../types'
import { FACTION_COLORS, hexToNumber } from '../theme'
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
  const cameraRef = useRef<Camera>({ x: -2800, y: -400, zoom: 0.45 })
  const didFitRef = useRef(false)
  // [修复 2026-10-01] 取景改的是 ref（不触发重渲染）→ 标记拿到的 zoom 仍是旧值。
  // 取景后用 camVersion 触发一次重渲染，让标记按新 zoom 计算尺寸。
  const [camVersion, setCamVersion] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  // [修复 2026-10-01] Pixi 初始化是异步的；用 ready 门控渲染，避免首个 state
  // 在 Pixi 就绪前到达导致地图空白且不再重绘。
  const [pixiReady, setPixiReady] = useState(false)

  // [美术 2026-10-01] 改为"古地图"风格：不再散布贴图装饰（读起来像噪点），
  // 地形改用线描山脉表现（见渲染层）。
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
        background: SEA_COLOR,  // 古地图风：深色海（与陆地羊皮纸形成对比）
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
      setPixiReady(true)
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
    if (!state || !pixiReady || !pixiCameraRef.current) return

    const camera = pixiCameraRef.current
    camera.removeChildren()

    // [UX 修复 2026-10-01] 首次渲染自动取景整张地图（原默认 zoom 0.45 只看得到局部，
    // 且缩放下限 0.3 锁死 → 永远看不到全图）。
    if (!didFitRef.current) {
      const vw = containerRef.current?.clientWidth || 1300
      const vh = containerRef.current?.clientHeight || 900
      const mw = state.hex_map?.width || 200
      const mh = state.hex_map?.height || 120
      const wW = HEX_SIZE * (Math.sqrt(3) * (mw - 1) + (Math.sqrt(3) / 2) * (mh - 1))
      const wH = HEX_SIZE * (1.5 * (mh - 1))
      const z = Math.max(0.06, Math.min(1.2, Math.min(vw / wW, vh / wH) * 0.96))
      const cx = (vw - wW * z) / 2
      const cy = (vh - wH * z) / 2
      cameraRef.current = { x: cx, y: cy, zoom: z }
      camera.position.set(cx, cy)
      camera.scale.set(z)
      // [修复 2026-10-01] 同步 DOM 覆盖层（城市/军队标记）。否则取景后标记仍停在
      // 初始 transform 上，看起来像"城池漂到海里"。
      if (overlayRef.current) {
        overlayRef.current.style.transform = `translate(${cx}px, ${cy}px) scale(${z})`
      }
      didFitRef.current = true
      setCamVersion((v) => v + 1)
    }

    // === 渲染层 ===
    // 构建 tileMap + coords
    const tileMap = new Map<string, { terrain: string; faction: string | null; province_id: string | null }>()
    const coords = new Set<string>()
    state.hex_map?.tiles?.forEach((t: HexCoord & { terrain: string; faction: string | null; province_id: string | null }) => {
      const key = `${t.q},${t.r}`; tileMap.set(key, { terrain: t.terrain, faction: t.faction, province_id: t.province_id }); coords.add(key)
    })
    Object.values(state.cities).forEach((c) => coords.add(`${c.position.q},${c.position.r}`))
    Object.values(state.armies).forEach((a) => { if (a.current_hex) coords.add(`${a.current_hex.q},${a.current_hex.r}`) })

    // [修复 2026-10-01] 去掉"斜"的来源：轴向坐标 (q,r) 的矩形地块集合，在屏幕上是
    // 平行四边形（逐行右移半格），其外缘/雾层呈斜边。改为把画布底色 = 海色，使版图
    // 之外自然融为海面，斜边随之消失。着色仍用 province_id 判定。

    // 1. 地块（势力色为主，地形微调）
    const tilesGraphics = new Graphics()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const terrain = tile?.terrain || 'plain'
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      const points = hexPoints(x, y, HEX_SIZE)

      // === 渲染逻辑：古地图风（羊皮纸陆地 + 深色海） ===
      const isWater = terrain === 'water' || terrain === 'deep_water'
      tilesGraphics.poly(points).fill(isWater ? SEA_COLOR : parchmentTint(terrain))
    })
    camera.addChild(tilesGraphics)

    // 势力领地：半透明色块叠在羊皮纸上（参考三国志：纯色填充 + 深色边界）
    const factionGraphics = new Graphics()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const fac = tile?.faction || getFactionAt(state, coord)
      if (!fac || fac === 'neutral') return
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      factionGraphics.poly(hexPoints(x, y, HEX_SIZE))
        .fill({ color: hexToNumber(FACTION_COLORS[fac] || '#666666'), alpha: 0.42 })
    })
    camera.addChild(factionGraphics)

    // 河流（黄河/长江）：真实走向的经纬度折线 → 格坐标 → 像素
    const riverGraphics = new Graphics()
    RIVERS.forEach((pts) => {
      const px = pts.map(([lon, lat]) => {
        const r = (54 - lat) * 119 / 38
        const q = (lon - 60) * 199 / 90 - r / 2
        return axialToPixel({ q, r }, HEX_SIZE)
      })
      if (px.length < 2) return
      const dense: { x: number; y: number }[] = []
      for (let i = 0; i < px.length - 1; i++) {
        const a = px[i], b = px[i + 1]
        for (let t = 0; t < 8; t++) {
          const f = t / 8
          dense.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f })
        }
      }
      dense.push(px[px.length - 1])
      riverGraphics.moveTo(dense[0].x, dense[0].y)
      for (let i = 1; i < dense.length; i++) riverGraphics.lineTo(dense[i].x, dense[i].y)
      riverGraphics.stroke({ color: 0x3f6d86, width: 13, alpha: 0.92 })
    })
    camera.addChild(riverGraphics)

    // [美术 2026-10-01] 线描山脉在"整图缩放"下会糊成噪点，暂不绘制；
    // 保持"平铺羊皮纸 + 墨线省界 + 半透明势力色"的干净古地图风（参考三国志12）。

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
          .stroke({ color: darken(hexToNumber(FACTION_COLORS[faction] || '#666666'), 0.55), width: 3, alpha: 0.9 })
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
            // [美术 2026-10-01] 实线墨线（原来虚线在整图缩放下变成点点、看不清）
            provinceGraphics.moveTo(x1, y1).lineTo(x2, y2)
              .stroke({ color: INK_COLOR, width: 1.2, alpha: 0.85 })
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
      const pw = metric.width + 16; const ph = metric.height + 16
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

  }, [state, pixiReady])

  // 地图像素边界（世界坐标）— 动态从 hex_map 读取
  const hw = state?.hex_map?.width || 180
  const hh = state?.hex_map?.height || 128
  const worldW = HEX_SIZE * (Math.sqrt(3) * (hw - 1) + Math.sqrt(3) / 2 * (hh - 1))
  const worldH = HEX_SIZE * (1.5 * (hh - 1))
  const PAD = HEX_SIZE * 90

  const clampCamera = (cam: Camera, viewW: number, viewH: number): Camera => {
    const z = Math.max(0.06, Math.min(1.2, cam.zoom))
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
      const newZoom = Math.max(0.06, Math.min(1.2, prev.zoom * zoomFactor))
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
        backgroundColor: '#1b3a4b',
      }}
    >
      {/* PixiJS Canvas 由 useEffect 插入 */}

      {/* DOM Overlay 层：城市 + 军队标记 */}
      <div
        ref={overlayRef}
        data-cam={camVersion}
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

/** 颜色按系数压暗（用于弱化境外陆地） */
function darken(color: number, factor: number): number {  const r = Math.min(255, Math.round(((color >> 16) & 0xff) * factor))
  const g = Math.min(255, Math.round(((color >> 8) & 0xff) * factor))
  const b = Math.min(255, Math.round((color & 0xff) * factor))
  return (r << 16) | (g << 8) | b
}

/** 古地图配色：深色海 + 墨线 */
const SEA_COLOR = 0x1b3a4b
const INK_COLOR = 0x4a3a28

/** 三条主河的近似走向（[经度, 纬度]），用于古地图上的水系表现 */
const RIVERS: [number, number][][] = [
  // 黄河（源→渤海湾）：含"几字弯"——兰州→河套北上→潼关/三门峡南下至 ~34.9°N→华北平原东流入海
  [[96, 35.0], [98, 34.8], [100, 35.2], [102, 35.8], [103.8, 36.1], [105.2, 37.5],
   [106.3, 38.5], [107.4, 40.0], [108.5, 40.7], [109.8, 40.6], [111.0, 40.3],
   [111.2, 39.3], [110.8, 37.6], [110.5, 35.6], [110.3, 34.7], [111.4, 34.8],
   [112.4, 34.9], [113.6, 34.9], [114.3, 34.9], [115.0, 35.5], [116.0, 36.4],
   [117.0, 36.8], [118.0, 37.2], [119.1, 37.8]],
  // 长江（源→长江口）：唐古拉山→金沙江(99°E/27°N)→四川盆地→三峡→武汉→南京→上海
  [[91, 33.5], [93, 32.5], [95, 31.5], [97, 29.5], [98.5, 28.0], [100, 27.0],
   [101.5, 27.0], [103, 28.0], [104.5, 28.8], [106, 29.4], [107.5, 30.1],
   [109, 30.7], [110.5, 30.9], [112, 30.5], [113.5, 30.6], [115, 29.8],
   [116.5, 29.9], [118, 31.2], [119.5, 32.0], [121, 31.6], [121.9, 31.4]],
  // 珠江（西江→珠江口，广州/番禺入海）
  [[103.5, 24.5], [105.5, 23.8], [107.5, 23.5], [109.5, 23.3], [111.3, 23.5],
   [112.8, 23.1], [113.6, 22.7]],
]

/** 羊皮纸底：整片统一（参考三国志12 古地图——地形不做花斑，只靠墨线省界与势力色） */
function parchmentTint(_terrain: string): number {
  return 0xd9c9a3
}

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

export function computeChinaMask(
  tileMap: Map<string, { terrain: string; faction: string | null; province_id: string | null }>,
  width: number,
  height: number,
): Set<string> {
  /**
   * 计算中国版图内部格子集合。
   *
   * 策略：
   * 1. 所有有 province_id 的格子视为中国版图。
   * 2. 没有 province_id 的水格，如果从地图边界能通过"无 province_id 的水格"
   *    蔓延到它，说明是外海；否则是内陆水域，也归入中国版图。
   * 3. 其余格子为境外。
   *
   * 这比单纯依赖 province_id 更可靠，能把内陆湖/河也渲染成大陆色。
   */
  const isWater = (terrain: string) => terrain === 'water' || terrain === 'deep_water'

  // 无 province_id 的水格
  const waterWithoutProv = new Set<string>()
  for (let r = 0; r < height; r++) {
    for (let q = 0; q < width; q++) {
      const key = `${q},${r}`
      const tile = tileMap.get(key)
      if (tile && isWater(tile.terrain) && !tile.province_id) {
        waterWithoutProv.add(key)
      }
    }
  }

  // 从边界 flood fill，找出外海水格
  const exteriorWater = new Set<string>()
  const queue: HexCoord[] = []
  for (let q = 0; q < width; q++) {
    const k1 = `${q},0`
    const k2 = `${q},${height - 1}`
    if (waterWithoutProv.has(k1) && !exteriorWater.has(k1)) queue.push({ q, r: 0 })
    if (waterWithoutProv.has(k2) && !exteriorWater.has(k2)) queue.push({ q, r: height - 1 })
  }
  for (let r = 1; r < height - 1; r++) {
    const k1 = `0,${r}`
    const k2 = `${width - 1},${r}`
    if (waterWithoutProv.has(k1) && !exteriorWater.has(k1)) queue.push({ q: 0, r })
    if (waterWithoutProv.has(k2) && !exteriorWater.has(k2)) queue.push({ q: width - 1, r })
  }

  let head = 0
  while (head < queue.length) {
    const c = queue[head++]
    const key = `${c.q},${c.r}`
    if (exteriorWater.has(key)) continue
    exteriorWater.add(key)

    hexNeighbors(c).forEach((nb) => {
      if (nb.q < 0 || nb.q >= width || nb.r < 0 || nb.r >= height) return
      const nbKey = `${nb.q},${nb.r}`
      if (exteriorWater.has(nbKey) || !waterWithoutProv.has(nbKey)) return
      queue.push(nb)
    })
  }

  // 中国版图 = 有 province_id 的格子 + 被 province_id 陆地闭合环绕的内陆水格
  const china = new Set<string>()
  for (let r = 0; r < height; r++) {
    for (let q = 0; q < width; q++) {
      const key = `${q},${r}`
      const tile = tileMap.get(key)
      if (tile?.province_id) {
        china.add(key)
      } else if (tile && isWater(tile.terrain) && !exteriorWater.has(key)) {
        china.add(key)
      }
    }
  }
  return china
}

