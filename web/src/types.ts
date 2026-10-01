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
}

export interface FactionStat {
  name: string
  cities: number
  garrison: number
  gold: number
  food: number
  population: number
}

export interface GameEvent {
  turn: number
  type: string
  text: string
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
  provinces?: Record<string, ProvinceInfo>
  reasoning?: ReasoningEntry[]
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
