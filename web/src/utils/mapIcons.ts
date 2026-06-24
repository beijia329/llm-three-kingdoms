import { Assets, Sprite, Texture } from 'pixi.js'

const CDN_BASE = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/svgs/solid'

/** 地图图标名称映射 */
export const MAP_ICONS = {
  city: 'chess-rook',
  citySieged: 'tower-observation',
  armyAttack: 'flag',
  armyRetreat: 'people-arrows',
  gold: 'coins',
  food: 'wheat-awn',
  population: 'users',
  morale: 'heart',
  wall: 'shield-halved',
  crown: 'crown',
  gem: 'gem',
  star: 'star',
  scroll: 'scroll',
  warning: 'triangle-exclamation',
} as const

type IconKey = (typeof MAP_ICONS)[keyof typeof MAP_ICONS]

/** 纹理缓存 */
const textureCache = new Map<string, Texture>()

/**
 * 预加载所有地图图标纹理
 */
export async function preloadMapIcons(): Promise<void> {
  const icons: IconKey[] = [
    MAP_ICONS.city,
    MAP_ICONS.citySieged,
    MAP_ICONS.armyAttack,
    MAP_ICONS.armyRetreat,
    MAP_ICONS.gold,
    MAP_ICONS.food,
    MAP_ICONS.population,
    MAP_ICONS.morale,
    MAP_ICONS.wall,
    MAP_ICONS.crown,
    MAP_ICONS.gem,
    MAP_ICONS.star,
    MAP_ICONS.scroll,
    MAP_ICONS.warning,
  ]

  const loads = icons.map(async (name) => {
    const url = `${CDN_BASE}/${name}.svg`
    try {
      const texture = await Assets.load({ src: url, data: { scaleMode: 'linear' } })
      textureCache.set(name, texture)
    } catch {
      // 若 CDN 加载失败，静默忽略，渲染时会 fallback
    }
  })

  await Promise.all(loads)
}

/**
 * 获取图标纹理（已缓存）
 */
export function getIconTexture(name: IconKey): Texture | undefined {
  return textureCache.get(name)
}

/**
 * 创建一个图标 Sprite，带颜色和大小
 */
export function createIconSprite(
  name: IconKey,
  color: number,
  size: number
): Sprite | null {
  const texture = textureCache.get(name)
  if (!texture) return null

  const sprite = new Sprite(texture)
  sprite.anchor.set(0.5)
  sprite.width = size
  sprite.height = size
  sprite.tint = color
  return sprite
}

/**
 * 绘制进度条（兵力/士气）— Graphics 仍是最佳选择
 */
export function drawProgressBar(
  g: import('pixi.js').Graphics,
  ratio: number,
  barW: number,
  barH: number,
  yOffset: number
): void {
  const hpColor = ratio > 0.5 ? 0x3cb464 : ratio > 0.2 ? 0xc8a032 : 0xc85046
  g.rect(-barW / 2, yOffset, barW, barH).fill(0x282836)
  g.rect(-barW / 2, yOffset, barW * Math.max(0, Math.min(1, ratio)), barH).fill(hpColor)
}
