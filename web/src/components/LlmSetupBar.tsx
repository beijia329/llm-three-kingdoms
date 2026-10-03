import { useEffect, useMemo, useRef, useState } from 'react'
import type { ResetOptions } from '../hooks/useGame'
import { FACTION_COLORS, FACTIONS } from '../theme'

interface LlmSetupBarProps {
  /** 后端回报的**实际** LLM 生效状态 */
  llmActive: boolean
  /** 请求了 LLM 但被回退时的原因 */
  llmError: string
  /** 后端回报的实际模型 id */
  llmModel?: string
  /** 本局实际参战势力 */
  activeFactions?: string[]
  restarting: boolean
  restartError: string
  thinking: boolean
  /** 等待已持续秒数 */
  thinkingSeconds: number
  onRestart: (options: ResetOptions) => void | Promise<unknown>
}

/** LLM 模式下推荐势力数：3 方 = 原版规格且单回合耗时可接受；12 方会到分钟级 */
const RECOMMENDED_FACTION_COUNT = 3

/** 单势力 LLM 决策的经验耗时（秒），用于「约 N 秒」提示 */
const SECONDS_PER_FACTION = 10

export function LlmSetupBar({
  llmActive,
  llmError,
  llmModel,
  activeFactions,
  restarting,
  restartError,
  thinking,
  thinkingSeconds,
  onRestart,
}: LlmSetupBarProps) {
  const [mode, setMode] = useState<'cli' | 'llm'>('cli')
  const [selected, setSelected] = useState<string[]>([])
  const [expanded, setExpanded] = useState(false)
  const wrapRef = useRef<HTMLDivElement | null>(null)

  // 只在首次拿到后端参战势力时回填一次。
  // 🔴 不能直接依赖 activeFactions（数组）：WS 每次推送 state 都会产生**新数组**，
  //    effect 会随之重跑并把用户手动勾选的结果冲掉（实测点 3 下只留下 1 个）。
  //    所以用 ref 锁住"仅初始化同步"，之后完全交给用户操作。
  const didSyncFactions = useRef(false)
  useEffect(() => {
    if (didSyncFactions.current) return
    if (!activeFactions || activeFactions.length === 0) return
    setSelected(activeFactions)
    didSyncFactions.current = true
  }, [activeFactions])

  // 点外部收起势力选择面板
  useEffect(() => {
    if (!expanded) return
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setExpanded(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [expanded])

  const allFactionIds = useMemo(() => Object.keys(FACTIONS), [])

  const toggleFaction = (fid: string) => {    setSelected((prev) =>
      prev.includes(fid) ? prev.filter((f) => f !== fid) : [...prev, fid],
    )
  }

  // 预计单回合耗时：LLM 按势力数线性放大，CLI 视为瞬时
  const estimateSeconds = mode === 'llm' ? Math.max(1, selected.length) * SECONDS_PER_FACTION : 0

  const busy = restarting || thinking
  const modeLabel = mode === 'llm' ? 'LLM 围观' : 'CLI AI'

  const handleRestart = () => {
    void onRestart({ useLlm: mode === 'llm', factions: selected })
  }

  return (
    <div style={styles.wrap} ref={wrapRef}>
      {/* ---- 降级提示条：静默回退必须可见，不能让用户以为在跑 LLM ---- */}
      {llmError && (
        <div style={styles.degradeBanner} role="alert">
          <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: '6px' }}></i>
          <span style={styles.degradeText}>
            <strong style={{ color: '#e8735a' }}>LLM 未生效</strong>
            ：{llmError}
          </span>
        </div>
      )}

      <div style={styles.bar}>
        {/* 模式选择 */}
        <div style={styles.modeGroup} role="radiogroup" aria-label="AI 模式">
          <button
            style={{
              ...styles.modeBtn,
              ...(mode === 'cli' ? styles.modeBtnActive : {}),
            }}
            onClick={() => setMode('cli')}
            disabled={busy}
            title="规则 AI：瞬间出结果，无决策理由"
          >
            <i className="fa-solid fa-bolt" style={{ marginRight: '4px' }}></i>
            CLI AI
          </button>
          <button
            style={{
              ...styles.modeBtn,
              ...(mode === 'llm' ? styles.modeBtnActive : {}),
            }}
            onClick={() => setMode('llm')}
            disabled={busy}
            title="真实大模型决策：能看到主观意图，但单回合慢"
          >
            <i className="fa-solid fa-brain" style={{ marginRight: '4px' }}></i>
            LLM 围观
          </button>
        </div>

        {/* 参战势力多选 */}
        <div style={styles.factionWrap}>
          <button
            style={styles.factionToggle}
            onClick={() => setExpanded((v) => !v)}
            disabled={busy}
            title="选择参战势力"
          >
            <i className="fa-solid fa-flag" style={{ marginRight: '4px' }}></i>
            {mode === 'llm' ? (
              <>
                参战势力
                <span style={styles.factionCount}>
                  {selected.length > 0 ? `${selected.length} 方` : '未选'}
                </span>
              </>
            ) : (
              <span style={{ color: '#7d7a92' }}>全部 12 方</span>
            )}
            <i
              className={`fa-solid fa-chevron-${expanded ? 'up' : 'down'}`}
              style={{ marginLeft: '5px', fontSize: '9px' }}
            ></i>
          </button>

          {expanded && (
            <div style={styles.dropdown}>
              <div style={styles.dropdownHint}>
                LLM 模式建议 {RECOMMENDED_FACTION_COUNT} 方（单回合约{' '}
                {RECOMMENDED_FACTION_COUNT * SECONDS_PER_FACTION} 秒）；势力越多越慢
                {selected.length > RECOMMENDED_FACTION_COUNT && (
                  <span style={{ color: '#d4a84b' }}>
                    　当前 {selected.length} 方 ≈ {selected.length * SECONDS_PER_FACTION} 秒/回合
                  </span>
                )}
              </div>
              <div style={styles.factionGrid}>
                {allFactionIds.map((fid) => {
                  const on = selected.includes(fid)
                  const color = FACTION_COLORS[fid] || '#888'
                  return (
                    <button
                      key={fid}
                      style={{
                        ...styles.factionChip,
                        borderColor: on ? color : 'rgba(255,255,255,0.12)',
                        background: on ? `${color}33` : 'rgba(255,255,255,0.03)',
                        color: on ? '#e8e0d0' : '#8d8a9c',
                      }}
                      onClick={() => toggleFaction(fid)}
                    >
                      <span style={{ ...styles.chipDot, background: color }} />
                      {FACTIONS[fid]}
                    </button>
                  )
                })}
              </div>
              <div style={styles.dropdownFooter}>
                <button
                  style={styles.linkBtn}
                  onClick={() => setSelected(allFactionIds)}
                >
                  全选 12 方（会很慢）
                </button>
                <button
                  style={styles.linkBtn}
                  onClick={() =>
                    setSelected(['caocao', 'liubei', 'sunjian'])
                  }
                >
                  常用三方
                </button>
                <button
                  style={styles.linkBtn}
                  onClick={() => setSelected([])}
                >
                  清空（= 全部）
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 生效状态徽标：以后端回报为准 */}
        <span
          style={{
            ...styles.statusPill,
            borderColor: llmActive ? 'rgba(90,180,100,0.5)' : 'rgba(255,255,255,0.12)',
            color: llmActive ? '#5ab464' : '#8d8a9c',
          }}
          title={
            llmActive
              ? `本局实际使用真实模型${llmModel ? `：${llmModel}` : ''}`
              : '本局为规则 AI（CLIPlayer），决策面板不会有模型理由'
          }
        >
          <i
            className={`fa-solid ${llmActive ? 'fa-robot' : 'fa-gear'}`}
            style={{ marginRight: '4px', fontSize: '10px' }}
          ></i>
          {llmActive ? '模型在跑' : '规则 AI'}
        </span>

        {/* 重开一局 */}
        <button
          style={{
            ...styles.restartBtn,
            opacity: busy ? 0.6 : 1,
            cursor: busy ? 'not-allowed' : 'pointer',
          }}
          onClick={handleRestart}
          disabled={busy}
          title="按当前模式与参战势力重新开局（会清空当前进度）"
        >
          {restarting ? (
            <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '5px' }}></i>
          ) : (
            <i className="fa-solid fa-rotate-right" style={{ marginRight: '5px' }}></i>
          )}
          {restarting ? '重开中...' : '重开一局'}
        </button>
      </div>

      {/* 长耗时反馈：点了必须看得到 */}
      {thinking && (
        <div style={styles.thinkingBar}>
          <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '7px' }}></i>
          <span>
            {mode === 'llm' || llmActive
              ? `AI 正在思考中（约 ${estimateSeconds || 30} 秒）`
              : '正在推进回合...'}
          </span>
          <span style={styles.thinkingSub}>已等待 {thinkingSeconds}s</span>
        </div>
      )}

      {restartError && (
        <div style={styles.errorBar} role="alert">
          <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '6px' }}></i>
          {restartError}
        </div>
      )}

      <div style={styles.modeHint}>
        当前选择：<span style={{ color: '#d4a84b' }}>{modeLabel}</span>
        {mode === 'llm' && (
          <>
            　{selected.length > 0 ? `${selected.length} 方参战` : '未选势力（= 全部 12 方，会非常慢）'}
            　·　预计 {estimateSeconds} 秒/回合
          </>
        )}
        {mode === 'cli' && '　·　瞬间出结果，无决策理由'}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    position: 'absolute',
    top: '70px',
    left: '12px',
    zIndex: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    maxWidth: '560px',
  },
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '7px 10px',
    background: 'rgba(18, 18, 34, 0.86)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '10px',
    backdropFilter: 'blur(12px)',
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.3)',
  },
  modeGroup: {
    display: 'flex',
    gap: '2px',
    padding: '2px',
    background: 'rgba(255,255,255,0.04)',
    borderRadius: '7px',
  },
  modeBtn: {
    padding: '4px 9px',
    border: 'none',
    background: 'transparent',
    color: '#8d8a9c',
    fontSize: '11px',
    fontFamily: 'inherit',
    borderRadius: '5px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition: 'all 0.15s ease',
  },
  modeBtnActive: {
    background: 'rgba(212, 168, 75, 0.18)',
    color: '#d4a84b',
    fontWeight: 600,
  },
  factionWrap: {
    position: 'relative',
  },
  factionToggle: {
    display: 'flex',
    alignItems: 'center',
    padding: '4px 9px',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: '#b8b3aa',
    fontSize: '11px',
    fontFamily: 'inherit',
    borderRadius: '6px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  factionCount: {
    marginLeft: '5px',
    color: '#d4a84b',
    fontWeight: 600,
  },
  dropdown: {
    position: 'absolute',
    top: '30px',
    left: '0',
    width: '340px',
    padding: '10px',
    background: 'rgba(14, 14, 28, 0.97)',
    border: '1px solid rgba(212, 168, 75, 0.3)',
    borderRadius: '10px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.55)',
    zIndex: 20,
  },
  dropdownHint: {
    fontSize: '10px',
    color: '#8d8a9c',
    lineHeight: '1.5',
    marginBottom: '8px',
  },
  factionGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '5px',
  },
  factionChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 5px',
    border: '1px solid',
    borderRadius: '6px',
    fontSize: '11px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  chipDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  dropdownFooter: {
    display: 'flex',
    gap: '10px',
    marginTop: '9px',
    paddingTop: '8px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
  },
  linkBtn: {
    background: 'none',
    border: 'none',
    color: '#64a0d2',
    fontSize: '10px',
    fontFamily: 'inherit',
    cursor: 'pointer',
    padding: 0,
  },
  statusPill: {
    display: 'flex',
    alignItems: 'center',
    padding: '3px 8px',
    border: '1px solid',
    borderRadius: '20px',
    fontSize: '10px',
    whiteSpace: 'nowrap',
  },
  restartBtn: {
    display: 'flex',
    alignItems: 'center',
    padding: '5px 11px',
    background: 'rgba(212, 168, 75, 0.16)',
    border: '1px solid rgba(212, 168, 75, 0.5)',
    color: '#d4a84b',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'inherit',
    borderRadius: '6px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  thinkingBar: {
    display: 'flex',
    alignItems: 'center',
    padding: '7px 12px',
    background: 'rgba(212, 168, 75, 0.14)',
    border: '1px solid rgba(212, 168, 75, 0.45)',
    borderRadius: '8px',
    color: '#d4a84b',
    fontSize: '12px',
    backdropFilter: 'blur(12px)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
  },
  thinkingSub: {
    color: '#e8e0d0',
    marginLeft: '4px',
    fontVariantNumeric: 'tabular-nums',
  },
  errorBar: {
    display: 'flex',
    alignItems: 'center',
    padding: '6px 11px',
    background: 'rgba(200, 80, 70, 0.18)',
    border: '1px solid rgba(200, 80, 70, 0.55)',
    borderRadius: '8px',
    color: '#e8735a',
    fontSize: '11px',
  },
  degradeBanner: {
    display: 'flex',
    alignItems: 'flex-start',
    padding: '8px 12px',
    background: 'rgba(200, 80, 70, 0.16)',
    border: '1px solid rgba(200, 80, 70, 0.5)',
    borderLeft: '3px solid #c85046',
    borderRadius: '8px',
    color: '#e8e0d0',
    fontSize: '11px',
    lineHeight: '1.5',
    backdropFilter: 'blur(12px)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
  },
  degradeText: {
    flex: 1,
  },
  modeHint: {
    fontSize: '10px',
    color: '#7d7a92',
    paddingLeft: '2px',
  },
}
