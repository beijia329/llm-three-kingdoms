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
  caocao: '#8A4B32',          // 曹操 — 中褐（D3：原 #5E3828 在纸底上发闷 → 提亮）
  liubei: '#2D7A3A',          // 刘备 — 森林绿（仁德）
  sunjian: '#8A1A2B',         // 孙坚 — 深绛（勇猛）
  yuanshao: '#DB861D',        // 袁绍 — 铜橙（盟主）
  gongsunzan: '#6E8073',      // 公孙瓒 — 北疆灰绿（原米褐几乎隐形于图上）
  mateng: '#6B3FA0',          // 马腾 — 紫（西凉）
  // 董卓 — 近黑（D3：原 #1D1B24 近黑，叠纸底像脏斑 → 提亮为「暗紫褐」，保留篡逆意象）
  dongzhuo: '#5A4A63',
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
  return L > 0.45 ? '#16222B' : '#ffffff'
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
//
// [D2 2026-10-04] 圆角上限收到 6（去卡通）：sm 4→2、md 6→4、lg 10→6；
// pill 弃用胶囊（999→0）。全站 borderRadius 只允许 0/2/4/6（999 仅头像等特殊）。
export const SPACE = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const
export const RADIUS = { sm: 2, md: 4, lg: 6, pill: 0 } as const
export const FONT_SIZE = { xs: 11, sm: 12, md: 13, lg: 15, xl: 20 } as const

// === 战棋标尺表（D3 · docs/art/2026-10-04-战棋视觉元素规范.md §4.7）===
// 🔴 「比例没做好」的根因是过去无刻度：全站 fontSize 15 种、borderRadius 11 种。
//    这里把地图/战斗层用到的四类刻度钉死，组件照抄。
/** A. 字号刻度（屏幕 px） */
export const FS = { micro: 9, caption: 10, body: 12, label: 14, title: 18, display: 22 } as const
/** B. 线宽刻度（屏幕 px，恒定；绘制时 × 1/zoom 换世界 px） */
export const LW = { hair: 1.0, thin: 1.5, mid: 2.0, bold: 3.0 } as const
/** C. 标记尺寸刻度（屏幕 px，恒定） */
export const MK = { xs: 12, sm: 16, md: 20, lg: 22, xl: 26 } as const
/** D. 不透明度刻度 */
export const OP = { wash: 0.30, soft: 0.48, mid: 0.72, strong: 0.92, glow: 0.40 } as const

/** 城池等级 → 标记尺寸档（屏幕 px，恒定）：14/16/19/22/26 */
export const CITY_MARKER_SIZE: Record<number, number> = { 1: 14, 2: 16, 3: 19, 4: 22, 5: 26 }
/** 军队兵力 → 标记尺寸档（屏幕 px）：小队 12 / 大队 16 / 军团 20 */
export function armyMarkerSize(soldiers: number): number {
  if (soldiers < 3000) return MK.xs   // 12
  if (soldiers < 10000) return MK.sm  // 16
  return MK.md                        // 20
}
/** 🔴 军队标记尺寸 ≤ 同格城池标记尺寸 × 0.80（学兵棋「单位符号 ≤ 地形符号」） */
export const ARMY_VS_CITY_RATIO = 0.80


/**
 * 右侧常驻面板宽度（px）—— **宽屏基准值**。
 *
 * [M5 2026-10-04] 此前顶栏/事件流/「下一回合」按钮/自动推进条各自硬编码 right
 * 偏移（324 / 330 / 318 / 470），四个值互不对齐（最大差 12px），且 Panel 宽度一改
 * 就四处全错位。现在统一由本常量推导：right = PANEL_W + GAP_PANEL。
 *
 * [M4 2026-10-04] 300 → 420：外交关系矩阵（12×12）在 300px 栏里格太小、需滚动。
 * 🔴 加宽会挤压地图可用区，故**不直接全局写死 420**，而是由
 * `responsivePanelWidth(viewportW)` 按视口宽度取档（见下），组件用 `usePanelWidth()`
 * 拿运行值——窄屏（1366/1280）自动收窄，保证地图不被压到不可用。
 */
export const PANEL_W = 420
/** 面板宽度下限（窄屏不再低于此值，否则内容/矩阵不可读） */
export const PANEL_W_MIN = 300

/**
 * 按视口宽度取面板宽度档（M4 响应式）：
 *   ≥1440 → 420（宽屏基准）
 *   1200–1439 → 360（1366 等常见窄屏：地图仍 ≥1000px）
 *   <1200 → 300（小屏保底）
 * 返回值为「不含间距」的面板宽度；浮层右偏移 = 返回值 + GAP_PANEL。
 */
export function responsivePanelWidth(viewportW: number): number {
  if (viewportW >= 1440) return 420
  if (viewportW >= 1200) return 360
  return PANEL_W_MIN
}
/** 浮层与面板之间的统一间距 */
export const GAP_PANEL = 24
/** 「下一回合」按钮宽度（自动推进条定位依赖它） */
export const NEXT_BTN_W = 140

// 字体栈：标题走衬线（系统自带，零体积），正文走黑体。
// 这是阶段A 的「零成本汉风层级」；阶段B 再换成思源宋体/霞鹜文楷。
export const FONT_STACK = {
  sans: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  serif: '"Songti SC", "STSong", "SimSun", "Noto Serif SC", serif',
} as const

// 属性配色语义（阶段A 修复：原来「统帅」和「勇武」都用 #c85046，同色异义）
// [D2 2026-10-04] 换中国传统色（方向甲·绢本墨色），去 Material 三件套。
export const STAT_COLORS = {
  command: '#9D2933',   // 统帅 — 朱砂
  politics: '#4A6FA5',  // 政治 — 天青
  bravery: '#9C5B2D',   // 勇武 — 赭石（与统帅区分开）
  intelligence: '#C8A85A', // 智力 — 古金
  loyalty: '#5B7A4E',   // 忠诚 — 竹青
} as const

// === UI 基础色（方向甲 · 绢本墨色）===
// [D2 2026-10-04] 全表换血：把「蓝紫黑 + 电竞金 + 毛玻璃 + 大圆角」换成
// 「墨青绢本 + 朱砂赭金」。对比度按新底 #16222B 重算（见 docs/art/2026-10-04-UI古韵方向.md §3.1）。
// 🔴 旧「电竞金」硬编码已全站清零，一律走本表 / --gold。
export const UI_COLORS = {
  bg: '#16222B',                       // 墨青
  bgElevated: '#1F2E38',               // 黛青（提亮）
  panelBg: 'rgba(20, 32, 40, 0.90)',   // 绢底（叠 textures/绢纹）
  panelBorder: 'rgba(200, 168, 90, 0.18)', // 淡金褐描边（替代现代细白框）
  textPrimary: '#EDE6D6',              // 缟（米白）
  textSecondary: '#B9AF9C',
  textMuted: '#9A9184',
  gold: '#C8A85A',                     // 秋香 / 赭金（替代旧电竞金，降饱和偏土黄）
  goldGlow: 'rgba(200, 168, 90, 0.30)', // 辉光强度减半（去霓虹）
  red: '#9D2933',                      // 朱砂
  green: '#5B7A4E',                    // 竹青
  blue: '#4A6FA5',                     // 天青
  purple: '#6B5A82',                   // 藕紫
  // 新增（§3.1）
  ink: '#2C2C2C',                      // 墨色描边 / 浅底文字 / 地图标注
  paper: '#EFE6D2',                    // 绢本（浅色块 / 印章底 / 进度槽）
  accentStamp: '#9D2933',              // 印章 / 最强动作 / 交战标记
  ochre: '#9C5B2D',                    // 木牌 / 次级标签
  divider: '#5A4A38',                  // 双线分隔主线
}

// === 阴影与光效（去霓虹辉光 / 去毛玻璃）===
export const SHADOWS = {
  card: '0 2px 8px rgba(0, 0, 0, 0.35)',   // 低扩散投影（替代大扩散 + 霓虹）
  glow: (color: string) => `0 0 8px ${color}`, // 选中态专用，强度减半
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
