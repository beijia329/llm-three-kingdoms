import { useEffect, useState } from 'react'
import { EventTicker } from './components/EventTicker'
import { GameMap } from './components/GameMap'
import { Panel } from './components/Panel'
import { TopBar } from './components/TopBar'
import { useGame } from './hooks/useGame'

type TabKey = 'factions' | 'city' | 'generals' | 'log'

function App() {
  const { state, connected, auto, nextTurn, toggleAuto } = useGame()
  const [tab, setTab] = useState<TabKey>('factions')
  const [selectedCityId, setSelectedCityId] = useState<string | null>(null)
  const [selectedFaction, setSelectedFaction] = useState<string | null>(null)

  // 键盘快捷键
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault()
        if (!auto) nextTurn()
      } else if (e.key === 'a' || e.key === 'A') {
        toggleAuto()
      } else if (e.key === '1') {
        setTab('factions')
      } else if (e.key === '2') {
        setTab('city')
      } else if (e.key === '3') {
        setTab('generals')
      } else if (e.key === '4') {
        setTab('log')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [auto, nextTurn, toggleAuto])

  // 选中城市时自动切换到城市标签
  const handleSelectCity = (cityId: string) => {
    setSelectedCityId(cityId)
    setTab('city')
  }

  return (
    <div style={styles.app}>
      <div style={styles.mapArea}>
        <TopBar state={state} connected={connected} />
        <GameMap state={state} onSelectCity={handleSelectCity} />
        <EventTicker events={state?.events || []} />

        {/* 下一回合按钮 */}
        <button
          style={{
            ...styles.nextButton,
            opacity: auto ? 0.5 : 1,
            cursor: auto ? 'not-allowed' : 'pointer',
          }}
          onClick={() => !auto && nextTurn()}
          disabled={auto}
        >
          <div style={{ color: '#d4a84b', fontSize: '16px', fontWeight: 600 }}>下一回合</div>
          <div style={{ color: '#96918a', fontSize: '11px' }}>空格键 / A 自动</div>
        </button>

        {/* 自动模式指示器 */}
        {auto && (
          <div style={styles.autoIndicator}>▶ 自动推进中</div>
        )}
      </div>
      <Panel
        state={state}
        tab={tab}
        setTab={setTab}
        selectedCityId={selectedCityId}
        selectedFaction={selectedFaction}
        setSelectedFaction={setSelectedFaction}
      />
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    width: '100vw',
    height: '100vh',
    backgroundColor: '#1a1a2e',
  },
  mapArea: {
    position: 'relative',
    flex: 1,
    height: '100%',
    overflow: 'hidden',
  },
  nextButton: {
    position: 'absolute',
    bottom: '12px',
    right: '316px',
    width: '140px',
    height: '42px',
    backgroundColor: 'rgba(18, 18, 34, 0.92)',
    border: '2px solid #d4a84b',
    borderRadius: '6px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '2px',
    zIndex: 10,
  },
  autoIndicator: {
    position: 'absolute',
    bottom: '12px',
    right: '470px',
    padding: '8px 14px',
    backgroundColor: 'rgba(18, 18, 34, 0.92)',
    border: '1px solid #5ab464',
    borderRadius: '6px',
    color: '#5ab464',
    fontSize: '13px',
    zIndex: 10,
  },
}

export default App
