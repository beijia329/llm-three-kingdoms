import { useEffect, useRef, useState } from 'react'
import { Application, Container, Graphics, Text, TextStyle } from 'pixi.js'
import type { GameState, HexCoord } from '../types'
import { FACTION_COLORS, TERRAIN_PARCHMENT, hexToNumber, LW, OP, FS } from '../theme'
import { HEX_SIZE, axialToPixel, hexNeighbors, hexPoints } from '../utils/hex'
import { CityMarker } from './map/CityMarker'
import { ArmyMarker } from './map/ArmyMarker'
import { BattleOverlay } from './map/BattleOverlay'

interface GameMapProps {
  state: GameState | null
  onSelectCity: (cityId: string) => void
  /** 选中地图上的军队（补上「军队完全点不了」的缺口） */
  onSelectArmy?: (armyId: string) => void
  selectedArmyId?: string | null
  /** 当前选中的城池：地图上金色高亮 + 自动居中（审计 §4-4） */
  selectedCityId?: string | null
}

interface Camera {
  x: number
  y: number
  zoom: number
}

export function GameMap({ state, onSelectCity, onSelectArmy, selectedArmyId, selectedCityId }: GameMapProps) {
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
  // [性能 2026-10-03] 记录已渲染的 hex_map 版本。后端只在「占领变城」时改版本，
  // 版本未变则复用整层 Pixi 图形 —— 不再每 0.8s 重画 24000 格（卡顿根因）。
  const renderedHexVersionRef = useRef<string | null>(null)
  // [D3 2026-10-04] zoom 档位门控：格网/地形的可见性按 0.30 / 0.55 两档切换，
  // 跨档才重建该层（档内不重建），线宽随 zoom 换算才能屏幕恒定。
  const renderedZoomBucketRef = useRef<number>(-1)

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

    // [性能 2026-10-03] 版本门控：hex_map 只在占领变城时变，未变则**不重建**
    // 整层 Pixi 图形（24000 格 + 边界 + 州名）。普通 state（军队移动/资源变化）
    // 只走 DOM 标记层更新，这是「缩放平移不跟手」的直接修复。
    // 无地图数据（缓存缺失的异常态）时不动，避免把已有画布清空。
    if (!state.hex_map) return
    const hexVersion = state.hex_map_version ?? 'legacy'
    // [D3] 版本 + zoom 档位双门控：任一变化才重建（档内缩放不重建，避免每滚一格重画）
    const bucketNow = zoomBucket(cameraRef.current.zoom)
    if (hexVersion === renderedHexVersionRef.current && bucketNow === renderedZoomBucketRef.current) return

    const camera = pixiCameraRef.current
    camera.removeChildren()

    // [阶段A 2026-10-03] 取景改「收缩到陆地包围盒」。
    // 原按整张 200×120 网格 fit —— 实测该网格 71%（16970/24000）是深海，
    // 结果陆地只占半个屏幕、四周大片空海（截图 01-overview 取证）。
    // 现按有 province_id 的陆地格包围盒取景，陆地可铺满 70%+ 屏宽。
    if (!didFitRef.current) {
      const vw = containerRef.current?.clientWidth || 1300
      const vh = containerRef.current?.clientHeight || 900
      const allTiles = state.hex_map?.tiles || []
      const landTiles = allTiles.filter((t) => t.province_id)
      const src = landTiles.length > 0 ? landTiles : allTiles
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      if (src.length > 0) {
        src.forEach((t) => {
          const { x, y } = axialToPixel({ q: t.q, r: t.r }, HEX_SIZE)
          if (x < minX) minX = x
          if (x > maxX) maxX = x
          if (y < minY) minY = y
          if (y > maxY) maxY = y
        })
      }
      if (!isFinite(minX)) { minX = 0; minY = 0; maxX = HEX_SIZE * 200; maxY = HEX_SIZE * 120 }
      const pad = HEX_SIZE * 2.5
      const bW = Math.max(1, maxX - minX + pad * 2)
      const bH = Math.max(1, maxY - minY + pad * 2)
      const z = Math.max(0.06, Math.min(1.2, Math.min(vw / bW, vh / bH) * 0.98))
      // 相机：世界点 wx → 屏幕 wx*z + cx。让 (minX-pad) 落在左边距中心处。
      const cx = (vw - bW * z) / 2 - (minX - pad) * z
      const cy = (vh - bH * z) / 2 - (minY - pad) * z
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

    // [D3] 屏幕 px → 世界 px（线宽在屏幕上恒定：世界px = 屏幕px / zoom）
    const zoom = cameraRef.current.zoom
    const w = (screenPx: number) => lw(screenPx, zoom)
    const nBucket = zoomBucket(zoom)

    // 交战国对（L4 交战前线用）：后端下发 [[a,b], ...]
    const atWar = new Set<string>(
      (state.at_war_pairs || []).map(([a, b]) => [a, b].sort().join('|')),
    )

    // 1. 地块底色（羊皮纸陆地 + 深色海）
    const tilesGraphics = new Graphics()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const terrain = tile?.terrain || 'plain'
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      const points = hexPoints(x, y, HEX_SIZE)
      const isWater = terrain === 'water' || terrain === 'deep_water'
      tilesGraphics.poly(points).fill(isWater ? SEA_COLOR : parchmentTint(terrain))
    })
    camera.addChild(tilesGraphics)

    // 2. 地形符号（§4.3 LOD）：<0.30 不画（纸色）；≥0.30 画符号
    if (nBucket >= 1) {
      const terrainGraphics = new Graphics()
      coords.forEach((key) => {
        const tile = tileMap.get(key)
        if (!tile?.province_id) return
        if (!TERRAIN_SYMBOL.has(tile.terrain)) return
        const [q, r] = key.split(',').map(Number)
        const { x, y } = axialToPixel({ q, r }, HEX_SIZE)
        drawTerrainSymbol(terrainGraphics, tile.terrain, x, y, zoom, q, r)
      })
      camera.addChild(terrainGraphics)
    }

    // 3. 势力领地：alpha 0.30（§4.1，让地形透出来；归属靠边界线承担）
    const factionGraphics = new Graphics()
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const tile = tileMap.get(key)
      const fac = tile?.faction || getFactionAt(state, coord)
      if (!fac || fac === 'neutral') return
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      factionGraphics.poly(hexPoints(x, y, HEX_SIZE))
        .fill({ color: hexToNumber(FACTION_COLORS[fac] || '#666666'), alpha: OP.wash })
    })
    camera.addChild(factionGraphics)

    // 4. ★格网（H2）：地块仅 fill 时读不出棋盘结构 —— 给陆地格描一道细发线格网。
    //    线宽屏幕恒定（÷zoom），全图视角（<0.30）不画（LOD）。
    if (nBucket >= 1) {
      const gridGraphics = new Graphics()
      coords.forEach((key) => {
        const tile = tileMap.get(key)
        if (!tile?.province_id) return
        const [q, r] = key.split(',').map(Number)
        const { x, y } = axialToPixel({ q, r }, HEX_SIZE)
        gridGraphics.poly(hexPoints(x, y, HEX_SIZE))
          .stroke({ color: GRID_COLOR, width: w(LW.hair), alpha: 0.20 })
      })
      camera.addChild(gridGraphics)
    }

    // 5. 水系（黄河/长江）：真实走向折线（主干 10 世界px，§4.3）
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
      riverGraphics.stroke({ color: 0x3f6d86, width: 10, alpha: 0.92 })
    })
    camera.addChild(riverGraphics)

    // 6. 州郡界 L2（§4.2）：1.8 屏幕px 实线 INK，alpha 0.72
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
            provinceGraphics.moveTo(x1, y1).lineTo(x2, y2)
              .stroke({ color: INK_COLOR, width: w(LW.mid), alpha: OP.mid })
          }
        }
      })
    })
    camera.addChild(provinceGraphics)

    // 7. 势力界 L3 / 交战前线 L4（§4.2）：3.0 屏幕px；交战对覆盖为朱红 + 外侧亮描边
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
        const x1 = mx+nx, y1 = my+ny, x2 = mx-nx, y2 = my-ny
        const atWarHere =
          !!nbFaction && nbFaction !== 'neutral' &&
          atWar.has([faction, nbFaction].sort().join('|'))
        if (atWarHere) {
          // L4：外侧亮描边（浅底可读）+ 朱红主线
          factionBorderGraphics.moveTo(x1, y1).lineTo(x2, y2)
            .stroke({ color: CORE_LIGHT, width: w(LW.bold) + w(2), alpha: 0.85 })
          factionBorderGraphics.moveTo(x1, y1).lineTo(x2, y2)
            .stroke({ color: WAR_COLOR, width: w(LW.bold), alpha: 1.0 })
        } else {
          factionBorderGraphics.moveTo(x1, y1).lineTo(x2, y2)
            .stroke({
              color: darken(hexToNumber(FACTION_COLORS[faction] || '#666666'), 0.45),
              width: w(LW.bold),
              alpha: OP.strong,
            })
        }
      })
    })
    camera.addChild(factionBorderGraphics)

    // 8. 标注层次：州名（大，衬线感） > 城名（中）
    Object.entries(provinceHexes).forEach(([provId, hexList]) => {
      if (hexList.length === 0) return
      const cx = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).x, 0) / hexList.length
      const cy = hexList.reduce((s, h) => s + axialToPixel(h, HEX_SIZE).y, 0) / hexList.length
      const provName = state.provinces?.[provId]?.name || provId
      // 州名背景底板
      const metric = new Text({ text: provName, style: new TextStyle({ fontSize: FS.title, fontWeight: 'bold' }) })
      const pw = metric.width + 16; const ph = metric.height + 16
      const bg = new Graphics()
      bg.rect(-pw/2, -ph/2, pw, ph).fill({ color: 0x16222b, alpha: 0.7 })
      bg.position.set(cx, cy); camera.addChild(bg)
      // 州名文字（用 map 标注 token 色：墨色 + 米白描边）
      const label = new Text({
        text: provName,
        style: new TextStyle({
          fontSize: FS.title,
          fill: 0x2c2c2c, stroke: { color: 0xefe6d2, width: 4 },
          fontWeight: 'bold', align: 'center',
        }),
      })
      label.anchor.set(0.5); label.position.set(cx, cy)
      camera.addChild(label)
    })
    // 城名（去掉 🏯 emoji，M2；字号走标尺 FS.body）
    Object.values(state.cities).forEach((city) => {
      const { x, y } = axialToPixel(city.position, HEX_SIZE)
      const label = new Text({
        text: city.name,
        style: new TextStyle({
          fontSize: FS.body,
          fill: 0x2f2418, stroke: { color: 0xefe6d2, width: 3 },
          fontWeight: 'bold',
        }),
      })
      label.anchor.set(0.5); label.position.set(x, y + HEX_SIZE * 1.4)
      camera.addChild(label)
    })

    // 记录本次已渲染版本 + zoom 档位，供后续 state 快照 / 档内缩放跳过重建
    renderedHexVersionRef.current = hexVersion
    renderedZoomBucketRef.current = nBucket

  }, [state, pixiReady, camVersion])

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
    // [D3] zoom 跨 LOD 档位（0.30/0.55）时触发一次重渲染，让格网/地形层按新档重建；
    // 档内缩放不重建（避免每滚一格重画整层）。
    const prevBucket = zoomBucket(cameraRef.current.zoom)
    cameraRef.current = clamped
    if (pixiCameraRef.current) {
      pixiCameraRef.current.position.set(clamped.x, clamped.y)
      pixiCameraRef.current.scale.set(clamped.zoom)
    }
    if (overlayRef.current) {
      overlayRef.current.style.transform = `translate(${clamped.x}px, ${clamped.y}px) scale(${clamped.zoom})`
    }
    if (zoomBucket(clamped.zoom) !== prevBucket) setCamVersion((v) => v + 1)
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

  // [交互 2026-10-03] 窗口 resize：此前画布只在挂载时量一次尺寸，
  // 改窗口后 canvas 尺寸不变 → 地图错位/留白。用 ResizeObserver 跟随容器。
  useEffect(() => {
    const container = containerRef.current
    if (!container || !pixiReady) return
    const ro = new ResizeObserver(() => {
      const app = appRef.current
      const w = container.clientWidth
      const h = container.clientHeight
      if (!app || w <= 0 || h <= 0) return
      app.renderer.resize(w, h)
      // 视口变化后重新约束相机，避免地图被拖出可视范围
      syncCamera(cameraRef.current)
    })
    ro.observe(container)
    return () => ro.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pixiReady])

  // [交互 2026-10-03] 选中城池 → 地图自动居中（审计 §4-4：此前点城市只切 tab，地图毫无变化）。
  // 只在"选中的城变了"时聚焦一次，避免每次 state 推送（每回合）都把镜头拽回去。
  const focusedCityRef = useRef<string | null>(null)
  useEffect(() => {
    if (!selectedCityId) { focusedCityRef.current = null; return }
    if (focusedCityRef.current === selectedCityId) return
    const city = state?.cities[selectedCityId]
    const container = containerRef.current
    if (!city || !container || !appRef.current) return
    focusedCityRef.current = selectedCityId
    const vw = container.clientWidth
    const vh = container.clientHeight
    if (vw <= 0 || vh <= 0) return
    const { x, y } = axialToPixel(city.position, HEX_SIZE)
    // 放大到至少 0.42，让城名/剪影可读；已更大则保持
    const z = Math.max(cameraRef.current.zoom, 0.42)
    syncCamera({ x: vw / 2 - x * z, y: vh / 2 - y * z, zoom: z })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCityId, state?.cities])

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
          const hex = army.current_hex!
          const base = axialToPixel(hex, HEX_SIZE)
          // [D3 §4.5④] 同格有城时：军队标记偏移到格右下角（沿 hex 30° 方向）。
          const coCity = Object.values(state.cities).find(
            (c) => c.position.q === hex.q && c.position.r === hex.r,
          )
          const pos = coCity
            ? { x: base.x + HEX_SIZE * 0.45 * Math.cos(Math.PI / 6), y: base.y + HEX_SIZE * 0.45 * Math.sin(Math.PI / 6) }
            : base
          const toCity = army.to_city ? state.cities[army.to_city] : undefined
          const toPos = toCity ? axialToPixel(toCity.position, HEX_SIZE) : null
          return { army, pos, cityLevel: coCity?.level, toPos }
        })
    : []

  // === 战斗回放（v4.1 · 阶段C2）===
  // 后端每回合把近 N 场战斗放进 state.recent_battles；这里对**新出现的**战斗
  // 逐场短回放（每场 ~1.5s），让观众看到「谁打谁 / 结果 / 从哪来打向哪」。
  // 用 battle_id 保序；recent_battles 缺省时（后端未落地）整个叠层不渲染。
  const battles = state?.recent_battles || []
  const [replayIdx, setReplayIdx] = useState(-1)
  const [replayProgress, setReplayProgress] = useState(0)
  const replayKeyRef = useRef('')
  const REPLAY_PER_BATTLE_MS = 1500
  const REPLAY_MAX = 3

  useEffect(() => {
    if (battles.length === 0) {
      setReplayIdx(-1)
      return
    }
    // 只在「出现新战斗」时触发（WS 每次推送都是新数组，不能只看引用）
    const last = battles[battles.length - 1]
    const key = `${last.battle_id}|${last.turn}|${battles.length}`
    if (key === replayKeyRef.current) return
    replayKeyRef.current = key

    let cancelled = false
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
    const start = Math.max(0, battles.length - REPLAY_MAX)
    const run = async () => {
      for (let i = start; i < battles.length; i++) {
        if (cancelled) return
        setReplayIdx(i)
        const t0 = performance.now()
        while (true) {
          if (cancelled) return
          const p = (performance.now() - t0) / REPLAY_PER_BATTLE_MS
          setReplayProgress(Math.min(1, p))
          if (p >= 1) break
          await sleep(50)
        }
      }
      if (cancelled) return
      await sleep(700)
      if (!cancelled) setReplayIdx(-1)
    }
    void run()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.recent_battles, state?.turn])

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
            selected={selectedCityId === city.id}
            onClick={() => onSelectCity(city.id)}
          />
        ))}
        {armyMarkers.map(({ army, pos, cityLevel, toPos }) => (
          <ArmyMarker
            key={army.id}
            army={army}
            x={pos.x}
            y={pos.y}
            zoom={cam.zoom}
            selected={selectedArmyId === army.id}
            onClick={onSelectArmy ? () => onSelectArmy(army.id) : undefined}
            generalName={state?.generals[army.general_id]?.name}
            fromName={army.from_city ? state?.cities[army.from_city]?.name : undefined}
            toName={army.to_city ? state?.cities[army.to_city]?.name : undefined}
            cityLevel={cityLevel}
            toPos={toPos}
          />
        ))}
        {/* 战斗回放层（箭头 + 回放标签），与城市/军队同一世界坐标 transform */}
        {battles.length > 0 && (
          <BattleOverlay
            battles={battles}
            cities={state?.cities || {}}
            activeIndex={replayIdx}
            progress={replayProgress}
            zoom={cam.zoom}
          />
        )}
      </div>

      {/* CSS 动画定义 */}
      <style>{`
        @keyframes city-pulse {
          0%, 100% { filter: drop-shadow(0 0 4px rgba(157,41,51,0.6)); }
          50% { filter: drop-shadow(0 0 12px rgba(157,41,51,0.9)); }
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
        @keyframes city-select-pulse {
          0%, 100% { opacity: 0.65; }
          50% { opacity: 1; }
        }
      `}</style>

      {/* 加载/等待态（审计 §3-10：此前 hex_map 解析期间只有顶栏一行字，地图纯黑无反馈） */}
      {!state && (
        <div style={styles.loadingOverlay}>
          <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '30px', color: 'var(--gold)', marginBottom: '14px' }}></i>
          <div style={{ color: 'var(--text)', fontSize: '15px', fontWeight: 600 }}>正在连接后端并载入地图…</div>
          <div style={{ color: 'var(--text-2)', fontSize: '12px', marginTop: '6px' }}>
            首次载入需解析约 2.4 万格六角地图，请稍候
          </div>
        </div>
      )}
      {state && !pixiReady && (
        <div style={styles.loadingOverlay}>
          <i className="fa-solid fa-spinner fa-spin" style={{ fontSize: '26px', color: 'var(--gold)', marginBottom: '12px' }}></i>
          <div style={{ color: 'var(--text)', fontSize: '14px' }}>正在绘制地图…</div>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  loadingOverlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(10, 20, 26, 0.72)',
    zIndex: 40,
    pointerEvents: 'auto',
    textAlign: 'center',
  },
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
/** [D3] 格网线（H2）、交战前线朱红（L4）、箭头亮芯 */
const GRID_COLOR = 0x6b5a44
const WAR_COLOR = 0xc0392b
const CORE_LIGHT = 0xfbf6ea

/** [D3] 缩放 LOD 档位：<0.30 全图（只纸色）/ 0.30–0.55 中景 / ≥0.55 近景 */
function zoomBucket(z: number): 0 | 1 | 2 {
  if (z < 0.30) return 0
  if (z < 0.55) return 1
  return 2
}

/** [D3] 屏幕 px → 世界 px（线宽屏幕恒定：世界px = 屏幕px / zoom） */
function lw(screenPx: number, zoom: number): number {
  return screenPx / Math.max(zoom, 0.02)
}

/** [D3] 由格坐标生成稳定伪随机 [0,1)，用于地形符号的确定性散布 */
function hexHash(q: number, r: number, salt: number): number {
  const n = Math.sin((q * 127.1 + r * 311.7 + salt * 74.7)) * 43758.5453
  return n - Math.floor(n)
}

/** 需要绘制地形符号的地形集合（§4.3） */
const TERRAIN_SYMBOL = new Set([
  'mountain', 'peak', 'forest', 'dense_forest', 'hill', 'desert', 'marsh',
])

/**
 * [D3] 绘制单个格的地形符号（古法制图符号，§4.3）：
 * 山「人」字∧ + 单侧阴影排线 / 林锥形簇 / 丘缓浪 / 沙漠点阵 / 沼泽短横。
 * 符号几何为世界 px（随 zoom 缩放），仅描边宽度按 1/zoom 换算保证屏幕可见。
 */
function drawTerrainSymbol(
  g: Graphics, terrain: string, x: number, y: number, zoom: number, q: number, r: number,
) {
  const sw = lw(LW.hair, zoom)
  if (terrain === 'mountain' || terrain === 'peak' || terrain === 'hill') {
    const big = terrain !== 'hill'
    const n = terrain === 'peak' ? 3 : (terrain === 'mountain' ? 2 : 1)
    for (let i = 0; i < n; i++) {
      const jitter = hexHash(q, r, i)
      const ox = (i - (n - 1) / 2) * HEX_SIZE * 0.5 + (jitter - 0.5) * 5
      const oy = (hexHash(r, q, i) - 0.5) * 6
      const hh = (big ? 10 : 5) + jitter * 4
      const halfW = hh * 0.62
      const bx = x + ox
      const by = y + oy + hh * 0.4
      // 「人」字 ∧ + 单侧（右）阴影排线
      g.moveTo(bx - halfW, by).lineTo(bx, by - hh).lineTo(bx + halfW, by)
        .stroke({ color: 0x5a4a38, width: sw, alpha: 0.85 })
      g.moveTo(bx, by - hh).lineTo(bx + halfW * 0.5, by - hh * 0.35)
        .stroke({ color: 0x8a7a60, width: sw, alpha: 0.5 })
    }
  } else if (terrain === 'forest' || terrain === 'dense_forest') {
    const n = terrain === 'dense_forest' ? 3 : 2
    for (let i = 0; i < n; i++) {
      const jitter = hexHash(q, r, 10 + i)
      const ox = (i - (n - 1) / 2) * HEX_SIZE * 0.5
      const oy = (hexHash(r, q, 20 + i) - 0.5) * 6
      const hh = 7 + jitter * 3
      const halfW = hh * 0.5
      const bx = x + ox
      const by = y + oy + 4
      // 锥形（针叶）簇
      g.moveTo(bx - halfW, by).lineTo(bx, by - hh).lineTo(bx + halfW, by).closePath()
        .fill({ color: 0x5a7a3e, alpha: 0.35 })
        .stroke({ color: 0x3d6832, width: sw, alpha: 0.8 })
    }
  } else if (terrain === 'desert') {
    const n = 6 + Math.floor(hexHash(q, r, 30) * 5)
    for (let i = 0; i < n; i++) {
      const ox = (hexHash(q, r, 40 + i) - 0.5) * HEX_SIZE * 1.1
      const oy = (hexHash(r, q, 50 + i) - 0.5) * HEX_SIZE * 0.9
      g.circle(x + ox, y + oy, 1.2).fill({ color: 0xa8905a, alpha: 0.5 })
    }
  } else if (terrain === 'marsh') {
    const n = 4 + Math.floor(hexHash(q, r, 60) * 3)
    for (let i = 0; i < n; i++) {
      const ox = (hexHash(q, r, 70 + i) - 0.5) * HEX_SIZE * 0.9
      const oy = (hexHash(r, q, 80 + i) - 0.5) * HEX_SIZE * 0.8
      g.moveTo(x + ox - 2, y + oy).lineTo(x + ox + 2, y + oy)
        .stroke({ color: 0x4a6a2e, width: sw, alpha: 0.55 })
    }
  }
}

/** 三条主河的近似走向（[经度, 纬度]），用于古地图上的水系表现 */
const RIVERS: [number, number][][] = [
  // 黄河（源→渤海湾）：含"几字弯"——兰州→河套北上→潼关/三门峡南下至 ~34.9°N→华北平原东流入海
  [[96, 35.0], [98, 34.8], [100, 35.2], [102, 35.8], [103.8, 36.1], [105.2, 37.5],
   [106.3, 38.5], [107.4, 40.0], [108.5, 40.7], [109.8, 40.6], [111.0, 40.3],
   [111.2, 39.3], [110.8, 37.6], [110.5, 35.6], [110.3, 34.7], [111.4, 34.8],
   [112.4, 34.9], [113.6, 34.9], [114.3, 34.9], [115.0, 35.5], [116.0, 36.4],
   [117.0, 36.8], [118.0, 37.2], [118.6, 37.9], [118.9, 38.5]],   // 末端延伸入渤海
  // 长江（源→长江口）：唐古拉山→金沙江(99°E/27°N)→四川盆地→三峡→武汉→南京→上海入东海
  [[91, 33.5], [93, 32.5], [95, 31.5], [97, 29.5], [98.5, 28.0], [100, 27.0],
   [101.5, 27.0], [103, 28.0], [104.5, 28.8], [106, 29.4], [107.5, 30.1],
   [109, 30.7], [110.5, 30.9], [112, 30.5], [113.5, 30.6], [115, 29.8],
   [116.5, 29.9], [118, 31.2], [119.5, 32.0], [121, 31.6], [121.9, 31.4],
   [122.3, 31.2], [122.6, 31.0]],                              // 末端延伸入东海
  // 珠江（西江→珠江口，广州/番禺入南海）
  [[103.5, 24.5], [105.5, 23.8], [107.5, 23.5], [109.5, 23.3], [111.3, 23.5],
   [112.8, 23.1], [113.6, 22.7], [113.5, 22.1], [113.3, 21.5]],  // 末端南伸入南海
]

/** 羊皮纸底：按地形返回同色系、有区分度的古地图色调。
 *  [阶段A 2026-10-03] 原实现对所有地形返回同一色 0xd9c9a3，导致山地/森林/沙漠/雪地
 *  在图上完全同色。现查 TERRAIN_PARCHMENT 表——保留古地图质感，但能看出地形差异。 */
function parchmentTint(terrain: string): number {
  return TERRAIN_PARCHMENT[terrain] ?? TERRAIN_PARCHMENT._default
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

