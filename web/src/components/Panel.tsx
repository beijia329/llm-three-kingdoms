import type { GameState } from '../types'
import { FACTION_COLORS, FACTIONS, hexToNumber } from '../utils/colors'

type TabKey = 'factions' | 'city' | 'generals' | 'log'

interface PanelProps {
  state: GameState | null
  tab: TabKey
  setTab: (tab: TabKey) => void
  selectedCityId: string | null
  selectedFaction: string | null
  setSelectedFaction: (fid: string) => void
}

const TABS: { key: TabKey; label: string }[] = [
  { key: 'factions', label: '1.势力' },
  { key: 'city', label: '2.城市' },
  { key: 'generals', label: '3.武将' },
  { key: 'log', label: '4.战报' },
]

export function Panel({ state, tab, setTab, selectedCityId, selectedFaction, setSelectedFaction }: PanelProps) {
  if (!state) return <div style={styles.container}><span style={styles.dim}>加载中...</span></div>

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.key}
            style={{
              ...styles.tab,
              backgroundColor: tab === t.key ? '#3c3c52' : 'transparent',
              color: tab === t.key ? '#d4a84b' : '#96918a',
              borderColor: tab === t.key ? '#5a5a72' : 'transparent',
            }}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div style={styles.content}>
        {tab === 'factions' && <FactionList state={state} selectedFaction={selectedFaction} setSelectedFaction={setSelectedFaction} />}
        {tab === 'city' && <CityDetail state={state} cityId={selectedCityId} />}
        {tab === 'generals' && <GeneralList state={state} />}
        {tab === 'log' && <EventLog events={state.events} />}
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
    <div>
      <div style={styles.headerRow}>
        <span style={styles.dim}>势力</span>
        <span style={styles.dim}>城</span>
        <span style={styles.dim}>兵</span>
        <span style={styles.dim}>金</span>
      </div>
      {rows.map((row) => {
        const color = hexToNumber(FACTION_COLORS[row.fid] || '#888888')
        const isSelected = selectedFaction === row.fid
        return (
          <div
            key={row.fid}
            style={{
              ...styles.row,
              backgroundColor: isSelected ? 'rgba(212, 168, 75, 0.12)' : 'transparent',
              cursor: 'pointer',
            }}
            onClick={() => setSelectedFaction(row.fid)}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: isSelected ? '#e8e0d0' : '#b8b3aa' }}>
              <span style={{
                width: '12px',
                height: '12px',
                borderRadius: '3px',
                backgroundColor: `#${color.toString(16).padStart(6, '0')}`,
                border: '1px solid rgba(232, 224, 208, 0.4)',
                boxShadow: '0 0 2px rgba(0,0,0,0.5)',
              }} />
              {row.name}
            </span>
            <span style={{ color: '#e8e0d0' }}>{row.cities}</span>
            <span style={{ color: '#96918a' }}>{row.garrison}</span>
            <span style={{ color: '#96918a' }}>{row.gold}</span>
          </div>
        )
      })}
    </div>
  )
}

function CityDetail({ state, cityId }: { state: GameState; cityId: string | null }) {
  if (!cityId) return <span style={styles.dim}>点击地图城市查看详情</span>
  const city = state.cities[cityId]
  if (!city) return <span style={styles.dim}>城市不存在</span>

  const color = hexToNumber(FACTION_COLORS[city.faction] || '#888888')
  const gens = Object.values(state.generals).filter((g) => g.location === city.id)

  return (
    <div>
      <h3 style={{ color: `#${color.toString(16).padStart(6, '0')}`, margin: '0 0 12px' }}>{city.name}</h3>
      <div style={styles.detailGrid}>
        <span style={styles.dim}>势力</span><span>{FACTIONS[city.faction] || city.faction}</span>
        <span style={styles.dim}>等级</span><span>{'★'.repeat(city.level)}</span>
        <span style={styles.dim}>城墙</span><span>{city.wall_hp} / {city.wall_max_hp}</span>
        <span style={styles.dim}>守军</span><span>{city.garrison}</span>
        <span style={styles.dim}>金钱</span><span>{city.gold}</span>
        <span style={styles.dim}>粮草</span><span>{city.food}</span>
        <span style={styles.dim}>人口</span><span>{city.population}</span>
        <span style={styles.dim}>民心</span><span>{city.morale}</span>
      </div>
      {city.is_besieged && <div style={{ color: '#c85046', marginTop: '8px' }}>⚠ 被围困中</div>}
      {gens.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ color: '#d4a84b', marginBottom: '6px' }}>驻守武将</div>
          {gens.map((g) => (
            <div key={g.id} style={{ color: '#96918a', fontSize: '12px' }}>
              {g.name} 统{g.command} 政{g.politics} 武{g.bravery} 智{g.intelligence}
            </div>
          ))}
        </div>
      )}
    </div>
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
    <div>
      {factionOrder.map((fid) => {
        const gens = byFaction[fid]
        if (!gens || gens.length === 0) return null
        const color = hexToNumber(FACTION_COLORS[fid] || '#888888')
        return (
          <div key={fid} style={{ marginBottom: '12px' }}>
            <div style={{ color: `#${color.toString(16).padStart(6, '0')}`, fontWeight: 600 }}>
              ■ {FACTIONS[fid] || fid}
            </div>
            {gens.slice(0, 4).map((g) => (
              <div key={g.id} style={{ color: '#96918a', fontSize: '12px', marginTop: '4px' }}>
                {g.name} 统{g.command} 政{g.politics} 武{g.bravery} 智{g.intelligence} 忠{g.loyalty}
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

function EventLog({ events }: { events: GameState['events'] }) {
  return (
    <div style={styles.logList}>
      {[...events].reverse().map((evt, idx) => (
        <div key={idx} style={styles.logItem}>
          <span style={styles.dim}>第{evt.turn}回合</span>
          <span style={{ color: '#e8e0d0' }}>{evt.text}</span>
        </div>
      ))}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '300px',
    height: '100%',
    backgroundColor: '#2a2a3e',
    borderLeft: '1px solid #3c3c52',
    display: 'flex',
    flexDirection: 'column',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid #3c3c52',
  },
  tab: {
    flex: 1,
    padding: '10px 0',
    border: '1px solid transparent',
    borderBottom: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: '13px',
    fontFamily: 'inherit',
    borderRadius: '4px 4px 0 0',
  },
  content: {
    flex: 1,
    padding: '12px',
    overflowY: 'auto',
  },
  dim: {
    color: '#96918a',
    fontSize: '13px',
  },
  headerRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 1.5fr 1fr',
    gap: '4px',
    fontSize: '12px',
    marginBottom: '6px',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 1.5fr 1fr',
    gap: '4px',
    fontSize: '13px',
    padding: '5px 4px',
    borderRadius: '4px',
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 2fr',
    gap: '8px 12px',
    fontSize: '13px',
    color: '#e8e0d0',
  },
  logList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  logItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    fontSize: '12px',
  },
}
