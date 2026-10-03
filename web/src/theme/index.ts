/**
 * 游戏视觉主题系统（Design Token）
 * 
 * 参考：三国志14（古典水墨风）、文明6（卡通渲染+清晰边界）
 * 目标：建立统一的视觉语言，支撑未来素材替换
 */

// === 势力色板 ===
// [阶段A 2026-10-03] 「最小区分度」微调（team-lead 批准，非考据重制）。
// 实测（CIELAB ΔE）原配色问题：
//   · dongzhuo×liuyan ΔE=17.2、caocao×sunjian 20.4、caocao×liubiao 24.1 …… 多个深色互相糊
//   · gongsunzan 对羊皮纸底 ΔE 仅 9.2 —— 几乎隐形在图上
//   · 红绿色盲模拟下 caocao×sunjian ΔE=1.0（完全无法区分）
// 调整后：最小两两 ΔE 17.2 → 28.4；对底色最小 ΔE 9.2 → 35；色盲模拟最小 1.0 → 6.8。
// 注：12 方仅靠颜色无法对色盲完全友好（需图案/标签辅助，留待阶段B）。
export const FACTION_COLORS: Record<string, string> = {
  zhangjiao: '#EFC200',       // 黄巾 — 明黄（与全天下对立）
  // 汉室联盟 — 暖色系
  han: '#CE2A18',             // 汉室 — 朱红（汉·火德尚赤）
  caocao: '#5E3828',          // 曹操 — 深褐（汉室嫡系）
  liubei: '#2D7A3A',          // 刘备 — 森林绿（仁德）
  sunjian: '#8A1A2B',         // 孙坚 — 深绛（勇猛）
  yuanshao: '#DB861D',        // 袁绍 — 铜橙（盟主）
  gongsunzan: '#6E8073',      // 公孙瓒 — 北疆灰绿（原米褐几乎隐形于图上）
  mateng: '#6B3FA0',          // 马腾 — 紫（西凉）
  // 董卓 — 近黑（未来篡逆，与联盟对立）
  dongzhuo: '#1D1B24',
  // 中立观望
  liubiao: '#9C7A34',         // 刘表 — 金褐
  liuyan: '#A99BC4',          // 刘焉 — 浅灰紫
  // 袁术 — 玫红（袁绍之弟，关联但对立）
  yuanshu: '#C81E63',
  neutral: '#666666',
}

export const FACTIONS: Record<string, string> = {
  han: '汉室',
  zhangjiao: '黄巾',
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

// 势力辉光：从 FACTION_COLORS 派生（原来是一份手写的、与色值脱节的副本——
// 改色时极易漏改，属于「两个事实源」隐患，这里合并为一个）。
export const FACTION_GLOW: Record<string, string> = Object.fromEntries(
  Object.entries(FACTION_COLORS).map(([k, v]) => [k, hexToRgba(v, 0.5)]),
)

// === 势力「单字简称」（可访问性：色盲/灰度/小屏下的非颜色线索）===
//
// 为什么需要：红绿色盲模拟下势力色最小 ΔE 仅 6.8（可靠区分需 >10）——
// **颜色本身承载不了 12 个势力的区分**，必须再加一层与颜色无关的线索。
// 详见 docs/art/2026-10-colorblind-non-color-cues.md。
//
// 取字规则：**优先取姓氏首字；同姓冲突的那一组，整组改用「名」首字**。
//   · {刘备, 刘表, 刘焉} 同姓「刘」→ 备 / 表 / 焉
//   · {袁绍, 袁术}      同姓「袁」→ 绍 / 术
//   （将来加新势力时按同一规则判断：先看姓氏，撞了再退到名。）
//   例外：**汉室、黄巾**是 184 年 12 方里唯二的「非个人政治实体」（政权/教门），
//   它们本来就没有姓氏，直接用阵营字。
//
// 🔴 守卫一：下面这个对象**以「字」为键**。若两个势力取到同一个字，
//    就是「对象字面量重复键」，tsc 会直接编译失败（strict 下报 TS1117）。
//    这是刻意的——本项目的构建是 `tsc && vite build`，撞字会让构建挂掉，
//    不会出现「悄悄上线两个『刘』」。
const GLYPH_TO_FACTION = {
  汉: 'han',        // 汉室（政权名）
  黄: 'zhangjiao',  // 黄巾（教团/军队名。原显示名「张角」与麾下将领张角撞名，已改阵营名）
  董: 'dongzhuo',   // 董卓
  曹: 'caocao',     // 曹操
  孙: 'sunjian',    // 孙坚
  马: 'mateng',     // 马腾
  公: 'gongsunzan', // 公孙瓒（复姓取首字）
  备: 'liubei',     // 刘备 ← 同姓「刘」组，用名首字
  表: 'liubiao',    // 刘表 ← 同姓「刘」组
  焉: 'liuyan',     // 刘焉 ← 同姓「刘」组
  绍: 'yuanshao',   // 袁绍 ← 同姓「袁」组
  术: 'yuanshu',    // 袁术 ← 同姓「袁」组
} as const

/** 会上图的势力 id（不含 neutral）。新增势力时这里也要加，否则下面的覆盖断言编译失败。 */
export const FACTION_IDS = [
  'han', 'zhangjiao', 'dongzhuo', 'caocao', 'liubei', 'sunjian',
  'yuanshao', 'gongsunzan', 'mateng', 'liubiao', 'liuyan', 'yuanshu',
] as const
type FactionId = (typeof FACTION_IDS)[number]

// 守卫二：单字的取值必须是合法势力 id（把 id 写错会在此编译失败）
export const _GLYPH_VALUE_TYPES: Record<string, FactionId> = GLYPH_TO_FACTION

// 守卫三：覆盖性——每个势力都必须有单字。
// 漏配时 _MissingGlyph 不为 never，断言类型塌成 never，`= true` 即编译失败。
type _MissingGlyph = Exclude<FactionId, (typeof GLYPH_TO_FACTION)[keyof typeof GLYPH_TO_FACTION]>
export const _GLYPH_COVERAGE: _MissingGlyph extends never ? true : never = true

/** 势力 → 单字（由 GLYPH_TO_FACTION 反转，保证与上面同一事实源） */
export const FACTION_GLYPH: Record<string, string> = Object.fromEntries(
  Object.entries(GLYPH_TO_FACTION).map(([glyph, fid]) => [fid, glyph]),
)

/** 依背景亮度选前景色——保证单字在任意势力色（含亮黄/浅紫）上都读得出来 */
export function contrastText(hex: string): string {
  const n = parseInt(hex.replace('#', ''), 16)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
  const r = lin(((n >> 16) & 0xff) / 255)
  const g = lin(((n >> 8) & 0xff) / 255)
  const b = lin((n & 0xff) / 255)
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return L > 0.45 ? '#1a1a2e' : '#ffffff'
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

// === 古地图「羊皮纸」地形色（阶段A 新增）===
// 修复：原来 parchmentTint() 对所有地形返回同一个色 0xd9c9a3，导致
// 山地/森林/沙漠/雪地在图上完全同色。这里给每种地形一个同色系、
// 但有区分度的羊皮纸色调——既保留「古地图」质感，又能看出地形差异。
// 全部取同一明度带的大地/羊皮纸色，避免出现「卡通花斑」。
export const TERRAIN_PARCHMENT: Record<string, number> = {
  plain:        0xd9c9a3, // 基准羊皮纸
  grassland:    0xd4c79c,
  grass:        0xcabd8f, // 略偏草绿
  forest:       0xbdb083, // 更深
  dense_forest: 0xa89b6e, // 最深（林）
  marsh:        0xc6bf95,
  hill:         0xd6c6a0,
  mountain:     0xc3b28e, // 山体偏灰褐
  peak:         0xe2d8be, // 峰顶提亮（积雪感）
  desert:       0xe8d79f, // 沙漠偏黄
  tundra:       0xd8d2c0,
  snow:         0xefece2, // 雪接近白
  // 非水默认
  _default:     0xd9c9a3,
}

// === 阶段A：间距 / 圆角 / 字号 刻度（Design Token）===
// 目的：原来各组件硬编码 4/6/8/10/12/14 混用、圆角 4/6/8/10 混用，
// 视觉上「拼凑感」明显。统一到一套刻度后，改一处即可全站生效。
export const SPACE = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const
export const RADIUS = { sm: 4, md: 6, lg: 10, pill: 999 } as const
export const FONT_SIZE = { xs: 11, sm: 12, md: 13, lg: 15, xl: 20 } as const

// 字体栈：标题走衬线（系统自带，零体积），正文走黑体。
// 这是阶段A 的「零成本汉风层级」；阶段B 再换成思源宋体/霞鹜文楷。
export const FONT_STACK = {
  sans: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  serif: '"Songti SC", "STSong", "SimSun", "Noto Serif SC", serif',
} as const

// 属性配色语义（阶段A 修复：原来「统帅」和「勇武」都用 #c85046，同色异义）
export const STAT_COLORS = {
  command: '#e0705a',   // 统帅 — 朱
  politics: '#64a0d2',  // 政治 — 蓝
  bravery: '#d99a3c',   // 勇武 — 橙（与统帅区分开）
  intelligence: '#d4a84b', // 智力 — 金
  loyalty: '#5ab464',   // 忠诚 — 绿
} as const

// === UI 基础色 ===
// 阶段A 对比度修复：原 textMuted #5a5a72 对深底仅约 2.8:1（远低于 WCAG AA 4.5:1），
// 且被用在 10px 提示文字上几乎不可见。#8a86a0 实测约 5.3:1，达标。
// textSecondary 也由 #96918a 提亮到 #a8a29a（约 7.3:1），小字号更稳。
export const UI_COLORS = {
  bg: '#1a1a2e',
  bgElevated: '#22223e',
  panelBg: 'rgba(18, 18, 34, 0.88)',
  panelBorder: 'rgba(255, 255, 255, 0.08)',
  textPrimary: '#e8e0d0',
  textSecondary: '#a8a29a',
  textMuted: '#8a86a0',
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
