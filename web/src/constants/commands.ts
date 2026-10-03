/**
 * 命令类名 → 中文标签映射
 *
 * 背景：「决策」tab 此前直接把后端 Python 类名（`DevelopCommand`/`MessageCommand`…）
 * 渲染给观众看，等于把内部实现泄漏到 UI。观众关心的是"曹操这回合做了什么"，
 * 不是"实例化了哪个 dataclass"。
 *
 * 数据来源：api/game_manager.py 的 process_turn()
 *   "commands": [type(cmd).__name__ for cmd in commands]
 * 因此这里的 key 必须覆盖 game/models.py 里全部 Command 子类名。
 * 另附后端 REST/WS 使用的 snake_case type（execute_command 的 type 字段），
 * 两套命名都做兜底映射，避免将来某一端改了序列化方式就再次露出类名。
 */

/** Python 类名 → 中文标签 */
export const COMMAND_LABELS: Record<string, string> = {
  DevelopCommand: '发展',
  RecruitCommand: '征兵',
  AttackCommand: '进攻',
  RewardCommand: '赏赐',
  ExploreCommand: '探索',
  MessageCommand: '通使',
  RumorCommand: '散布谣言',
  ProposeAllianceCommand: '结盟',
  DeclareWarCommand: '宣战',
  // 基类 / 未知类型兜底
  Command: '行动',
}

/** snake_case 命令 type → 中文标签（后端 execute_command 使用的命名） */
export const COMMAND_TYPE_LABELS: Record<string, string> = {
  develop: '发展',
  recruit: '征兵',
  attack: '进攻',
  reward: '赏赐',
  explore: '探索',
  message: '通使',
  rumor: '散布谣言',
  propose_alliance: '结盟',
  declare_war: '宣战',
}

/** 命令类型 → 图标（Font Awesome class 后缀） */
export const COMMAND_ICONS: Record<string, string> = {
  DevelopCommand: 'fa-city',
  RecruitCommand: 'fa-users',
  AttackCommand: 'fa-sword',
  RewardCommand: 'fa-gift',
  ExploreCommand: 'fa-compass',
  MessageCommand: 'fa-envelope-open-text',
  RumorCommand: 'fa-comment-dots',
  ProposeAllianceCommand: 'fa-handshake',
  DeclareWarCommand: 'fa-bolt',
}

/** snake_case 版本图标 */
const COMMAND_TYPE_ICONS: Record<string, string> = {
  develop: 'fa-city',
  recruit: 'fa-users',
  attack: 'fa-sword',
  reward: 'fa-gift',
  explore: 'fa-compass',
  message: 'fa-envelope-open-text',
  rumor: 'fa-comment-dots',
  propose_alliance: 'fa-handshake',
  declare_war: 'fa-bolt',
}

/**
 * 把后端给的命令标识翻译成中文标签。
 * 认得类名就查类名表，认得 snake_case 就查 type 表，
 * 都不认得则原样返回（不做二次猜测，避免把未知命令错标成别的动作）。
 */
export function commandLabel(raw: string): string {
  if (!raw) return '行动'
  if (COMMAND_LABELS[raw]) return COMMAND_LABELS[raw]
  if (COMMAND_TYPE_LABELS[raw]) return COMMAND_TYPE_LABELS[raw]
  return raw
}

/** 取命令图标；未知命令回落到通用图标 */
export function commandIcon(raw: string): string {
  if (COMMAND_ICONS[raw]) return COMMAND_ICONS[raw]
  if (COMMAND_TYPE_ICONS[raw]) return COMMAND_TYPE_ICONS[raw]
  return 'fa-circle-dot'
}

/** 导出全部已知命令类名，供测试断言"映射表覆盖完整" */
export const KNOWN_COMMAND_CLASS_NAMES = Object.keys(COMMAND_LABELS)
