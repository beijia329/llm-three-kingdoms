/**
 * 游戏视觉主题系统（Design Token）
 * 
 * 参考：三国志14（古典水墨风）、文明6（卡通渲染+清晰边界）
 * 目标：建立统一的视觉语言，支撑未来素材替换
 */

// === 势力色板 ===
export const FACTION_COLORS: Record<string, string> = {
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

export const FACTIONS: Record<string, string> = {
  han: '汉室',
  zhangjiao: '张角',
  dongzhuo: '董卓',
  yuanshao: '袁绍',
  caocao: '曹操',
  liubei: '刘备',
  sunjian: '孙坚',
  liubiao: '刘表',
  liuyan: '刘焉',
  gongsunzan: '公孙瓒',
  mateng: '马腾',
  yuanshu: '袁术',
}

export const FACTION_GLOW: Record<string, string> = {
  han: 'rgba(255, 215, 0, 0.5)',
  zhangjiao: 'rgba(255, 255, 0, 0.5)',
  dongzhuo: 'rgba(139, 0, 0, 0.5)',
  yuanshao: 'rgba(255, 102, 0, 0.5)',
  caocao: 'rgba(0, 85, 164, 0.5)',
  liubei: 'rgba(0, 170, 85, 0.5)',
  sunjian: 'rgba(204, 0, 0, 0.5)',
  liubiao: 'rgba(139, 69, 19, 0.5)',
  liuyan: 'rgba(147, 112, 219, 0.5)',
  gongsunzan: 'rgba(255, 255, 255, 0.5)',
  mateng: 'rgba(75, 0, 130, 0.5)',
  yuanshu: 'rgba(255, 20, 147, 0.5)',
  neutral: 'rgba(136, 136, 136, 0.5)',
}

// === 地形色板（文明6 风格低饱和度 / 15 种地形） ===
export const TERRAIN_COLORS: Record<string, { fill: number; border: number }> = {
  grass:        { fill: 0x9bbf6e, border: 0x8aad5e },
  grassland:    { fill: 0xa8b87a, border: 0x96a56c },
  plain:        { fill: 0x8b9a6e, border: 0x7a8960 },
  forest:       { fill: 0x4a6b3a, border: 0x3d5a30 },
  dense_forest: { fill: 0x2d4a1e, border: 0x1f3512 },
  hill:         { fill: 0x9b8e7a, border: 0x8a7e6c },
  mountain:     { fill: 0x7a7a7a, border: 0x6a6a6a },
  peak:         { fill: 0xb0ada6, border: 0x9e9b94 },
  desert:       { fill: 0xc4b58a, border: 0xb0a27a },
  marsh:        { fill: 0x5a6b3a, border: 0x4a5a2e },
  tundra:       { fill: 0x9aacb0, border: 0x889a9e },
  snow:         { fill: 0xd8e0e8, border: 0xc8d0d8 },
  water:        { fill: 0x4a8fb8, border: 0x3e7a9e },
  deep_water:   { fill: 0x2a5a80, border: 0x1e4868 },
  river:        { fill: 0x5a9fc8, border: 0x4a8fb8 },
}

// === UI 基础色 ===
export const UI_COLORS = {
  bg: '#1a1a2e',
  bgElevated: '#22223e',
  panelBg: 'rgba(18, 18, 34, 0.88)',
  panelBorder: 'rgba(255, 255, 255, 0.08)',
  textPrimary: '#e8e0d0',
  textSecondary: '#96918a',
  textMuted: '#5a5a72',
  gold: '#d4a84b',
  goldGlow: 'rgba(212, 168, 75, 0.4)',
  red: '#c85046',
  green: '#5ab464',
  blue: '#64a0d2',
  purple: '#9370DB',
}

// === 阴影与光效 ===
export const SHADOWS = {
  card: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255,255,255,0.06)',
  glow: (color: string) => `0 0 12px ${color}, 0 0 4px ${color}`,
  drop: '0 4px 16px rgba(0, 0, 0, 0.5)',
  inset: 'inset 0 1px 0 rgba(255,255,255,0.08)',
}

// === 城市标记样式 ===
export const CITY_STYLES = {
  // 等级对应的基础尺寸
  sizeByLevel: (level: number) => 18 + level * 4,
  
  // 城池图标：SVG path 数据（简化版城堡）
  castlePath: (size: number) => {
    const s = size
    return `
      M${-s*0.7},${s*0.3} 
      L${-s*0.7},${-s*0.5} 
      L${-s*0.5},${-s*0.5} 
      L${-s*0.5},${-s*0.3} 
      L${-s*0.3},${-s*0.3} 
      L${-s*0.3},${-s*0.5} 
      L${s*0.3},${-s*0.5} 
      L${s*0.3},${-s*0.3} 
      L${s*0.5},${-s*0.3} 
      L${s*0.5},${-s*0.5} 
      L${s*0.7},${-s*0.5} 
      L${s*0.7},${s*0.3} 
      Z
      M${-s*0.25},${s*0.3} 
      A${s*0.25},${s*0.25} 0 0,1 ${s*0.25},${s*0.3}
      Z
    `
  },
  
  // 围城脉冲动画
  siegePulse: `
    @keyframes siege-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(200, 80, 70, 0.6); }
      50% { box-shadow: 0 0 0 8px rgba(200, 80, 70, 0); }
    }
  `,
}

// === 军队标记样式 ===
export const ARMY_STYLES = {
  size: 14,
  bannerPath: (size: number, direction: 'up' | 'down') => {
    const s = size
    if (direction === 'up') {
      return `M0,${-s} L${s*0.6},${s*0.3} L${s*0.2},${s*0.3} L${s*0.2},${s} L${-s*0.2},${s} L${-s*0.2},${s*0.3} L${-s*0.6},${s*0.3} Z`
    }
    return `M0,${s} L${s*0.6},${-s*0.3} L${s*0.2},${-s*0.3} L${s*0.2},${-s} L${-s*0.2},${-s} L${-s*0.2},${-s*0.3} L${-s*0.6},${-s*0.3} Z`
  },
  retreatPath: (size: number) => {
    const s = size
    return `M${-s*0.5},${-s*0.3} L${-s*0.8},0 L${-s*0.5},${s*0.3} M${-s*0.5},0 L${s*0.5},0`
  },
}

// === 工具函数 ===
export function hexToNumber(hex: string): number {
  return parseInt(hex.replace('#', ''), 16)
}

export function hexToRgba(hex: string, alpha: number): string {
  const num = parseInt(hex.replace('#', ''), 16)
  const r = (num >> 16) & 0xff
  const g = (num >> 8) & 0xff
  const b = num & 0xff
  return `rgba(${r},${g},${b},${alpha})`
}
