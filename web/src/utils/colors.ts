export const UI_COLORS = {
  bg: 0x1a1a2e,
  panelBg: 0x2a2a3e,
  panelHeader: 0x3c3c52,
  text: 0xe8e0d0,
  gold: 0xd4a84b,
  dim: 0x96918a,
  red: 0xc85046,
  green: 0x5ab464,
  blue: 0x64a0d2,
}

export const TERRAIN_COLORS: Record<string, { fill: number; border: number }> = {
  plain: { fill: 0x8b9a6e, border: 0x7a8960 },
  forest: { fill: 0x4a6b3a, border: 0x3d5a30 },
  hill: { fill: 0x9b8e7a, border: 0x8a7e6c },
  mountain: { fill: 0x7a7a7a, border: 0x6a6a6a },
  river: { fill: 0x4a8fb8, border: 0x3e7a9e },
  desert: { fill: 0xc4b58a, border: 0xb0a27a },
}

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

export function hexToNumber(hex: string): number {
  return parseInt(hex.replace('#', ''), 16)
}
