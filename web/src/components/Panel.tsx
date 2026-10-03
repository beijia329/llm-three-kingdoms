import { useState } from 'react'
import type { GameEvent, GameState, General, ReasoningEntry } from '../types'
import { FACTION_COLORS, FACTIONS } from '../theme'
import { commandIcon, commandLabel } from '../constants/commands'
import { DiplomacyPanel } from './DiplomacyPanel'

type TabKey = 'factions' | 'city' | 'generals' | 'diplomacy' | 'data' | 'events' | 'log' | 'reasoning'

interface PanelProps {
  state: GameState | null
  tab: TabKey
  setTab: (tab: TabKey) => void
  selectedCityId: string | null
  selectedFaction: string | null
  setSelectedFaction: (fid: string) => void
  onSelectCity: (cityId: string) => void
}

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'factions', label: '势力', icon: 'fa-chess-king' },
  { key: 'city', label: '城市', icon: 'fa-city' },
  { key: 'generals', label: '武将', icon: 'fa-user-shield' },
  { key: 'diplomacy', label: '外交', icon: 'fa-handshake' },
  { key: 'data', label: '数据', icon: 'fa-chart-bar' },
  { key: 'events', label: '事件', icon: 'fa-calendar-day' },
  { key: 'log', label: '战报', icon: 'fa-scroll' },
  { key: 'reasoning', label: '决策', icon: 'fa-brain' },
]

export function Panel({ state, tab, setTab, selectedCityId, selectedFaction, setSelectedFaction, onSelectCity }: PanelProps) {
  if (!state) return (
    <div style={styles.container}>
      <div style={styles.glassCard}>
        <span style={styles.dim}><i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '6px' }}></i>加载中...</span>
      </div>
    </div>
  )

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.key}
            style={{
              ...styles.tab,
              backgroundColor: tab === t.key ? 'rgba(212, 168, 75, 0.15)' : 'transparent',
              color: tab === t.key ? '#d4a84b' : '#96918a',
              borderColor: tab === t.key ? 'rgba(212, 168, 75, 0.4)' : 'transparent',
            }}
            onClick={() => setTab(t.key)}
          >
            <i className={`fa-solid ${t.icon}`} style={{ fontSize: '12px', marginBottom: '2px' }}></i>
            <span style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>{t.label}</span>
          </button>
        ))}
      </div>
      <div style={styles.content}>
        {tab === 'factions' && <FactionList state={state} selectedFaction={selectedFaction} setSelectedFaction={setSelectedFaction} />}
        {tab === 'city' && <CityDetail state={state} cityId={selectedCityId} onSelectCity={onSelectCity} />}
        {tab === 'generals' && <GeneralList state={state} />}
        {tab === 'diplomacy' && <DiplomacyPanel state={state} />}
        {tab === 'data' && <DataPanel state={state} />}
        {tab === 'events' && <EventsPanel state={state} />}
        {tab === 'log' && <EventLog events={state.events} />}
        {tab === 'reasoning' && <ReasoningPanel state={state} />}
      </div>
    </div>
  )
}

function FactionList({
  state,
  selectedFaction,
  setSelectedFaction,
}: {
  state: GameState
  selectedFaction: string | null
  setSelectedFaction: (fid: string) => void
}) {
  const rows = Object.entries(state.faction_stats)
    .map(([fid, s]) => ({ fid, ...s }))
    .sort((a, b) => b.cities - a.cities || a.name.localeCompare(b.name, 'zh-CN'))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {rows.map((row) => {
        const color = FACTION_COLORS[row.fid] || '#888888'
        const isSelected = selectedFaction === row.fid
        return (
          <div
            key={row.fid}
            style={{
              ...styles.card,
              borderLeft: `3px solid ${color}`,
              backgroundColor: isSelected ? 'rgba(212, 168, 75, 0.1)' : 'rgba(255, 255, 255, 0.03)',
              cursor: 'pointer',
            }}
            onClick={() => setSelectedFaction(row.fid)}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isSelected ? '#e8e0d0' : '#b8b3aa', fontWeight: 600, fontSize: '14px' }}>
                <i className="fa-solid fa-flag" style={{ color, fontSize: '12px' }}></i>
                {row.name}
                {/* v4.0.1：标出这一方由哪个大模型指挥 —— 多模型对战的关键信息，
                    让观众一眼看出"曹操是 v4-pro 在打，孙坚是 flash 在打"。 */}
                {row.model && (
                  <span
                    style={styles.modelTag}
                    title={`由 ${row.model} 指挥`}
                  >
                    <i className="fa-solid fa-robot" style={{ marginRight: '3px', fontSize: '8px' }}></i>
                    {row.model.replace(/^deepseek-/, '')}
                  </span>
                )}
              </span>
              {row.cities >= 5 && <i className="fa-solid fa-crown" style={{ color: '#d4a84b', fontSize: '11px' }} title="称帝"></i>}
              {row.cities >= 3 && row.cities < 5 && <i className="fa-solid fa-gem" style={{ color: '#64a0d2', fontSize: '11px' }} title="称王"></i>}
            </div>
            <div style={styles.statGrid}>
              <span style={styles.statItem}>
                <i className="fa-solid fa-chess-rook" style={{ color: '#d4a84b', fontSize: '10px', marginRight: '3px' }}></i>
                {row.cities}城
              </span>
              <span style={styles.statItem}>
                <i className="fa-solid fa-users" style={{ color: '#5ab464', fontSize: '10px', marginRight: '3px' }}></i>
                {row.garrison}
              </span>
              <span style={styles.statItem}>
                <i className="fa-solid fa-coins" style={{ color: '#d4a84b', fontSize: '10px', marginRight: '3px' }}></i>
                {row.gold}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CityDetail({ state, cityId, onSelectCity }: { state: GameState; cityId: string | null; onSelectCity: (id: string) => void }) {
  if (!cityId) {
    // [修复 2026-10-01] 原来只有一句占位提示 + 大片空白 → 改为可点击的城市列表
    const cities = Object.values(state.cities)
    const byFaction: Record<string, typeof cities> = {}
    cities.forEach((c) => { (byFaction[c.faction] = byFaction[c.faction] || []).push(c) })
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ fontSize: '13px', color: '#d4a84b' }}>城市列表（{cities.length}）</div>
        {Object.keys(FACTIONS).filter((f) => byFaction[f]?.length).map((f) => (
          <div key={f} style={styles.card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: FACTION_COLORS[f] || '#888' }} />
              <span style={{ fontSize: '12px', color: '#96918a' }}>{FACTIONS[f] || f} · {byFaction[f].length} 城</span>
            </div>
            {byFaction[f].map((c) => (
              <div
                key={c.id}
                onClick={() => onSelectCity(c.id)}
                style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', marginBottom: '4px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', cursor: 'pointer' }}
              >
                <span style={{ fontSize: '13px', color: '#e8e0d0' }}>{c.name}</span>
                <span style={{ fontSize: '11px', color: '#96918a' }}>兵 {c.garrison} · 金 {c.gold}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }
  const city = state.cities[cityId]
  if (!city) {
    return (
      <div style={{ ...styles.card, textAlign: 'center', padding: '24px' }}>
        <i className="fa-solid fa-circle-question" style={{ fontSize: '28px', color: '#5a5a72', marginBottom: '10px' }}></i>
        <div style={styles.dim}>城市不存在</div>
      </div>
    )
  }

  const color = FACTION_COLORS[city.faction] || '#888888'
  const gens = Object.values(state.generals).filter((g) => g.location === city.id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ ...styles.card, borderLeft: `3px solid ${color}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <h3 style={{ color, margin: 0, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <i className="fa-solid fa-city"></i>
            {city.name}
          </h3>
          <div style={{ display: 'flex', gap: '2px' }}>
            {Array.from({ length: city.level }).map((_, i) => (
              <i key={i} className="fa-solid fa-star" style={{ color: '#d4a84b', fontSize: '10px' }}></i>
            ))}
          </div>
        </div>

        <div style={styles.detailGrid}>
          <span style={styles.dim}><i className="fa-solid fa-flag" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>势力</span>
          <span style={{ color: '#e8e0d0' }}>{FACTIONS[city.faction] || city.faction}</span>

          <span style={styles.dim}><i className="fa-solid fa-shield-halved" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>城墙</span>
          <span style={{ color: '#e8e0d0' }}>{city.wall_hp} / {city.wall_max_hp}</span>

          <span style={styles.dim}><i className="fa-solid fa-users" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>守军</span>
          <span style={{ color: '#e8e0d0' }}>{city.garrison}</span>

          <span style={styles.dim}><i className="fa-solid fa-coins" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>金钱</span>
          <span style={{ color: '#d4a84b' }}>{city.gold}</span>

          <span style={styles.dim}><i className="fa-solid fa-bread-slice" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>粮草</span>
          <span style={{ color: '#5ab464' }}>{city.food}</span>

          <span style={styles.dim}><i className="fa-solid fa-people-group" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>人口</span>
          <span style={{ color: '#e8e0d0' }}>{city.population}</span>

          <span style={styles.dim}><i className="fa-solid fa-heart" style={{ marginRight: '4px', width: '14px', textAlign: 'center' }}></i>民心</span>
          <span style={{ color: city.morale > 70 ? '#5ab464' : city.morale > 40 ? '#d4a84b' : '#c85046' }}>{city.morale}</span>
        </div>

        {city.is_besieged && (
          <div style={{ marginTop: '10px', padding: '8px 10px', backgroundColor: 'rgba(200, 80, 70, 0.15)', borderRadius: '6px', color: '#c85046', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <i className="fa-solid fa-triangle-exclamation"></i>
            被围困中
          </div>
        )}
      </div>

      {gens.length > 0 && (
        <div style={styles.card}>
          <div style={{ color: '#d4a84b', marginBottom: '8px', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <i className="fa-solid fa-user-shield"></i>
            驻守武将
          </div>
          {gens.map((g) => (
            <div key={g.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '12px' }}>
              <i className="fa-solid fa-user" style={{ color: '#96918a', fontSize: '10px' }}></i>
              <span style={{ color: '#e8e0d0', minWidth: '50px' }}>{g.name}</span>
              <ElementBadge general={g} />
              <span style={{ color: '#c85046' }}>统{g.command}</span>
              <span style={{ color: '#64a0d2' }}>政{g.politics}</span>
              <span style={{ color: '#c85046' }}>武{g.bravery}</span>
              <span style={{ color: '#d4a84b' }}>智{g.intelligence}</span>
              <span style={{ color: '#5ab464' }}>忠{g.loyalty}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * 五行配色（v4.0）
 *
 * 火赤 / 土黄 / 金白 / 水蓝 / 木青，与将领「将道」徽章配套使用。
 * 将道决定了战斗中的相克关系（克制 +15% / 被克 -15%），
 * 是观众理解「为什么这仗打赢了」的关键线索，因此必须在界面上可见。
 */
const ELEMENT_COLORS: Record<string, string> = {
  fire: '#d9604a',
  earth: '#c9a24b',
  metal: '#c8c2b4',
  water: '#5b93c4',
  wood: '#5aa86a',
}

/** 将道徽章：显示五行 + 悬停显示人物称号 */
function ElementBadge({ general }: { general: General }) {
  if (!general.element_name) return null
  const color = ELEMENT_COLORS[general.element || ''] || '#96918a'
  return (
    <span
      title={general.title || undefined}
      style={{
        color,
        border: `1px solid ${color}`,
        borderRadius: '3px',
        padding: '0 3px',
        fontSize: '10px',
        lineHeight: '14px',
        opacity: 0.9,
        whiteSpace: 'nowrap',
      }}
    >
      {general.element_name}
    </span>
  )
}

function GeneralList({ state }: { state: GameState }) {
  const byFaction: Record<string, typeof state.generals[string][]> = {}
  Object.values(state.generals).forEach((g) => {
    if (g.is_captured) return
    byFaction[g.faction] = byFaction[g.faction] || []
    byFaction[g.faction].push(g)
  })

  const factionOrder = Object.entries(state.faction_stats)
    .sort((a, b) => b[1].cities - a[1].cities)
    .map(([fid]) => fid)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {factionOrder.map((fid) => {
        const gens = byFaction[fid]
        if (!gens || gens.length === 0) return null
        const color = FACTION_COLORS[fid] || '#888888'
        return (
          <div key={fid} style={{ ...styles.card, borderLeft: `3px solid ${color}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', fontWeight: 600, fontSize: '13px', color }}>
              <i className="fa-solid fa-flag" style={{ fontSize: '11px' }}></i>
              {FACTIONS[fid] || fid}
              <span style={{ color: '#96918a', fontWeight: 400, fontSize: '11px' }}>({gens.length}人)</span>
            </div>
            {gens.slice(0, 5).map((g) => (
              <div key={g.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: '12px' }}>
                <i className="fa-solid fa-user" style={{ color: '#96918a', fontSize: '9px' }}></i>
                <span style={{ color: '#e8e0d0', minWidth: '50px' }}>{g.name}</span>
                <ElementBadge general={g} />
                <span style={{ color: '#c85046' }}>统{g.command}</span>
                <span style={{ color: '#64a0d2' }}>政{g.politics}</span>
                <span style={{ color: '#c85046' }}>武{g.bravery}</span>
                <span style={{ color: '#d4a84b' }}>智{g.intelligence}</span>
                <span style={{ color: '#5ab464' }}>忠{g.loyalty}</span>
              </div>
            ))}
            {gens.length > 5 && (
              <div style={{ color: '#5a5a72', fontSize: '11px', marginTop: '4px', textAlign: 'center' }}>
                <i className="fa-solid fa-ellipsis" style={{ marginRight: '4px' }}></i>还有 {gens.length - 5} 人
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/**
 * 战报 tab 事件分类
 *
 * 🔴 历史问题：建国/称王类事件（`X 称kingdom! 国号【魏】`）每回合都会刷一条，
 * 12 方时几乎占满整个事件流，把真实战斗挤到很下面，观众根本看不到打仗。
 * 现在把「战事」置顶常显，「建国/称王」单独归类并默认折叠。
 */
type EventCategory = 'battle' | 'kingdom' | 'diplomacy' | 'other'

const KINGDOM_PATTERNS = [/称(kingdom|王|帝|公|侯)/, /国号【/, /^🏰/]
const DIPLOMACY_PATTERNS = [/结盟/, /盟约/, /外交/, /通使/, /宣战/, /中立/, /同盟/]
const BATTLE_PATTERNS = [/攻占/, /占领/, /城陷/, /战斗/, /大战/, /围城/, /被围/, /投降/, /溃退/, /斩/, /大破/, /^第.*场战斗/]

function categorizeEvent(evt: GameEvent): EventCategory {
  const t = evt.text
  // 后端已打 type="kingdom" 的直接归建国；否则按文案判定
  if (evt.type === 'kingdom') return 'kingdom'
  if (evt.type === 'battle') return 'battle'
  if (KINGDOM_PATTERNS.some((p) => p.test(t))) return 'kingdom'
  if (BATTLE_PATTERNS.some((p) => p.test(t))) return 'battle'
  if (DIPLOMACY_PATTERNS.some((p) => p.test(t))) return 'diplomacy'
  return 'other'
}

const CATEGORY_META: Record<EventCategory, { label: string; icon: string; color: string }> = {
  battle: { label: '战事', icon: 'fa-khanda', color: '#c85046' },
  kingdom: { label: '建国 · 称王', icon: 'fa-crown', color: '#d4a84b' },
  diplomacy: { label: '外交', icon: 'fa-handshake', color: '#5ab464' },
  other: { label: '其他', icon: 'fa-scroll', color: '#96918a' },
}

const getEventIcon = (text: string): string => {
  if (text.includes('攻占') || text.includes('占领')) return 'fa-chess-rook'
  if (text.includes('战斗') || text.includes('攻')) return 'fa-khanda'
  if (text.includes('围')) return 'fa-triangle-exclamation'
  if (text.includes('迁都') || text.includes('建')) return 'fa-city'
  if (text.includes('外交') || text.includes('盟')) return 'fa-handshake'
  if (text.includes('投降') || text.includes('溃')) return 'fa-flag'
  if (text.includes('募兵') || text.includes('训练')) return 'fa-users'
  if (text.includes('发展') || text.includes('经济')) return 'fa-coins'
  return 'fa-scroll'
}

const getEventColor = (text: string): string => {
  if (text.includes('攻占') || text.includes('占领')) return '#d4a84b'
  if (text.includes('战斗') || text.includes('攻')) return '#c85046'
  if (text.includes('围')) return '#c85046'
  if (text.includes('建')) return '#64a0d2'
  if (text.includes('外交') || text.includes('盟')) return '#5ab464'
  if (text.includes('投降') || text.includes('溃')) return '#96918a'
  return '#96918a'
}

function EventLog({ events }: { events: GameEvent[] }) {
  // 倒序（最新在上）
  const ordered = [...events].reverse()
  const groups: Record<EventCategory, GameEvent[]> = {
    battle: [], kingdom: [], diplomacy: [], other: [],
  }
  ordered.forEach((e) => {
    groups[categorizeEvent(e)].push(e)
  })

  // 战事置顶常显；建国/称王默认折叠（它每回合刷屏，是噪声大头）
  const [showKingdom, setShowKingdom] = useState(false)
  const showDiplo = groups.diplomacy.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {groups.battle.length > 0 && (
        <CategorySection
          title={CATEGORY_META.battle.label}
          icon={CATEGORY_META.battle.icon}
          color={CATEGORY_META.battle.color}
          events={groups.battle}
        />
      )}

      {groups.battle.length === 0 && groups.kingdom.length > 0 && (
        <div style={{ fontSize: '11px', color: '#7d7a92', textAlign: 'center', padding: '6px 0' }}>
          暂无战斗事件（AI 还在内政发育）
        </div>
      )}

      {showDiplo && (
        <CategorySection
          title={CATEGORY_META.diplomacy.label}
          icon={CATEGORY_META.diplomacy.icon}
          color={CATEGORY_META.diplomacy.color}
          events={groups.diplomacy}
        />
      )}

      {groups.other.length > 0 && (
        <CategorySection
          title={CATEGORY_META.other.label}
          icon={CATEGORY_META.other.icon}
          color={CATEGORY_META.other.color}
          events={groups.other}
        />
      )}

      {groups.kingdom.length > 0 && (
        <div>
          <button
            style={styles.foldToggle}
            onClick={() => setShowKingdom((v) => !v)}
          >
            <i className={`fa-solid fa-chevron-${showKingdom ? 'down' : 'right'}`} style={{ marginRight: '6px', fontSize: '9px' }}></i>
            <i className={`fa-solid ${CATEGORY_META.kingdom.icon}`} style={{ marginRight: '5px', color: CATEGORY_META.kingdom.color }}></i>
            <span style={{ color: CATEGORY_META.kingdom.color }}>{CATEGORY_META.kingdom.label}</span>
            <span style={styles.foldCount}>{groups.kingdom.length} 条</span>
            <span style={styles.foldHint}>{showKingdom ? '点击折叠' : '点击展开'}</span>
          </button>
          {showKingdom && (
            <div style={{ marginTop: '6px' }}>
              <CategorySection
                title=""
                icon={CATEGORY_META.kingdom.icon}
                color={CATEGORY_META.kingdom.color}
                events={groups.kingdom}
                bare
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function CategorySection({
  title,
  icon,
  color,
  events,
  bare,
}: {
  title: string
  icon: string
  color: string
  events: GameEvent[]
  bare?: boolean
}) {
  return (
    <div>
      {!bare && (
        <div style={{ ...styles.sectionHead, color }}>
          <i className={`fa-solid ${icon}`} style={{ marginRight: '5px' }}></i>
          {title}
          <span style={styles.foldCount}>{events.length} 条</span>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        {events.map((evt, idx) => (
          <div key={`${evt.turn}-${idx}`} style={styles.logCard}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
              <i
                className={`fa-solid ${categorizeEvent(evt) === 'battle' ? icon : getEventIcon(evt.text)}`}
                style={{ color: categorizeEvent(evt) === 'battle' ? color : getEventColor(evt.text), fontSize: '10px', width: '14px', textAlign: 'center' }}
              ></i>
              <span style={{ color: '#5a5a72', fontSize: '11px' }}>第{evt.turn}回合</span>
            </div>
            <span style={{ color: '#e8e0d0', fontSize: '12px', lineHeight: '1.5', paddingLeft: '20px' }}>{evt.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** 同一回合里同一种命令可能重复多次（发展 ×2），折叠成 "发展 ×2"，避免刷屏 */
function countCommands(commands: string[]): [string, number][] {
  const counts = new Map<string, number>()
  commands.forEach((c) => counts.set(c, (counts.get(c) || 0) + 1))
  return [...counts.entries()]
}

function ReasoningPanel({ state }: { state: GameState }) {
  const entries = state.reasoning || []
  const llmActive = state.llm_active === true
  const llmRequested = state.llm_requested === true

  if (entries.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ ...styles.card, textAlign: 'center', padding: '24px' }}>
          <i
            className={`fa-solid ${llmActive ? 'fa-brain' : 'fa-circle-question'}`}
            style={{ fontSize: '28px', color: llmActive ? '#5ab464' : '#5a5a72', marginBottom: '10px' }}
          ></i>
          <div style={styles.dim}>
            {llmActive
              ? '模型已就位，推进一回合即可看到它的决策理由'
              : llmRequested
                ? '本局 LLM 未生效（已回退规则 AI），不会有模型决策理由'
                : '当前为规则 AI（CLI）开局，无决策理由。切换到「LLM 围观」并重开一局即可看到真实模型的意图。'}
          </div>
        </div>
        {!llmActive && (
          <div style={{ ...styles.card, borderLeft: '3px solid #d4a84b' }}>
            <div style={{ color: '#d4a84b', fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
              <i className="fa-solid fa-lightbulb" style={{ marginRight: '5px' }}></i>
              怎么看大模型的"主观意图"
            </div>
            <div style={{ color: '#b8b3aa', fontSize: '12px', lineHeight: '1.7' }}>
              1. 顶部切到 <span style={{ color: '#d4a84b' }}>LLM 围观</span>
              <br />
              2. 选 <span style={{ color: '#d4a84b' }}>3 个势力</span>（12 方会到分钟级）
              <br />
              3. 点 <span style={{ color: '#d4a84b' }}>重开一局</span>
              <br />
              4. 点 <span style={{ color: '#d4a84b' }}>下一回合</span>，等约 30 秒
            </div>
          </div>
        )}
      </div>
    )
  }

  // 按 turn 倒序分组（最新回合在上）
  const turns: number[] = []
  const byTurn: Record<number, ReasoningEntry[]> = {}
  entries.forEach((e) => {
    if (!byTurn[e.turn]) {
      byTurn[e.turn] = []
      turns.push(e.turn)
    }
    byTurn[e.turn].push(e)
  })
  turns.sort((a, b) => b - a)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {turns.map((turn) => (
        <div key={turn} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ color: '#d4a84b', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <i className="fa-solid fa-calendar-day"></i>
            第 {turn} 回合
          </div>
          {byTurn[turn].map((e, idx) => {
            const color = FACTION_COLORS[e.faction] || '#888888'
            return (
              <div key={`${turn}-${e.faction}-${idx}`} style={{ ...styles.card, borderLeft: `3px solid ${color}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: color, display: 'inline-block', flexShrink: 0 }}></span>
                  <span style={{ color: '#e8e0d0', fontWeight: 600, fontSize: '13px' }}>
                    {FACTIONS[e.faction] || e.faction}
                  </span>
                </div>
                <div style={{ color: '#b8b3aa', fontSize: '12px', lineHeight: '1.6', marginBottom: e.commands && e.commands.length > 0 ? '8px' : 0 }}>
                  {e.reasoning}
                </div>
                {e.commands && e.commands.length > 0 && (
                  <div style={styles.cmdRow}>
                    <span style={styles.cmdLabel}>本回合行动</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                      {countCommands(e.commands).map(([raw, n]) => (
                        <span key={raw} style={styles.cmdChip} title={raw}>
                          <i
                            className={`fa-solid ${commandIcon(raw)}`}
                            style={{ marginRight: '4px', fontSize: '9px' }}
                          ></i>
                          {commandLabel(raw)}
                          {n > 1 && <span style={styles.cmdCount}>×{n}</span>}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

function DataPanel({ state }: { state: GameState }) {
  const allGenerals = Object.values(state.generals).filter(g => !g.is_captured)
  const allCities = Object.values(state.cities)
  const topCommanders = [...allGenerals].sort((a, b) => b.command - a.command).slice(0, 10)
  const topPoliticians = [...allGenerals].sort((a, b) => b.politics - a.politics).slice(0, 10)
  const topBrave = [...allGenerals].sort((a, b) => b.bravery - a.bravery).slice(0, 10)
  const topIntel = [...allGenerals].sort((a, b) => b.intelligence - a.intelligence).slice(0, 10)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ ...styles.card }}>
        <div style={{ color: '#d4a84b', fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>
          <i className="fa-solid fa-ranking-star" style={{ marginRight: '6px' }}></i>武将排行榜
        </div>
        <RankList title="统帅 Top 5" items={topCommanders.slice(0, 5)} attr="command" color="#c85046" />
        <RankList title="政治 Top 5" items={topPoliticians.slice(0, 5)} attr="politics" color="#64a0d2" />
        <RankList title="勇武 Top 5" items={topBrave.slice(0, 5)} attr="bravery" color="#c85046" />
        <RankList title="智力 Top 5" items={topIntel.slice(0, 5)} attr="intelligence" color="#d4a84b" />
      </div>

      <div style={{ ...styles.card }}>
        <div style={{ color: '#d4a84b', fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>
          <i className="fa-solid fa-city" style={{ marginRight: '6px' }}></i>城池统计
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <StatBox label="总城池" value={allCities.length} />
          <StatBox label="总武将" value={allGenerals.length} />
          <StatBox label="总兵力" value={allCities.reduce((s, c) => s + c.garrison, 0)} />
          <StatBox label="总人口" value={allCities.reduce((s, c) => s + c.population, 0)} />
        </div>
      </div>
    </div>
  )
}

function RankList({ title, items, attr, color }: { title: string; items: General[]; attr: string; color: string }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ fontSize: '11px', color: '#96918a', marginBottom: '4px' }}>{title}</div>
      {items.map((g, i) => (
        <div key={g.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '12px' }}>
          <span style={{ color: '#e8e0d0' }}>{i + 1}. {g.name}</span>
          <span style={{ color }}>{(g as any)[attr]}</span>
        </div>
      ))}
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '8px', textAlign: 'center' }}>
      <div style={{ fontSize: '11px', color: '#96918a', marginBottom: '2px' }}>{label}</div>
      <div style={{ fontSize: '15px', color: '#e8e0d0', fontWeight: 600 }}>{value.toLocaleString()}</div>
    </div>
  )
}

function EventsPanel({ state }: { state: GameState }) {
  const turnLogs = state.turn_logs || []
  // [修复 2026-10-01] 开局 turn_logs 还空时回退展示 state.events，
  // 避免"事件 tab 空着、但事件流明明有事件"的口径不一致。
  const events = state.events || []
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ color: '#d4a84b', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
        <i className="fa-solid fa-calendar-day" style={{ marginRight: '6px' }}></i>回合事件
      </div>
      {turnLogs.length === 0 && events.length === 0 && (
        <div style={{ fontSize: '12px', color: '#666', textAlign: 'center', padding: '20px 0' }}>暂无记录</div>
      )}
      {turnLogs.length === 0 && events.length > 0 && (
        <div style={{ ...styles.card, padding: '10px' }}>
          <div style={{ fontSize: '12px', color: '#96918a', marginBottom: '6px' }}>开局事件</div>
          {events.slice().reverse().map((e, i) => (
            <div key={i} style={{ fontSize: '12px', color: '#e8e0d0', marginBottom: '4px' }}>
              <span style={{ color: '#96918a', marginRight: '6px' }}>第{e.turn}回合</span>{e.text}
            </div>
          ))}
        </div>
      )}
      {turnLogs.slice().reverse().map((tl) => (
        <div key={tl.turn} style={{ ...styles.card, padding: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '13px', color: '#e8e0d0', fontWeight: 600 }}>第 {tl.turn} 回合</span>
            <span style={{ fontSize: '11px', color: '#96918a' }}>{state.year}年</span>
          </div>
          <div style={{ display: 'flex', gap: '12px', fontSize: '12px' }}>
            <span style={{ color: '#c85046' }}><i className="fa-solid fa-khanda" style={{ marginRight: '3px' }}></i>{tl.battles_fought} 战斗</span>
            <span style={{ color: '#5ab464' }}><i className="fa-solid fa-person-military-rifle" style={{ marginRight: '3px' }}></i>{tl.armies_moved} 行军</span>
            {tl.cities_captured.length > 0 && (
              <span style={{ color: '#d4a84b' }}><i className="fa-solid fa-chess-rook" style={{ marginRight: '3px' }}></i>{tl.cities_captured.length} 城陷</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  /** 势力卡上的「指挥模型」小标签（v4.0.1 多模型对战） */
  modelTag: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0 4px',
    border: '1px solid rgba(100, 160, 210, 0.5)',
    borderRadius: '8px',
    color: '#64a0d2',
    fontSize: '9px',
    fontWeight: 400,
    whiteSpace: 'nowrap',
  },
  container: {
    width: '300px',
    height: '100%',
    backgroundColor: 'rgba(18, 18, 34, 0.85)',
    borderLeft: '1px solid rgba(255, 255, 255, 0.06)',
    backdropFilter: 'blur(12px)',
    display: 'flex',
    flexDirection: 'column',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
    padding: '6px 6px 0',
    gap: '2px',
  },
  tab: {
    flex: 1,
    padding: '6px 2px',
    border: '1px solid transparent',
    borderBottom: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontFamily: 'inherit',
    borderRadius: '6px 6px 0 0',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    transition: 'all 0.2s ease',
  },
  content: {
    flex: 1,
    padding: '12px',
    overflowY: 'auto',
  },
  glassCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: '10px',
    padding: '14px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    backdropFilter: 'blur(4px)',
  },
  card: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: '10px',
    padding: '12px',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    backdropFilter: 'blur(4px)',
    transition: 'background-color 0.2s ease',
  },
  dim: {
    color: '#96918a',
    fontSize: '13px',
  },
  statGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr',
    gap: '6px',
  },
  statItem: {
    display: 'flex',
    alignItems: 'center',
    color: '#96918a',
    fontSize: '12px',
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    gap: '8px 12px',
    fontSize: '13px',
    color: '#e8e0d0',
    alignItems: 'center',
  },
  logCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '8px',
    padding: '8px 10px',
    border: '1px solid rgba(255, 255, 255, 0.04)',
  },
  sectionHead: {
    display: 'flex',
    alignItems: 'center',
    fontSize: '12px',
    fontWeight: 600,
    marginBottom: '6px',
  },
  foldCount: {
    marginLeft: '6px',
    color: '#7d7a92',
    fontSize: '10px',
    fontWeight: 400,
  },
  foldHint: {
    marginLeft: 'auto',
    color: '#5a5a72',
    fontSize: '10px',
    fontWeight: 400,
  },
  foldToggle: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    padding: '7px 10px',
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid rgba(255, 255, 255, 0.06)',
    borderRadius: '8px',
    fontSize: '12px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    textAlign: 'left',
  },
  cmdRow: {
    paddingTop: '8px',
    borderTop: '1px solid rgba(255, 255, 255, 0.06)',
  },
  cmdLabel: {
    display: 'block',
    color: '#7d7a92',
    fontSize: '10px',
    marginBottom: '5px',
  },
  cmdChip: {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: '10px',
    color: '#d4a84b',
    backgroundColor: 'rgba(212, 168, 75, 0.12)',
    border: '1px solid rgba(212, 168, 75, 0.3)',
    borderRadius: '4px',
    padding: '2px 7px',
  },
  cmdCount: {
    marginLeft: '4px',
    color: '#a8874a',
    fontSize: '9px',
  },
}
