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
  /**
   * 以下字段后端 `get_state()` 一直返回（见 `api/game_manager.py`），
   * 此前前端类型未声明 → 城池详情卡拿不到「驻守将领 / 相邻城池 / 州郡」。
   * 城池详情卡的「出征」目标下拉依赖 `neighbors`。均为只读，可选以免旧快照报错。
   */
  province_id?: string
  /** 驻守本城的将领 id 列表 */
  generals?: string[]
  /** 相邻城市 id 列表（六角格图上的连通城） */
  neighbors?: string[]
  /** 经济发展累计加成（%） */
  economic_bonus?: number
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
 * 🔴 `attacker_from_cities` / `defender_city` 是「从哪来、打向哪」的关键——
 *    没有它们只能显示结果，画不出进攻方向。
 *
 * 🔴 `attacker_from_cities` 是**复数**（设计文档 §4.3.1 更正）：
 *    一场战斗可以有**多支来自不同出发城**的攻方部队被合并（`battle_scheduler._group_by_target`），
 *    实测 **15% 的战斗**是多出发城。后端打包时用 `sorted(set(各军队 from_city))` 去重排序
 *    （排序是为了不踩集合迭代序的确定性坑，见 ADR-0002）。前端对**每个出发城画一条箭头**。
 *
 * 所有 `*_city` 是**城市 id**（前端再用 `state.cities[id].position` 转坐标）。
 */
export interface BattleReport {
  battle_id: string
  turn: number
  attacker_faction: string
  defender_faction: string
  /** 出发城 id 列表（复数！可能多于一，见上方说明） */
  attacker_from_cities: string[]
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
  /** 守方主将名。后端 `BattleEndedEvent` 尚未携带该字段（engineering 侧小改进行中），
   *  故为可选：有值就显示，无值静默不显示——落地后前端无需再改。 */
  defender_general_name?: string
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
  /**
   * hex_map 版本指纹（后端 `_hex_map_version()` 计算）。
   *
   * 🔴 性能契约（2026-10-03）：后端只在「占领变城」时改变该版本，且当客户端
   * 上报的已知版本与当前一致时，**不再回传** hex_map（响应从 ~2.34 MB → ~30 KB）。
   * 前端据此判断是否重建 Pixi 底图：版本未变则只更新标记层，不重画 24000 格。
   */
  hex_map_version?: string
  /**
   * hex_map 增量（占领回合只回传变化的格子）。
   *
   * 🔴 `tiles` 只含 `q/r/faction/owner_city_id`（可变字段），`terrain/province_id`
   * 建图后不变，前端在缓存上打补丁即可。`base_version` = 前端应持有的缓存版本。
   */
  hex_map_delta?: {
    version: string
    base_version: string
    tiles: Array<{
      q: number
      r: number
      faction: string | null
      owner_city_id: string | null
    }>
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
