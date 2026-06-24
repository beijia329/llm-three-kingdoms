import { useEffect, useRef, useState } from 'react'
import { Application, Container, Graphics, Text } from 'pixi.js'
import type { GameState, HexCoord } from '../types'
import { FACTION_COLORS, TERRAIN_COLORS, UI_COLORS, hexToNumber } from '../utils/colors'
import { HEX_SIZE, axialToPixel, hexNeighbors, hexPoints } from '../utils/hex'

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
  const cameraRef = useRef<Container | null>(null)
  const [camera, setCamera] = useState<Camera>({ x: -900, y: -500, zoom: 0.3 })
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
      cameraRef.current = camera
      app.stage.addChild(camera)

      camera.position.set(-900, -500)
      camera.scale.set(0.3)
    }

    init()

    return () => {
      cancelled = true
      if (app) {
        app.destroy(true, { children: true, texture: true })
        app = null
      }
      appRef.current = null
      cameraRef.current = null
    }
  }, [])

  // 同步相机状态到 Pixi
  useEffect(() => {
    const pixiCamera = cameraRef.current
    if (!pixiCamera) return
    pixiCamera.position.set(camera.x, camera.y)
    pixiCamera.scale.set(camera.zoom)
  }, [camera])

  // 渲染地图
  useEffect(() => {
    if (!state || !cameraRef.current) return

    const camera = cameraRef.current
    camera.removeChildren()

    const { cities, armies } = state

    // 1. 绘制地块
    const tilesGraphics = new Graphics()
    const tileMap = new Map<string, { terrain: string; faction: string | null }>()
    const coords = new Set<string>()

    // 收集实际地块数据
    state.hex_map?.tiles?.forEach((t: HexCoord & { terrain: string; faction: string | null }) => {
      const key = `${t.q},${t.r}`
      tileMap.set(key, { terrain: t.terrain, faction: t.faction })
      coords.add(key)
    })

    // 补充城市与军队所在位置确保可见
    Object.values(cities).forEach((c) => coords.add(`${c.position.q},${c.position.r}`))
    Object.values(armies).forEach((a) => {
      if (a.current_hex) coords.add(`${a.current_hex.q},${a.current_hex.r}`)
    })

    // 绘制六角格
    coords.forEach((key) => {
      const [q, r] = key.split(',').map(Number)
      const coord: HexCoord = { q, r }
      const { x, y } = axialToPixel(coord, HEX_SIZE)
      const tile = tileMap.get(key)
      const terrain = tile?.terrain || 'plain'
      const colors = TERRAIN_COLORS[terrain] || TERRAIN_COLORS.plain
      const points = hexPoints(x, y, HEX_SIZE)

      // 势力颜色淡化填充
      const faction = tile?.faction || getFactionAt(state, coord)
      let fill = colors.fill
      if (faction && faction !== 'neutral') {
        fill = blendColor(colors.fill, hexToNumber(FACTION_COLORS[faction] || '#888888'), 0.15)
      }

      tilesGraphics.poly(points).fill(fill).stroke({ color: colors.border, width: 1 })
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
          .stroke({ color: hexToNumber(FACTION_COLORS[faction] || '#888888'), width: 3 })
      })
    })
    camera.addChild(borderGraphics)

    // 3. 绘制城市
    Object.values(cities).forEach((city) => {
      const { x, y } = axialToPixel(city.position, HEX_SIZE)
      const cityContainer = new Container()
      cityContainer.position.set(x, y)

      const color = hexToNumber(FACTION_COLORS[city.faction] || '#888888')
      const radius = Math.max(4, Math.min(18, (5 + city.level * 1.8)))

      const circle = new Graphics()
      circle.circle(0, 0, radius).fill(color).stroke({ color: 0xe8e0d0, width: 2 })
      cityContainer.addChild(circle)

      if (city.is_besieged) {
        const ring = new Graphics()
        ring.circle(0, 0, radius + 4).stroke({ color: 0xc85046, width: 2 })
        cityContainer.addChild(ring)
      }

      // 城市名
      const nameText = new Text({
        text: city.name,
        style: { fontSize: 12, fill: '#e8e0d0', fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif' },
      })
      nameText.anchor.set(0.5, 1)
      nameText.position.set(0, -radius - 2)
      cityContainer.addChild(nameText)

      // 兵力条
      const maxG = city.level * 1000
      const ratio = Math.min(1, city.garrison / maxG)
      const barW = 24
      const barH = 4
      const bar = new Graphics()
      bar.rect(-barW / 2, radius + 3, barW, barH).fill(0x282836)
      const hpColor = ratio > 0.5 ? 0x3cb464 : ratio > 0.2 ? 0xc8a032 : 0xc85046
      bar.rect(-barW / 2, radius + 3, barW * ratio, barH).fill(hpColor)
      cityContainer.addChild(bar)

      // 点击区域
      const hitArea = new Graphics()
      hitArea.circle(0, 0, radius + 6).fill({ color: 0xffffff, alpha: 0.001 })
      hitArea.eventMode = 'static'
      hitArea.cursor = 'pointer'
      hitArea.on('pointerdown', () => onSelectCity(city.id))
      cityContainer.addChild(hitArea)

      camera.addChild(cityContainer)
    })

    // 4. 绘制军队
    Object.values(armies).forEach((army) => {
      if (army.soldiers <= 0) return
      const pos = army.current_hex
        ? axialToPixel(army.current_hex, HEX_SIZE)
        : cities[army.to_city]
          ? axialToPixel(cities[army.to_city].position, HEX_SIZE)
          : null
      if (!pos) return

      const armyContainer = new Container()
      armyContainer.position.set(pos.x, pos.y)

      const color = hexToNumber(FACTION_COLORS[army.faction] || '#888888')
      const size = Math.max(4, Math.min(14, 7))

      const triangle = new Graphics()
      const points = army.status === 'retreating'
        ? [0, size, -size * 0.9, -size * 0.6, size * 0.9, -size * 0.6]
        : [0, -size, -size * 0.9, size * 0.6, size * 0.9, size * 0.6]
      triangle.poly(points).fill(color).stroke({ color: 0xe8e0d0, width: 1 })
      armyContainer.addChild(triangle)

      const soldierText = new Text({
        text: String(army.soldiers),
        style: { fontSize: 10, fill: '#e8e0d0', fontFamily: 'sans-serif' },
      })
      soldierText.anchor.set(0.5, 1)
      soldierText.position.set(0, -size - 1)
      armyContainer.addChild(soldierText)

      // 士气条
      const ratio = Math.max(0, Math.min(1, army.morale / 100))
      const barW = 18
      const barH = 3
      const moraleBar = new Graphics()
      moraleBar.rect(-barW / 2, size + 2, barW, barH).fill(0x282836)
      const moraleColor = ratio > 0.5 ? 0x3cb464 : ratio > 0.2 ? 0xc8a032 : 0xc85046
      moraleBar.rect(-barW / 2, size + 2, barW * ratio, barH).fill(moraleColor)
      armyContainer.addChild(moraleBar)

      camera.addChild(armyContainer)
    })
  }, [state, onSelectCity])

  // 鼠标/滚轮事件
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault()
      const rect = container.getBoundingClientRect()
      const mouseX = e.clientX - rect.left
      const mouseY = e.clientY - rect.top

      setCamera((prev) => {
        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
        const newZoom = Math.max(0.08, Math.min(1.5, prev.zoom * zoomFactor))
        const wx = (mouseX - prev.x) / prev.zoom
        const wy = (mouseY - prev.y) / prev.zoom
        return {
          x: mouseX - wx * newZoom,
          y: mouseY - wy * newZoom,
          zoom: newZoom,
        }
      })
    }

    const handleMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return
      setIsDragging(true)
      dragStartRef.current = { x: e.clientX, y: e.clientY }
      cameraStartRef.current = { x: camera.x, y: camera.y }
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !dragStartRef.current || !cameraStartRef.current) return
      const dx = e.clientX - dragStartRef.current.x
      const dy = e.clientY - dragStartRef.current.y
      setCamera((prev) => ({
        ...prev,
        x: cameraStartRef.current!.x + dx,
        y: cameraStartRef.current!.y + dy,
      }))
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
  }, [camera.x, camera.y, isDragging])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
    />
  )
}

function getFactionAt(state: GameState, coord: HexCoord): string | null {
  // 查找控制该地块的城市
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
