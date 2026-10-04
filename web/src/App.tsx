import { useEffect, useState } from 'react'
import { AttributionBar } from './components/AttributionBar'
import { CityCard } from './components/CityCard'
import { EventTicker } from './components/EventTicker'
import { GameMap } from './components/GameMap'
import { GameOverOverlay } from './components/GameOverOverlay'
import { LlmSetupBar } from './components/LlmSetupBar'
import { Panel } from './components/Panel'
import { ShortcutHelp } from './components/ShortcutHelp'
import { TooltipProvider, useHintProps } from './components/Tooltip'
import { TopBar } from './components/TopBar'
import { FACTION_COLORS, FACTIONS, GAP_PANEL, NEXT_BTN_W, PANEL_W } from './theme'
import { useGame } from './hooks/useGame'

type TabKey = 'factions' | 'city' | 'generals' | 'diplomacy' | 'data' | 'events' | 'log' | 'reasoning' | 'records'

/** 判断事件目标是否是可输入控件 —— 快捷键必须让位给输入框 */
function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el || !el.tagName) return false
  const tag = el.tagName.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
  if (el.isContentEditable) return true
  return false
}

function App() {
  const {
    state, connected, auto, nextTurn, toggleAuto, restart,
    // thinkingSeconds 仅透传给 LlmSetupBar（等待条在那边渲染，见 M7 注释）
    restarting, restartError, thinking, thinkingSeconds, llmActive, llmError,
    runCommand, commandPending, commandResult,
    // A5：置灰原因必须写进界面 —— 不做假控件
    nextTurnBlockedReason, actionBlockedReason,
  } = useGame()
  const [tab, setTab] = useState<TabKey>('factions')
  const [selectedCityId, setSelectedCityId] = useState<string | null>(null)
  const [selectedFaction, setSelectedFaction] = useState<string | null>(null)
  const [selectedArmyId, setSelectedArmyId] = useState<string | null>(null)
  const [gameOverDismissed, setGameOverDismissed] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  // 新一局开始时复位结算层的关闭状态
  useEffect(() => {
    if (!state?.game_over) setGameOverDismissed(false)
  }, [state?.game_over])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      // [交互修复 2026-10-03] 输入框/下拉聚焦时不再吞键：此前在 <select> 里
      // 按空格/字母/数字会推进回合、切自动、切 tab，完全无法正常输入。
      if (isEditableTarget(e.target)) return

      // 快捷键说明面板 / 全局取消
      if (e.key === '?' || e.key === 'h' || e.key === 'H') {
        e.preventDefault()
        setHelpOpen((v) => !v)
        return
      }
      if (e.key === 'Escape') {
        // 逐层关闭：帮助 → 城池卡 → 军队卡
        setHelpOpen(false)
        setSelectedCityId((cur) => (cur ? null : cur))
        setSelectedArmyId((cur) => (cur ? null : cur))
        return
      }
      // 帮助面板打开时，屏蔽其余玩法快捷键，避免误触推进回合
      if (helpOpen) return

      if (e.code === 'Space') {
        e.preventDefault()
        // 🔴 A5：与按钮同一套判定。原来只有 `if (!auto)`，断网/终局时按空格
        // 仍会调 nextTurn —— nextTurn 内部虽已拦住不再锁死按钮，但这里
        // 静默无反馈会让"空格好像坏了"。统一走 nextTurnBlockedReason。
        if (!nextTurnBlockedReason) nextTurn()
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
      } else if (e.key === '9') {
        setTab('records')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [auto, nextTurn, toggleAuto, helpOpen, nextTurnBlockedReason])

  const handleSelectCity = (cityId: string) => {
    setSelectedCityId(cityId)
    setTab('city')
  }

  const selectedCity = selectedCityId && state ? state.cities[selectedCityId] : null
  const army = selectedArmyId && state ? state.armies[selectedArmyId] : null

  return (
    <TooltipProvider>
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

          <HelpButton onClick={() => setHelpOpen(true)} />

          <GameMap
            state={state}
            onSelectCity={handleSelectCity}
            onSelectArmy={(id) => setSelectedArmyId((cur) => (cur === id ? null : id))}
            selectedArmyId={selectedArmyId}
            selectedCityId={selectedCityId}
          />
          <EventTicker events={state?.events || []} />

          {/* 🔴 A5：disabled 判定纳入 connected，并把「为什么不可用」写进按钮。
              原实现 disabled={auto || thinking} 有两个问题：
                ① 断网时按钮可点 → 点下去 send() 静默 return，UI 却进入"思考中"
                   并锁死 240s（TURN_TIMEOUT_S），观感是"点了没反应还把按钮搞坏"；
                ② 置灰不写理由 —— 用户无法区分"在思考"/"自动推进中"/"已断网"。
              纪律：不做假控件。不可用就要说清楚为什么不可用。 */}
          <button
            style={{
              ...styles.nextButton,
              opacity: nextTurnBlockedReason ? 0.5 : 1,
              cursor: nextTurnBlockedReason ? 'not-allowed' : 'pointer',
            }}
            onClick={() => !nextTurnBlockedReason && nextTurn()}
            disabled={!!nextTurnBlockedReason}
            title={nextTurnBlockedReason || '推进一个回合（快捷键：空格）'}
          >
            <i
              className={`fa-solid ${thinking ? 'fa-spinner fa-spin' : 'fa-forward-step'}`}
              style={{ color: 'var(--gold)', fontSize: '16px' }}
            ></i>
            <div style={{ color: 'var(--gold)', fontSize: '14px', fontWeight: 600 }}>
              {thinking ? '思考中...' : '下一回合'}
            </div>
            <div style={{ color: 'var(--text-2)', fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {nextTurnBlockedReason ? (
                // 不可用时，这行小字改为显示原因（原来恒为「空格 / A」，
                // 与按钮实际是否可用无关，本身也是一种"假控件"）
                <span style={{ color: '#e8a04b' }}>{nextTurnBlockedReason}</span>
              ) : (
                <>
                  <i className="fa-solid fa-keyboard" style={{ fontSize: '9px' }}></i>空格 / A
                </>
              )}
            </div>
          </button>

          {/* 操作被前端拦下时的原因提示（如断网点按钮）。
              静默失败会让用户以为"点了没反应"，所以必须给出可见反馈。 */}
          {actionBlockedReason && (
            <div style={styles.blockedNotice} role="alert">
              <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '6px' }}></i>
              {actionBlockedReason}
            </div>
          )}

          {auto && (
            <div style={styles.autoIndicator}>
              <i className="fa-solid fa-play" style={{ marginRight: '6px' }}></i>
              自动推进中
              <button
                style={styles.stopBtn}
                onClick={() => toggleAuto()}
                title="停止自动推进（快捷键 A）"
              >
                <i className="fa-solid fa-stop" style={{ marginRight: '4px' }}></i>
                停止
              </button>
            </div>
          )}

          {/* [M7 2026-10-04] 原「AI 思考中 · 已等待 Ns（LLM 单回合约 30 秒）」等待条已删除：
              ① 与 LlmSetupBar 的等待条重复（同一 thinking 状态两处渲染，文案还不一样）；
              ② 「约 30 秒」在 CLI 规则 AI 模式下是错的（实测单回合 <120ms）。
              LlmSetupBar 那条已按 llmActive 区分文案，信息更完整，保留它。
              按钮上的「思考中...」+ 转圈图标仍然是即时反馈。 */}

          {/* 城池详情卡（含真实可执行操作） */}
          {state && selectedCity && (
            <CityCard
              state={state}
              city={selectedCity}
              onClose={() => setSelectedCityId(null)}
              onSelectCity={handleSelectCity}
              runCommand={runCommand}
              commandPending={commandPending}
              commandResult={commandResult}
            />
          )}

          {/* 军队详情卡：点地图上的军队后浮现（此前军队完全点不了） */}
          {state && army && (
            <ArmyCard state={state} armyId={selectedArmyId!} onClose={() => setSelectedArmyId(null)} />
          )}

          {state?.game_over && !gameOverDismissed && (
            <GameOverOverlay state={state} onDismiss={() => setGameOverDismissed(true)} />
          )}

          {helpOpen && <ShortcutHelp onClose={() => setHelpOpen(false)} />}
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
    </TooltipProvider>
  )
}

/** 快捷键帮助入口（审计 §4-7：此前快捷键只零散写在按钮小字里） */
function HelpButton({ onClick }: { onClick: () => void }) {
  const hint = useHintProps(() => ({ lines: ['查看全部快捷键（? 或 H）'] }))
  return (
    <button {...hint} style={styles.helpBtn} onClick={onClick} aria-label="快捷键说明">
      <i className="fa-solid fa-keyboard"></i>
      <span style={{ fontSize: '12px', marginLeft: '6px' }}>快捷键</span>
      <kbd style={styles.helpKbd}>?</kbd>
    </button>
  )
}

/** 军队详情卡（从 App 内联抽出，附 hover 说明） */
function ArmyCard({ state, armyId, onClose }: { state: NonNullable<ReturnType<typeof useGame>['state']>; armyId: string; onClose: () => void }) {
  const a = state.armies[armyId]
  if (!a) return null
  const gen = state.generals[a.general_id]
  const color = FACTION_COLORS[a.faction] || '#888'
  const statusLabels: Record<string, string> = {
    marching: '行军中', attacking: '进攻中', besieging: '围城中',
    retreating: '撤退中', defending: '驻守中', idle: '待命',
  }
  return (
    <div style={{ ...styles.armyCard, borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ color: 'var(--text)', fontWeight: 600, fontSize: '13px' }}>
          <i className="fa-solid fa-person-military-rifle" style={{ marginRight: '5px', color }}></i>
          {gen?.name || '未知将领'} 的部队
        </span>
        <button style={styles.armyClose} onClick={onClose} aria-label="关闭" title="关闭（Esc）">
          <i className="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text-2)', lineHeight: 1.7 }}>
        <div>势力：{FACTIONS[a.faction] || a.faction}</div>
        <div>兵力：{a.soldiers.toLocaleString()} · 士气：{a.morale}</div>
        <div>状态：{statusLabels[a.status] || a.status || '—'}</div>
        {(a.from_city || a.to_city) && (
          <div>
            {a.from_city ? `自 ${state.cities[a.from_city]?.name || a.from_city}` : ''}
            {a.to_city ? ` → ${state.cities[a.to_city]?.name || a.to_city}` : ''}
          </div>
        )}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    width: '100vw',
    height: '100vh',
    backgroundColor: 'var(--bg)',
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
    // [M5] 由面板宽度推导（原魔数 318 → 与顶栏/事件流统一为 324）
    right: PANEL_W + GAP_PANEL,
    width: NEXT_BTN_W,
    height: '46px',
    background: 'rgba(20, 32, 40, 0.82)',
    border: '1px solid rgba(200, 168, 90, 0.5)',
    borderRadius: '6px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '2px',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
  },
  autoIndicator: {
    position: 'absolute',
    bottom: '14px',
    // [M5] 紧邻「下一回合」按钮左侧：面板 + 间距 + 按钮宽 + 12 间距
    right: PANEL_W + GAP_PANEL + NEXT_BTN_W + 12,
    padding: '10px 16px',
    background: 'rgba(20, 32, 40, 0.82)',
    border: '1px solid rgba(90, 180, 100, 0.4)',
    borderRadius: '6px',
    color: 'var(--green)',
    fontSize: '13px',
    zIndex: 10,
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
    display: 'flex',
    alignItems: 'center',
  },
  /** [A5] 操作被拦下的原因提示：置于「下一回合」按钮正上方，不遮挡地图主体 */
  blockedNotice: {
    position: 'absolute',
    bottom: '68px',
    right: PANEL_W + GAP_PANEL,
    width: NEXT_BTN_W,
    padding: '7px 10px',
    background: 'rgba(157, 41, 51, 0.92)',
    border: '1px solid rgba(157, 41, 51, 0.6)',
    borderRadius: '6px',
    color: '#f0d5d0',
    fontSize: '11px',
    lineHeight: 1.45,
    zIndex: 11,
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
  },
  /** 自动推进的「停止」按钮（此前只能按 A 键，界面无入口） */
  stopBtn: {
    marginLeft: '10px',
    padding: '4px 10px',
    borderRadius: '6px',
    border: '1px solid rgba(157, 41, 51, 0.55)',
    background: 'rgba(157, 41, 51, 0.16)',
    color: '#e0776d',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    display: 'inline-flex',
    alignItems: 'center',
  },
  /** 快捷键帮助入口按钮 */
  helpBtn: {
    position: 'absolute',
    top: '74px',
    right: '12px',
    padding: '6px 10px',
    background: 'rgba(20, 32, 40, 0.82)',
    border: '1px solid rgba(255, 255, 255, 0.12)',
    borderRadius: '6px',
    color: '#b8b3aa',
    fontSize: '12px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    zIndex: 25,
    display: 'flex',
    alignItems: 'center',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
  },
  helpKbd: {
    marginLeft: '8px', padding: '0 6px', borderRadius: '4px',
    background: 'rgba(200, 168, 90, 0.16)', border: '1px solid rgba(200, 168, 90, 0.4)',
    color: '#e8c877', fontSize: '10px', fontWeight: 600,
  },
  /** 军队详情卡（点地图军队后浮现） */
  armyCard: {
    position: 'absolute',
    top: '116px',
    right: '12px',
    width: '240px',
    padding: '12px',
    background: 'rgba(20, 32, 40, 0.92)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '6px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
    zIndex: 30,
  },
  armyClose: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-2)',
    cursor: 'pointer',
    fontSize: '13px',
    padding: '2px 4px',
  },
}

export default App
