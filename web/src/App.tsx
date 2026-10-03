import { useEffect, useState } from 'react'
import { AttributionBar } from './components/AttributionBar'
import { EventTicker } from './components/EventTicker'
import { GameMap } from './components/GameMap'
import { LlmSetupBar } from './components/LlmSetupBar'
import { Panel } from './components/Panel'
import { TopBar } from './components/TopBar'
import { useGame } from './hooks/useGame'

type TabKey = 'factions' | 'city' | 'generals' | 'diplomacy' | 'data' | 'events' | 'log' | 'reasoning'

function App() {
  const {
    state, connected, auto, nextTurn, toggleAuto, restart,
    restarting, restartError, thinking, thinkingSeconds, llmActive, llmError,
  } = useGame()
  const [tab, setTab] = useState<TabKey>('factions')
  const [selectedCityId, setSelectedCityId] = useState<string | null>(null)
  const [selectedFaction, setSelectedFaction] = useState<string | null>(null)

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
        setTab('diplomacy')
      } else if (e.key === '5') {
        setTab('data')
      } else if (e.key === '6') {
        setTab('events')
      } else if (e.key === '7') {
        setTab('log')
      } else if (e.key === '8') {
        setTab('reasoning')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [auto, nextTurn, toggleAuto])
  const handleSelectCity = (cityId: string) => {
    setSelectedCityId(cityId)
    setTab('city')
  }

  return (
    <div style={styles.app}>
      <div style={styles.main}>
        <div style={styles.mapArea}>
        <TopBar state={state} connected={connected} />
        <LlmSetupBar
          llmActive={llmActive}
          llmError={llmError}
          llmModel={state?.llm_model}
          activeFactions={state?.llm_factions}
          restarting={restarting}
          restartError={restartError}
          thinking={thinking}
          thinkingSeconds={thinkingSeconds}
          onRestart={restart}
        />
        <GameMap state={state} onSelectCity={handleSelectCity} />
        <EventTicker events={state?.events || []} />

        <button
          style={{
            ...styles.nextButton,
            opacity: auto || thinking ? 0.5 : 1,
            cursor: auto || thinking ? 'not-allowed' : 'pointer',
          }}
          onClick={() => !auto && !thinking && nextTurn()}
          disabled={auto || thinking}
        >
          <i
            className={`fa-solid ${thinking ? 'fa-spinner fa-spin' : 'fa-forward-step'}`}
            style={{ color: '#d4a84b', fontSize: '16px' }}
          ></i>
          <div style={{ color: '#d4a84b', fontSize: '14px', fontWeight: 600 }}>
            {thinking ? '思考中...' : '下一回合'}
          </div>
          <div style={{ color: '#a8a29a', fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <i className="fa-solid fa-keyboard" style={{ fontSize: '9px' }}></i>空格 / A
          </div>
        </button>

        {auto && (
          <div style={styles.autoIndicator}>
            <i className="fa-solid fa-play" style={{ marginRight: '6px' }}></i>
            自动推进中
          </div>
        )}
        </div>
        <Panel
          state={state}
          tab={tab}
          setTab={setTab}
          selectedCityId={selectedCityId}
          selectedFaction={selectedFaction}
          setSelectedFaction={setSelectedFaction}
          onSelectCity={handleSelectCity}
        />
      </div>
      <AttributionBar />
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    width: '100vw',
    height: '100vh',
    backgroundColor: '#1a1a2e',
    fontFamily: '"Noto Sans SC", "PingFang SC", sans-serif',
  },
  main: {
    display: 'flex',
    flex: 1,
    minHeight: 0,
    width: '100%',
  },
  mapArea: {
    position: 'relative',
    flex: 1,
    height: '100%',
    overflow: 'hidden',
  },
  nextButton: {
    position: 'absolute',
    bottom: '14px',
    right: '318px',
    width: '140px',
    height: '46px',
    background: 'rgba(18, 18, 34, 0.82)',
    border: '1px solid rgba(212, 168, 75, 0.5)',
    borderRadius: '10px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '2px',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
    backdropFilter: 'blur(12px)',
  },
  autoIndicator: {
    position: 'absolute',
    bottom: '14px',
    right: '470px',
    padding: '10px 16px',
    background: 'rgba(18, 18, 34, 0.82)',
    border: '1px solid rgba(90, 180, 100, 0.4)',
    borderRadius: '10px',
    color: '#5ab464',
    fontSize: '13px',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
    backdropFilter: 'blur(12px)',
    display: 'flex',
    alignItems: 'center',
  },
}

export default App
