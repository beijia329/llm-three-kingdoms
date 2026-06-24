/**
 * 游戏视觉主题系统（Design Token）
 * 
 * 参考：三国志14（古典水墨风）、文明6（卡通渲染+清晰边界）
 * 目标：建立统一的视觉语言，支撑未来素材替换
 */

// === 势力色板（按 184 年初关系：联盟暖色系，对立冷/亮色系，无蓝） ===
export const FACTION_COLORS: Record<string, string> = {
  zhangjiao: '#FFD700',       // 黄巾 — 亮金（与全天下对立）
  // 汉室联盟 — 暖色系（金/红/棕/绿）
  han: '#DAA520',             // 汉室 — 深金
  caocao: '#6b3020',          // 曹操 — 深红褐（汉室嫡系）
  liubei: '#2d7a3a',          // 刘备 — 森林绿（仁德）
  sunjian: '#8B2020',         // 孙坚 — 暗红（勇猛）
  yuanshao: '#CC7733',        // 袁绍 — 铜橙（盟主）
  gongsunzan: '#c4b090',      // 公孙瓒 — 米褐（北疆）
  mateng: '#5a3070',          // 马腾 — 深紫（西凉，暖调）
  // 董卓 — 冷暗（未来篡逆，与联盟对立）
  dongzhuo: '#3a3040',
  // 中立观望 — 中间色
  liubiao: '#7a6040',         // 刘表 — 棕
  liuyan: '#5a5070',          // 刘焉 — 灰紫
  // 袁术 — 玫红（袁绍之弟，关联但对立）
  yuanshu: '#b04060',
  neutral: '#666666',
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
  zhangjiao: 'rgba(255, 215, 0, 0.5)',
  han: 'rgba(218, 165, 32, 0.5)',
  caocao: 'rgba(107, 48, 32, 0.5)',
  liubei: 'rgba(45, 122, 58, 0.5)',
  sunjian: 'rgba(139, 32, 32, 0.5)',
  yuanshao: 'rgba(204, 119, 51, 0.5)',
  gongsunzan: 'rgba(196, 176, 144, 0.5)',
  mateng: 'rgba(90, 48, 112, 0.5)',
  dongzhuo: 'rgba(58, 48, 64, 0.5)',
  liubiao: 'rgba(122, 96, 64, 0.5)',
  liuyan: 'rgba(90, 80, 112, 0.5)',
  yuanshu: 'rgba(176, 64, 96, 0.5)',
  neutral: 'rgba(102, 102, 102, 0.5)',
}

// === 地形色板（陆=大地色系，海=亮蓝，雾=深灰） ===
export const TERRAIN_COLORS: Record<string, { fill: number; border: number }> = {
  grass:        { fill: 0x8db85a, border: 0x7aa34e },
  grassland:    { fill: 0xa0b86a, border: 0x8ea55a },
  plain:        { fill: 0x9ea870, border: 0x8e9862 },
  forest:       { fill: 0x4a7a3e, border: 0x3d6832 },
  dense_forest: { fill: 0x2d5a1e, border: 0x1f4512 },
  hill:         { fill: 0xa09070, border: 0x908060 },
  mountain:     { fill: 0x7a7060, border: 0x6a6050 },
  peak:         { fill: 0xb0a898, border: 0x9e9686 },
  desert:       { fill: 0xc8b878, border: 0xb4a468 },
  marsh:        { fill: 0x5a7a3a, border: 0x4a6a2e },
  tundra:       { fill: 0xa0a890, border: 0x909680 },
  snow:         { fill: 0xdce0e8, border: 0xccd0d8 },
  // 海洋：统一浅蓝色（不区分深浅）
  water:        { fill: 0x4499cc, border: 0x4499cc },
  deep_water:   { fill: 0x4499cc, border: 0x4499cc },
  river:        { fill: 0x55aadd, border: 0x4499cc },
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
