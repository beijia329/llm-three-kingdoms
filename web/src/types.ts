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
}

export interface WebSocketMessage {
  type: string
  data?: unknown
  text?: string
  message?: string
}
