import { Assets, Sprite, Texture } from 'pixi.js'

/** 与 data/hex_map.json 中的 bounds 一致 */
const BOUNDS = {
  minLon: 95.0,
  maxLon: 125.0,
  minLat: 22.0,
  maxLat: 45.0,
}

/** 游戏像素范围（从 hex.ts 的 axialToPixel 推算） */
const GAME_PIXEL_WIDTH = 9145
const GAME_PIXEL_HEIGHT = 4320

/** CartoDB 暗色无标签底图（最适合游戏覆盖层） */
const TILE_URL_TEMPLATE = 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png'

function lonLatToGamePixel(lon: number, lat: number): { x: number; y: number } {
  const nx = (lon - BOUNDS.minLon) / (BOUNDS.maxLon - BOUNDS.minLon)
  const ny = (BOUNDS.maxLat - lat) / (BOUNDS.maxLat - BOUNDS.minLat)
  return {
    x: nx * GAME_PIXEL_WIDTH,
    y: ny * GAME_PIXEL_HEIGHT,
  }
}

function lonToTileX(lon: number, zoom: number): number {
  const n = Math.pow(2, zoom)
  return Math.floor(((lon + 180) / 360) * n)
}

function latToTileY(lat: number, zoom: number): number {
  const n = Math.pow(2, zoom)
  const latRad = (lat * Math.PI) / 180
  return Math.floor(
    ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n
  )
}

function tileXYToLonLat(x: number, y: number, zoom: number): { lon: number; lat: number } {
  const n = Math.pow(2, zoom)
  const lon = (x / n) * 360 - 180
  const latRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n)))
  const lat = (latRad * 180) / Math.PI
  return { lon, lat }
}

function getTileUrl(x: number, y: number, z: number): string {
  const subdomains = ['a', 'b', 'c', 'd']
  const s = subdomains[(x + y) % subdomains.length]
  return TILE_URL_TEMPLATE.replace('{s}', s).replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y))
}

export interface TileInfo {
  x: number
  y: number
  z: number
  url: string
  gameX: number
  gameY: number
  gameW: number
  gameH: number
}

/**
 * 计算覆盖当前地图 bounds 所需的所有瓦片
 * @param zoom 固定 zoom level，默认 6（35 张左右，加载快；7 约 120 张）
 */
export function computeTiles(zoom: number = 6): TileInfo[] {
  const xMin = lonToTileX(BOUNDS.minLon, zoom)
  const xMax = lonToTileX(BOUNDS.maxLon, zoom)
  const yMin = latToTileY(BOUNDS.maxLat, zoom)
  const yMax = latToTileY(BOUNDS.minLat, zoom)

  const tiles: TileInfo[] = []
  for (let tx = xMin; tx <= xMax; tx++) {
    for (let ty = yMin; ty <= yMax; ty++) {
      const tl = tileXYToLonLat(tx, ty, zoom)
      const br = tileXYToLonLat(tx + 1, ty + 1, zoom)
      const gameTL = lonLatToGamePixel(tl.lon, tl.lat)
      const gameBR = lonLatToGamePixel(br.lon, br.lat)
      tiles.push({
        x: tx,
        y: ty,
        z: zoom,
        url: getTileUrl(tx, ty, zoom),
        gameX: gameTL.x,
        gameY: gameTL.y,
        gameW: gameBR.x - gameTL.x,
        gameH: gameBR.y - gameTL.y,
      })
    }
  }
  return tiles
}

const tileTextureCache = new Map<string, Texture>()

/**
 * 预加载瓦片纹理（并行，容错）
 */
export async function preloadTiles(tiles: TileInfo[]): Promise<void> {
  const loads = tiles.map(async (t) => {
    if (tileTextureCache.has(t.url)) return
    try {
      const texture = await Assets.load({ src: t.url, data: { autoGarbageCollect: false } })
      tileTextureCache.set(t.url, texture)
    } catch {
      // CDN 瓦片加载失败静默忽略，地图仍可用纯色底图
    }
  })
  await Promise.all(loads)
}

export function getTileTexture(url: string): Texture | undefined {
  return tileTextureCache.get(url)
}

export function createTileSprite(tile: TileInfo): Sprite | null {
  const texture = tileTextureCache.get(tile.url)
  if (!texture) return null
  const sprite = new Sprite(texture)
  sprite.position.set(tile.gameX, tile.gameY)
  sprite.width = tile.gameW
  sprite.height = tile.gameH
  return sprite
}
