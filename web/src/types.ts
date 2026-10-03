export interface HexCoord {
  q: number
  r: number
}

export interface Tile {
  coord: HexCoord
  terrain: string
  faction: string | null
  owner_city_id: string | null
  gold_yield: number
  food_yield: number
  pop_yield: number
}

export interface City {
  id: string
  name: string
  faction: string
  level: number
  wall_hp: number
  wall_max_hp: number
  garrison: number
  gold: number
  food: number
  population: number
  morale: number
  position: HexCoord
  is_besieged: boolean
  besieging_armies: string[]
}

export interface Army {
  id: string
  faction: string
  general_id: string
  soldiers: number
  morale: number
  status: string
  from_city: string
  to_city: string
  current_hex: HexCoord | null
}

export interface General {
  id: string
  name: string
  faction: string
  command: number
  politics: number
  bravery: number
  intelligence: number
  loyalty: number
  location: string
  is_captured: boolean
  /** v4.0：将道五行键（fire/earth/metal/water/wood），由后端按五维推导 */
  element?: string
  /** v4.0：将道中文名（火/土/金/水/木） */
  element_name?: string
  /** v4.0：人物称号（来自人设档案，如「治世之能臣，乱世之奸雄」） */
  title?: string
}

export interface FactionStat {
  name: string
  cities: number
  garrison: number
  gold: number
  food: number
  population: number
  /** v4.0.1：该势力由哪个大模型指挥（多模型对战；CLI 模式下为空串） */
  model?: string
  /** v4.0.1：是否仍有城池（用于「已出局」展示） */
  is_alive?: boolean
}

export interface GameEvent {
  turn: number
  type: string
  text: string
}

/**
 * 单场战斗报告（v4.1 · 阶段C2 战斗可视化）
 *
 * 契约来源：`docs/design/v4.1-gameplay-gaps.md` §4.3 的 `BattleReport` DTO。
 * 引擎已算出这些字段，后端只需打包后经 `recent_battles` 广播出来（见该文档 §4.1）。
 *
 * 🔴 `attacker_from_city` / `defender_city` 是「从哪来、打向哪」的关键——
 *    没有它们只能显示结果，画不出进攻方向。
 * 所有 `*_city` 是**城市 id**（前端再用 `state.cities[id].position` 转坐标）。
 */
export interface BattleReport {
  battle_id: string
  turn: number
  attacker_faction: string
  defender_faction: string
  attacker_from_city: string | null
  defender_city: string | null
  attacker_soldiers: number
  defender_soldiers: number
  attacker_casualties: number
  defender_casualties: number
  /** attacker_win | defender_win | draw | retreat */
  result: string
  wall_hp_before?: number
  wall_hp_after?: number
  attacker_general_name?: string
}

export interface HexTile {
  q: number
  r: number
  terrain: string
  faction: string | null
  owner_city_id: string | null
  province_id: string | null
}

export interface FactionRelation {
  faction_a: string
  faction_b: string
  status: 'war' | 'neutral' | 'alliance' | 'truce'
  trust: number
  truce_end_turn?: number
  alliance_end_turn?: number
}

export interface DiplomacyMessage {
  id: string
  from_faction: string
  to_faction: string
  content: string
  turn: number
  is_read: boolean
}

export interface TurnLog {
  turn: number
  battles_fought: number
  armies_moved: number
  cities_captured: string[]
}

export interface ReasoningEntry {
  turn: number
  faction: string
  reasoning: string
  commands: string[]
}

export interface GameState {
  turn: number
  max_turns: number
  year: number
  season: string
  game_over: boolean
  winner: string | null
  cities: Record<string, City>
  armies: Record<string, Army>
  generals: Record<string, General>
  faction_stats: Record<string, FactionStat>
  events: GameEvent[]
  human_faction: string | null
  hex_map?: {
    width: number
    height: number
    tiles: HexTile[]
  }
  faction_relations?: FactionRelation[]
  messages?: DiplomacyMessage[]
  turn_logs?: TurnLog[]
  /** v4.1：近 N 场战斗（用于地图上的战斗回放）。后端未落地时为空/缺省。 */
  recent_battles?: BattleReport[]
  provinces?: Record<string, ProvinceInfo>
  reasoning?: ReasoningEntry[]
  // ---- LLM 模式状态（api/game_manager.py get_state() 只读字段）----
  /** 前端请求了 LLM 模式 */
  llm_requested?: boolean
  /** 后端**实际**是否真的建了 LLMPlayer（false = 已静默回退规则 AI） */
  llm_active?: boolean
  /** 回退原因（人类可读），llm_active=false 且 llm_requested=true 时有值 */
  llm_error?: string
  /** 实际生效的模型 id */
  llm_model?: string
  /** 本局实际参战势力 */
  llm_factions?: string[]
}

export interface ProvinceInfo {
  name: string
  capital_city_id: string | null
  color: string
  cities: string[]
}

export interface WebSocketMessage {
  type: string
  data?: unknown
  text?: string
  message?: string
}
