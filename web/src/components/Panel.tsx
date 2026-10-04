import { useEffect, useState } from 'react'
import type { GameEvent, GameState, General, ReasoningEntry, TurnLog } from '../types'
import { FACTION_COLORS, FACTIONS, PANEL_W, STAT_COLORS, UI_COLORS } from '../theme'
// [H2 2026-10-04] 事件正文是否自带回合号（避免同一条并列两个回合号）
import { hasTurnInText } from '../utils/eventTurn'
// [阶段B] 决策正文用霞鹜文楷（局部按需，见 utils/wenKai.ts）
import { useWenKai, WENKAI_STACK } from '../utils/wenKai'
// [阶段B] 势力单字徽标——色盲/灰度下的非颜色线索
import { FactionBadge } from './FactionBadge'
import { commandIcon, commandLabel } from '../constants/commands'
import { DiplomacyPanel } from './DiplomacyPanel'
// [交互 2026-10-03] hover 悬浮说明（审计 §4-3）：资源数字此前无任何解释
import { Hint } from './Tooltip'

type TabKey = 'factions' | 'city' | 'generals' | 'diplomacy' | 'data' | 'events' | 'log' | 'reasoning' | 'records'

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
  { key: 'records', label: '战绩', icon: 'fa-trophy' },
]

export function Panel({ state, tab, setTab, selectedCityId, selectedFaction, setSelectedFaction, onSelectCity }: PanelProps) {
  // [M8 2026-10-04] tab 的 hover 反馈。必须在 state 为空的提前返回**之前**声明，
  // 否则 hook 调用数量会随渲染变化，违反 React hook 规则。
  const [hoverTab, setHoverTab] = useState<TabKey | null>(null)

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
              // [M8] 选中 > hover > 常态（tab 原本连 hover 都没有）
              backgroundColor:
                tab === t.key ? 'rgba(200, 168, 90, 0.15)' : hoverTab === t.key ? 'rgba(255, 255, 255, 0.06)' : 'transparent',
              color: tab === t.key ? 'var(--gold)' : hoverTab === t.key ? '#d8d2c6' : UI_COLORS.textSecondary,
              borderColor: tab === t.key ? 'rgba(200, 168, 90, 0.4)' : 'transparent',
            }}
            onMouseEnter={() => setHoverTab(t.key)}
            onMouseLeave={() => setHoverTab((cur) => (cur === t.key ? null : cur))}
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
        {tab === 'records' && <ModelRecordsPanel />}
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

  // [M8 2026-10-04] hover 反馈：此前只有 cursor:pointer，鼠标悬停时毫无变化，
  // 观众无法预判"这个能不能点 / 我指着哪一个"。
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {/* [M4 2026-10-04] 12 方在 ≤1600×900 下一屏放不下（实测需滚 112~412px）。
          先显式告知总数，避免观众误以为"只有 8 方"；同时把卡片纵向间距压紧，
          让 1600×900 / 1440×900 这两档能一屏看全。 */}
      <div style={styles.listHead}>
        <span>共 {rows.length} 方势力</span>
        <span style={{ color: UI_COLORS.textMuted }}>· 点击高亮，向下滚动看全部</span>
      </div>
      {rows.map((row) => {
        const color = FACTION_COLORS[row.fid] || '#888888'
        const isSelected = selectedFaction === row.fid
        const dead = row.is_alive === false
        return (
          <div
            key={row.fid}
            style={{
              ...styles.card,
              padding: '10px',
              borderLeft: `3px solid ${color}`,
              backgroundColor: isSelected
                ? 'rgba(200, 168, 90, 0.1)'
                : hovered === row.fid
                  ? 'rgba(255, 255, 255, 0.07)'
                  : 'rgba(255, 255, 255, 0.03)',
              cursor: 'pointer',
              opacity: dead ? 0.55 : 1,
            }}
            onMouseEnter={() => setHovered(row.fid)}
            onMouseLeave={() => setHovered((cur) => (cur === row.fid ? null : cur))}
            onClick={() => setSelectedFaction(row.fid)}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isSelected ? 'var(--text)' : '#b8b3aa', fontWeight: 600, fontSize: '14px', fontFamily: 'var(--font-serif)' }}>
                <FactionBadge faction={row.fid} size={18} />
                {row.name}
                {/* 「已出局」标识：后端一直返回 is_alive，此前前端零处引用 → 灭亡势力
                    仍按普通卡片列。现明确标红，观众一眼看出谁已经退出争夺。 */}
                {dead && (
                  <span style={styles.deadTag} title="城池尽失，已退出争夺">已出局</span>
                )}
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
              {row.cities >= 5 && <i className="fa-solid fa-crown" style={{ color: 'var(--gold)', fontSize: '11px' }} title="称帝"></i>}
              {row.cities >= 3 && row.cities < 5 && <i className="fa-solid fa-gem" style={{ color: 'var(--blue)', fontSize: '11px' }} title="称王"></i>}
            </div>
            <div style={styles.statGrid}>
              <Hint content={{ title: '城池', lines: ['该势力当前控制的城池数'] }}>
                <span style={styles.statItem}>
                  <i className="fa-solid fa-chess-rook" style={{ color: 'var(--gold)', fontSize: '10px', marginRight: '3px' }}></i>
                  {row.cities}城
                </span>
              </Hint>
              <Hint content={{ title: '总守军', lines: ['各城守军兵力之和'] }}>
                <span style={styles.statItem}>
                  <i className="fa-solid fa-users" style={{ color: 'var(--green)', fontSize: '10px', marginRight: '3px' }}></i>
                  {row.garrison}
                </span>
              </Hint>
              <Hint content={{ title: '金钱', lines: ['各城金库之和；征兵/发展/赏赐都要花钱'] }}>
                <span style={styles.statItem}>
                  <i className="fa-solid fa-coins" style={{ color: 'var(--gold)', fontSize: '10px', marginRight: '3px' }}></i>
                  {row.gold}
                </span>
              </Hint>
            </div>
          </div>
        )
      })}
    </div>
  )
}

/**
 * 城市列表
 *
 * 原先此 tab 在选中城市后渲染一张**纯只读**详情卡（审计 §1「城市详情卡：整卡无 button」）。
 * 现把详情卡迁到地图浮层 `CityCard.tsx`（带真实可执行操作），此 tab 只负责
 * 「可选中、可高亮」的城市清单 —— 点击任一城 → 地图居中并弹出详情卡。
 */
function CityDetail({ state, cityId, onSelectCity }: { state: GameState; cityId: string | null; onSelectCity: (id: string) => void }) {
  const cities = Object.values(state.cities)
  const byFaction: Record<string, typeof cities> = {}
  cities.forEach((c) => { (byFaction[c.faction] = byFaction[c.faction] || []).push(c) })
  // [M8] 城市行的 hover 反馈
  const [hoverCity, setHoverCity] = useState<string | null>(null)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ fontSize: '13px', color: 'var(--gold)' }}>
        城市列表（{cities.length}）<span style={{ color: 'var(--text-muted)', fontSize: '11px' }}> · 点击在地图定位并查看详情</span>
      </div>
      {Object.keys(FACTIONS).filter((f) => byFaction[f]?.length).map((f) => (
        <div key={f} style={styles.card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: FACTION_COLORS[f] || '#888' }} />
            <span style={{ fontSize: '12px', color: UI_COLORS.textSecondary }}>{FACTIONS[f] || f} · {byFaction[f].length} 城</span>
          </div>
          {byFaction[f].map((c) => {
            const selected = cityId === c.id
            return (
              <Hint
                key={c.id}
                style={{ display: 'block' }}
                content={{
                  title: `${c.name} · ${FACTIONS[c.faction] || c.faction}`,
                  lines: [`守军 ${c.garrison.toLocaleString()} · 金钱 ${c.gold.toLocaleString()}`, c.is_besieged ? '⚠ 被围困中' : '单击定位并打开详情卡'],
                }}
              >
                <div
                  data-panel-city-id={c.id}
                  onClick={() => onSelectCity(c.id)}
                  onMouseEnter={() => setHoverCity(c.id)}
                  onMouseLeave={() => setHoverCity((cur) => (cur === c.id ? null : cur))}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '6px 8px', marginBottom: '4px', borderRadius: '6px', cursor: 'pointer',
                    // [M8] 选中 > hover > 常态
                    background: selected
                      ? 'rgba(200, 168, 90, 0.14)'
                      : hoverCity === c.id
                        ? 'rgba(255, 255, 255, 0.07)'
                        : 'rgba(255,255,255,0.03)',
                    border: selected ? '1px solid rgba(200, 168, 90, 0.45)' : '1px solid transparent',
                  }}
                >
                  <span style={{ fontSize: '13px', color: selected ? '#e8c877' : 'var(--text)' }}>
                    {selected && <i className="fa-solid fa-location-crosshairs" style={{ marginRight: '5px', fontSize: '10px' }}></i>}
                    {c.name}
                  </span>
                  <span style={{ fontSize: '11px', color: UI_COLORS.textSecondary }}>兵 {c.garrison} · 金 {c.gold}</span>
                </div>
              </Hint>
            )
          })}
        </div>
      ))}
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
  const color = ELEMENT_COLORS[general.element || ''] || UI_COLORS.textSecondary
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
  // 展开显示全部的势力集合（此前硬编码 slice(0,5)，「还有 N 人」还是不可点的纯文字
  // → 第 6 名之后的武将永远看不到）
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggle = (fid: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(fid)) next.delete(fid)
      else next.add(fid)
      return next
    })
  }

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
        const isOpen = expanded.has(fid)
        const shown = isOpen ? gens : gens.slice(0, 5)
        return (
          <div key={fid} style={{ ...styles.card, borderLeft: `3px solid ${color}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', fontWeight: 600, fontSize: '13px', color }}>
              <FactionBadge faction={fid} size={16} />
              {FACTIONS[fid] || fid}
              <span style={{ color: UI_COLORS.textSecondary, fontWeight: 400, fontSize: '11px' }}>({gens.length}人)</span>
            </div>
            {shown.map((g) => (
              <div key={g.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: '12px' }}>
                <i className="fa-solid fa-user" style={{ color: UI_COLORS.textSecondary, fontSize: '9px' }}></i>
                <span style={{ color: 'var(--text)', minWidth: '50px' }}>{g.name}</span>
                <ElementBadge general={g} />
                <span style={{ color: STAT_COLORS.command }}>统{g.command}</span>
                <span style={{ color: STAT_COLORS.politics }}>政{g.politics}</span>
                <span style={{ color: STAT_COLORS.bravery }}>武{g.bravery}</span>
                <span style={{ color: STAT_COLORS.intelligence }}>智{g.intelligence}</span>
                <span style={{ color: STAT_COLORS.loyalty }}>忠{g.loyalty}</span>
              </div>
            ))}
            {gens.length > 5 && (
              <button
                style={styles.expandToggle}
                onClick={() => toggle(fid)}
                title={isOpen ? '收起' : '查看全部武将'}
              >
                <i className={`fa-solid fa-chevron-${isOpen ? 'up' : 'down'}`} style={{ marginRight: '5px' }}></i>
                {isOpen ? '收起' : `还有 ${gens.length - 5} 人（点击展开）`}
              </button>
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

// [M2 2026-10-04] 去 emoji：后端建国事件不再带 🏰 前缀，故去掉 /^🏰/ 判定，
// 仍由 evt.type==='kingdom' 与「国号【」两条守卫归类。
const KINGDOM_PATTERNS = [/称(kingdom|王|帝|公|侯)/, /国号【/]
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
  battle: { label: '战事', icon: 'fa-khanda', color: 'var(--red)' },
  kingdom: { label: '建国 · 称王', icon: 'fa-crown', color: 'var(--gold)' },
  diplomacy: { label: '外交', icon: 'fa-handshake', color: 'var(--green)' },
  other: { label: '其他', icon: 'fa-scroll', color: UI_COLORS.textSecondary },
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
  if (text.includes('攻占') || text.includes('占领')) return 'var(--gold)'
  if (text.includes('战斗') || text.includes('攻')) return 'var(--red)'
  if (text.includes('围')) return 'var(--red)'
  if (text.includes('建')) return 'var(--blue)'
  if (text.includes('外交') || text.includes('盟')) return 'var(--green)'
  if (text.includes('投降') || text.includes('溃')) return UI_COLORS.textSecondary
  return UI_COLORS.textSecondary
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
        <div style={{ fontSize: '11px', color: UI_COLORS.textMuted, textAlign: 'center', padding: '6px 0' }}>
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
              {/* [H2 2026-10-04] 正文自带回合号时不再补前缀，避免同一条出现两个回合号 */}
              {!hasTurnInText(evt.text) && (
                <span style={{ color: UI_COLORS.textMuted, fontSize: '11px' }}>第{evt.turn}回合</span>
              )}
            </div>
            <span style={{ color: 'var(--text)', fontSize: '12px', lineHeight: '1.5', paddingLeft: '20px' }}>{evt.text}</span>
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
  // B2：决策理由不再随 /api/state 每帧下发（否则自动推进下 /api/state 会涨到 ~200KB）。
  // 本组件仅在该 Tab 激活时才挂载，于是「切到决策 Tab」即触发按需拉取；
  // 并把 turn 纳入依赖，每回合推进后再拉一次，保证看到最新理由。
  const API_BASE = import.meta.env.VITE_API_BASE || ''
  const [entries, setEntries] = useState<ReasoningEntry[]>(state?.reasoning || [])
  const [loading, setLoading] = useState(false)
  const llmActive = state?.llm_active === true
  const llmRequested = state?.llm_requested === true
  const turn = state?.turn ?? 0

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/reasoning`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return
        const list = Array.isArray(data.reasoning) ? data.reasoning : []
        setEntries(list as ReasoningEntry[])
      })
      .catch(() => {
        // 拉取失败不阻断面板：保持空态提示，不抛错、不假绿
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [turn])

  // 只在真的有决策理由要显示时才拉霞鹜文楷
  useWenKai(entries.length > 0)

  if (entries.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {loading ? (
          <div style={{ ...styles.card, textAlign: 'center', padding: '24px' }}>
            <i
              className="fa-solid fa-spinner fa-spin"
              style={{ fontSize: '28px', color: UI_COLORS.textMuted, marginBottom: '10px' }}
            ></i>
            <div style={styles.dim}>加载决策理由中…</div>
          </div>
        ) : (
        <div style={{ ...styles.card, textAlign: 'center', padding: '24px' }}>
          <i
            className={`fa-solid ${llmActive ? 'fa-brain' : 'fa-circle-question'}`}
            style={{ fontSize: '28px', color: llmActive ? 'var(--green)' : UI_COLORS.textMuted, marginBottom: '10px' }}
          ></i>
          <div style={styles.dim}>
            {llmActive
              ? '模型已就位，推进一回合即可看到它的决策理由'
              : llmRequested
                ? '本局 LLM 未生效（已回退规则 AI），不会有模型决策理由'
                : '当前为规则 AI（CLI）开局，无决策理由。切换到「LLM 围观」并重开一局即可看到真实模型的意图。'}
          </div>
        </div>
        )}
        {!loading && !llmActive && (
          <div style={{ ...styles.card, borderLeft: '3px solid var(--gold)' }}>
            <div style={{ color: 'var(--gold)', fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
              <i className="fa-solid fa-lightbulb" style={{ marginRight: '5px' }}></i>
              怎么看大模型的"主观意图"
            </div>
            <div style={{ color: '#b8b3aa', fontSize: '12px', lineHeight: '1.7' }}>
              1. 顶部切到 <span style={{ color: 'var(--gold)' }}>LLM 围观</span>
              <br />
              2. 选 <span style={{ color: 'var(--gold)' }}>3 个势力</span>（12 方会到分钟级）
              <br />
              3. 点 <span style={{ color: 'var(--gold)' }}>重开一局</span>
              <br />
              4. 点 <span style={{ color: 'var(--gold)' }}>下一回合</span>，等约 30 秒
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
          <div style={{ color: 'var(--gold)', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <i className="fa-solid fa-calendar-day"></i>
            第 {turn} 回合
          </div>
          {byTurn[turn].map((e, idx) => {
            const color = FACTION_COLORS[e.faction] || '#888888'
            return (
              <div key={`${turn}-${e.faction}-${idx}`} style={{ ...styles.card, borderLeft: `3px solid ${color}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: color, display: 'inline-block', flexShrink: 0 }}></span>
                  <span style={{ color: 'var(--text)', fontWeight: 600, fontSize: '13px' }}>
                    {FACTIONS[e.faction] || e.faction}
                  </span>
                </div>
                <div style={{ color: '#b8b3aa', fontSize: '12px', lineHeight: '1.6', marginBottom: e.commands && e.commands.length > 0 ? '8px' : 0, fontFamily: WENKAI_STACK }}>
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

// [批次B5] 跨局模型战绩榜：/api/model_records 早已存在，前端从未接线，
// 等于「定义了但观众永远看不到」。这里作为独立 Tab 按需拉取并展示。
interface ModelRecordRow {
  model: string
  matches: number
  wins: number
  win_rate: number
  avg_rank: number
  avg_cities: number
}
interface RecentMatchResult {
  faction: string
  faction_name: string
  model: string
  cities: number
  rank: number
  winner: boolean
}
interface RecentMatch {
  ts: string
  seed: number
  max_turns: number
  turns: number
  winner: string
  results: RecentMatchResult[]
}
interface ModelRecordsData {
  leaderboard: ModelRecordRow[]
  recent: RecentMatch[]
  total_matches: number
}

function ModelRecordsPanel() {
  const API_BASE = import.meta.env.VITE_API_BASE || ''
  const [data, setData] = useState<ModelRecordsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/model_records`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        if (!cancelled) setData(d as ModelRecordsData)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <div style={styles.dim}>加载战绩中…</div>
  }
  if (error) {
    return (
      <div style={{ ...styles.card, borderLeft: '3px solid #e0776d', color: '#e8a04b' }}>
        <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '6px' }}></i>
        战绩加载失败：{error}
      </div>
    )
  }
  if (!data || data.total_matches === 0) {
    return (
      <div style={{ ...styles.card, textAlign: 'center', padding: '24px' }}>
        <i
          className="fa-solid fa-trophy"
          style={{ fontSize: '28px', color: UI_COLORS.textMuted, marginBottom: '10px' }}
        ></i>
        <div style={styles.dim}>
          还没有跨局战绩。完成一局「LLM 围观」后，各模型的胜率与平均排名会在这里累计，
          用来回答「哪个大模型更会玩三国」。
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div>
        <div style={{ ...styles.sectionHead, color: 'var(--gold)' }}>
          <i className="fa-solid fa-trophy" style={{ marginRight: '5px' }}></i>
          模型战绩榜
          <span style={styles.foldCount}>{data.total_matches} 局累计</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          {data.leaderboard.map((row) => (
            <div
              key={row.model}
              style={{ ...styles.card, borderLeft: '3px solid var(--gold)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <span style={{ color: 'var(--text)', fontWeight: 600, fontSize: '13px' }}>
                  {row.model || '(未记录模型)'}
                </span>
                <span style={{ color: 'var(--green)', fontSize: '13px', fontWeight: 600 }}>
                  胜率 {Math.round(row.win_rate * 100)}%
                </span>
              </div>
              <div style={{ display: 'flex', gap: '14px', color: 'var(--text-2)', fontSize: '11px', marginTop: '4px' }}>
                <span>参战 {row.matches} 局</span>
                <span>胜 {row.wins}</span>
                <span>平均排名 {row.avg_rank}</span>
                <span>平均城池 {row.avg_cities}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div style={{ ...styles.sectionHead, color: 'var(--gold)' }}>
          <i className="fa-solid fa-clock-rotate-left" style={{ marginRight: '5px' }}></i>
          最近对局
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          {data.recent.map((m, i) => (
            <div key={`${m.ts}-${i}`} style={{ ...styles.card }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{ color: '#d8d2c6', fontSize: '12px' }}>
                  seed {m.seed} · 第 {m.turns} 回合 · 胜方 {FACTIONS[m.winner] || m.winner}
                </span>
                <span style={{ color: UI_COLORS.textMuted, fontSize: '10px' }}>{m.ts}</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                {m.results.map((r) => (
                  <span
                    key={r.faction}
                    style={{
                      ...styles.cmdChip,
                      borderColor: r.winner ? 'rgba(90,180,100,0.6)' : 'rgba(255,255,255,0.12)',
                    }}
                    title={`${r.faction_name}：城池 ${r.cities} · 排名 ${r.rank}`}
                  >
                    {r.winner && <i className="fa-solid fa-crown" style={{ marginRight: '3px', color: '#e8c877', fontSize: '9px' }}></i>}
                    {r.faction_name}
                    {r.model ? `（${r.model}）` : ''}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
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
        <div style={{ color: 'var(--gold)', fontSize: '13px', fontWeight: 600, marginBottom: '10px', fontFamily: 'var(--font-serif)' }}>
          <i className="fa-solid fa-ranking-star" style={{ marginRight: '6px' }}></i>武将排行榜
        </div>
        <RankList title="统帅 Top 5" items={topCommanders.slice(0, 5)} attr="command" color={STAT_COLORS.command} />
        <RankList title="政治 Top 5" items={topPoliticians.slice(0, 5)} attr="politics" color={STAT_COLORS.politics} />
        <RankList title="勇武 Top 5" items={topBrave.slice(0, 5)} attr="bravery" color={STAT_COLORS.bravery} />
        <RankList title="智力 Top 5" items={topIntel.slice(0, 5)} attr="intelligence" color={STAT_COLORS.intelligence} />
      </div>

      <div style={{ ...styles.card }}>
        <div style={{ color: 'var(--gold)', fontSize: '13px', fontWeight: 600, marginBottom: '10px', fontFamily: 'var(--font-serif)' }}>
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
      <div style={{ fontSize: '11px', color: UI_COLORS.textSecondary, marginBottom: '4px', fontFamily: 'var(--font-serif)' }}>{title}</div>
      {items.map((g, i) => (
        <div key={g.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '12px' }}>
          <span style={{ color: 'var(--text)' }}>{i + 1}. {g.name}</span>
          <span style={{ color }}>{(g as any)[attr]}</span>
        </div>
      ))}
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '6px', padding: '8px', textAlign: 'center' }}>
      <div style={{ fontSize: '11px', color: UI_COLORS.textSecondary, marginBottom: '2px', fontFamily: 'var(--font-serif)' }}>{label}</div>
      <div style={{ fontSize: '15px', color: 'var(--text)', fontWeight: 600 }}>{value.toLocaleString()}</div>
    </div>
  )
}

/**
 * [L9 2026-10-04] 把连续的「无战事」回合折叠成一行。
 *
 * 实测开局阶段连着 10 个回合都是「0 战斗 0 行军」，平铺占满整屏，
 * 把真正有内容的回合挤到看不见。折叠后 10 行 → 1 行。
 * 注意入参是**已倒序**（最新在前）的日志，因此 from 是新回合、to 是旧回合。
 */
type TurnRow = { idle: false; tl: TurnLog } | { idle: true; from: number; to: number }

function foldIdleTurns(logs: TurnLog[]): TurnRow[] {
  const isIdle = (t: TurnLog) =>
    t.battles_fought === 0 && t.armies_moved === 0 && (t.cities_captured?.length ?? 0) === 0
  const rows: TurnRow[] = []
  let idle: { from: number; to: number } | null = null
  const flush = () => {
    if (idle) rows.push({ idle: true, from: idle.from, to: idle.to })
    idle = null
  }
  for (const t of logs) {
    if (isIdle(t)) {
      if (idle) idle.to = t.turn
      else idle = { from: t.turn, to: t.turn }
    } else {
      flush()
      rows.push({ idle: false, tl: t })
    }
  }
  flush()
  return rows
}

function EventsPanel({ state }: { state: GameState }) {
  const turnLogs = state.turn_logs || []
  // [修复 2026-10-01] 开局 turn_logs 还空时回退展示 state.events，
  // 避免"事件 tab 空着、但事件流明明有事件"的口径不一致。
  const events = state.events || []
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ color: 'var(--gold)', fontSize: '13px', fontWeight: 600, marginBottom: '4px', fontFamily: 'var(--font-serif)' }}>
        <i className="fa-solid fa-calendar-day" style={{ marginRight: '6px' }}></i>回合事件
      </div>
      {turnLogs.length === 0 && events.length === 0 && (
        <div style={{ fontSize: '12px', color: '#666', textAlign: 'center', padding: '20px 0' }}>暂无记录</div>
      )}
      {turnLogs.length === 0 && events.length > 0 && (
        <div style={{ ...styles.card, padding: '10px' }}>
          <div style={{ fontSize: '12px', color: UI_COLORS.textSecondary, marginBottom: '6px' }}>开局事件</div>
          {events.slice().reverse().map((e, i) => (
            <div key={i} style={{ fontSize: '12px', color: 'var(--text)', marginBottom: '4px' }}>
              {/* [H2 2026-10-04] 同上：正文已含回合号则不再加前缀 */}
              {!hasTurnInText(e.text) && (
                <span style={{ color: UI_COLORS.textSecondary, marginRight: '6px' }}>第{e.turn}回合</span>
              )}
              {e.text}
            </div>
          ))}
        </div>
      )}
      {foldIdleTurns(turnLogs.slice().reverse()).map((row, i) =>
        row.idle ? (
          <div key={`idle-${i}-${row.from}-${row.to}`} style={styles.idleRow}>
            <i className="fa-solid fa-moon" style={{ marginRight: '5px', fontSize: '10px' }}></i>
            {row.from === row.to ? `第 ${row.from} 回合` : `第 ${row.to}–${row.from} 回合`}
            ：无战事
          </div>
        ) : (
          <div key={row.tl.turn} style={{ ...styles.card, padding: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '13px', color: 'var(--text)', fontWeight: 600 }}>第 {row.tl.turn} 回合</span>
              <span style={{ fontSize: '11px', color: UI_COLORS.textSecondary }}>{state.year}年</span>
            </div>
            <div style={{ display: 'flex', gap: '12px', fontSize: '12px' }}>
              <span style={{ color: 'var(--red)' }}><i className="fa-solid fa-khanda" style={{ marginRight: '3px' }}></i>{row.tl.battles_fought} 战斗</span>
              <span style={{ color: 'var(--green)' }}><i className="fa-solid fa-person-military-rifle" style={{ marginRight: '3px' }}></i>{row.tl.armies_moved} 行军</span>
              {row.tl.cities_captured.length > 0 && (
                <span style={{ color: 'var(--gold)' }}><i className="fa-solid fa-chess-rook" style={{ marginRight: '3px' }}></i>{row.tl.cities_captured.length} 城陷</span>
              )}
            </div>
          </div>
        ),
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  /** 势力卡上的「已出局」标识（is_alive=false） */
  deadTag: {
    fontSize: '10px',
    fontWeight: 400,
    color: '#e0776d',
    border: '1px solid rgba(157, 41, 51, 0.55)',
    borderRadius: '4px',
    padding: '0 4px',
    whiteSpace: 'nowrap',
  },
  /** 武将列表「展开全部」按钮（替代不可点的纯文字提示） */
  expandToggle: {
    marginTop: '6px',
    width: '100%',
    padding: '5px 8px',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '6px',
    color: 'var(--text-muted)',
    fontSize: '11px',
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  /** 势力卡上的「指挥模型」小标签（v4.0.1 多模型对战） */
  modelTag: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0 4px',
    border: '1px solid rgba(100, 160, 210, 0.5)',
    borderRadius: '6px',
    color: 'var(--blue)',
    fontSize: '9px',
    fontWeight: 400,
    whiteSpace: 'nowrap',
  },
  /** [L9] 被折叠的「无战事」回合段（虚线框，与有内容的实卡片区分） */
  idleRow: {
    display: 'flex',
    alignItems: 'center',
    padding: '6px 10px',
    borderRadius: '6px',
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px dashed rgba(255, 255, 255, 0.1)',
    color: UI_COLORS.textMuted,
    fontSize: '11px',
  },
  /** [M4] 列表顶部计数条：12 方在小屏一屏放不下，先告知总数是几方 */
  listHead: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '4px',
    padding: '2px 2px 0',
    fontSize: '11px',
    color: UI_COLORS.textSecondary,
  },
  container: {
    width: PANEL_W, // [M5] 与所有浮层的 right 偏移同一事实源
    height: '100%',
    backgroundColor: 'rgba(20, 32, 40, 0.85)',
    borderLeft: '1px solid var(--panel-border)',
    display: 'flex',
    flexDirection: 'column',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid var(--panel-border)',
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
    borderRadius: '6px',
    padding: '14px',
    border: '1px solid var(--panel-border)',
  },
  card: {
    backgroundColor: 'rgba(255, 255, 255, 0.04)',
    borderRadius: '6px',
    padding: '12px',
    border: '1px solid var(--panel-border)',
    transition: 'background-color 0.2s ease',
  },
  dim: {
    color: 'var(--text-2)', // 阶段A：提亮（原 #96918a）
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
    color: UI_COLORS.textSecondary,
    fontSize: '12px',
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    gap: '8px 12px',
    fontSize: '13px',
    color: 'var(--text)',
    alignItems: 'center',
  },
  logCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: '6px',
    padding: '8px 10px',
    border: '1px solid rgba(255, 255, 255, 0.04)',
  },
  sectionHead: {
    display: 'flex',
    alignItems: 'center',
    fontSize: '12px',
    fontWeight: 600,
    marginBottom: '6px',
    // [D2] 标题回衬线栈（汉风层级；正文仍无衬线）
    fontFamily: 'var(--font-serif)',
  },
  foldCount: {
    marginLeft: '6px',
    color: 'var(--text-muted)', // 阶段A：原 #7d7a92 偏暗
    fontSize: '10px',
    fontWeight: 400,
  },
  foldHint: {
    marginLeft: 'auto',
    color: 'var(--text-muted)', // 阶段A：原 #5a5a72 对深底仅约 2.8:1，不可见
    fontSize: '10px',
    fontWeight: 400,
  },
  foldToggle: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    padding: '7px 10px',
    background: 'rgba(255, 255, 255, 0.03)',
    border: '1px solid var(--panel-border)',
    borderRadius: '6px',
    fontSize: '12px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    textAlign: 'left',
  },
  cmdRow: {
    paddingTop: '8px',
    borderTop: '1px solid var(--panel-border)',
  },
  cmdLabel: {
    display: 'block',
    color: 'var(--text-muted)', // 阶段A：原 #7d7a92 偏暗
    fontSize: '10px',
    marginBottom: '5px',
  },
  cmdChip: {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: '10px',
    color: 'var(--gold)',
    backgroundColor: 'rgba(200, 168, 90, 0.12)',
    border: '1px solid rgba(200, 168, 90, 0.3)',
    borderRadius: '4px',
    padding: '2px 7px',
  },
  cmdCount: {
    marginLeft: '4px',
    color: '#a8874a',
    fontSize: '9px',
  },
}
