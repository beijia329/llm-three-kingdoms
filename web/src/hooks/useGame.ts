import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { GameState, WebSocketMessage } from '../types'

/**
 * WebSocket 地址：默认**同源**。
 * - 生产态：前端由后端 FastAPI 同源挂载（8000），同源 ws:// 正好命中后端
 * - 开发态：vite dev server (5173) 通过 proxy 把 /ws 转发到 8000，同源同样成立
 * 之前硬编码 ws://localhost:8000，一旦前端被别的端口托管就会连错服务器
 * （状态来自 A 服务器、重开请求却发给 B 服务器）。仍可用 VITE_WS_URL 覆盖。
 */
function resolveWsUrl(): string {
  const override = import.meta.env.VITE_WS_URL
  if (override) return override
  if (typeof window === 'undefined') return 'ws://localhost:8000/ws/game'
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/game`
}

const WS_URL = resolveWsUrl()
/** REST 基址：开发态由 vite proxy 转发 /api；生产态与前端同源（后端 8000 挂载静态产物） */
const API_BASE = import.meta.env.VITE_API_BASE || ''

/** 单回合等待上限（秒）。超过则判定异常并解除按钮禁用，避免永久卡死 */
const TURN_TIMEOUT_S = 240

export interface ResetOptions {
  /** true = LLM 围观模式；false = CLI 规则 AI */
  useLlm: boolean
  /** 参战势力 id 列表；空 = 全部 12 方 */
  factions: string[]
  model?: string
  provider?: string
}

export interface UseGameReturn {
  state: GameState | null
  connected: boolean
  auto: boolean
  sendCommand: (command: Record<string, unknown>) => void
  nextTurn: () => void
  toggleAuto: () => void
  reset: (config?: Record<string, unknown>) => void
  /** POST /api/reset：按新配置重开一局，返回后端给出的完整状态 */
  restart: (options: ResetOptions) => Promise<GameState | null>
  /** 重开一局进行中（按钮禁用 + 转圈） */
  restarting: boolean
  /** 重开一局失败信息 */
  restartError: string
  /** 回合推进中（后端阻塞 27~42s），按钮禁用 + 转圈 */
  thinking: boolean
  /** 等待已持续秒数 */
  thinkingSeconds: number
  /** 本局是否处于 LLM 围观模式（以后端回报的 llm_active 为准，不以前端请求为准） */
  llmActive: boolean
  /** 请求了 LLM 但被静默回退时的原因 */
  llmError: string
}

export function useGame(): UseGameReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [state, setState] = useState<GameState | null>(null)
  const [connected, setConnected] = useState(false)
  const [auto, setAuto] = useState(false)
  const [restarting, setRestarting] = useState(false)
  const [restartError, setRestartError] = useState('')
  // 回合推进中：LLM 单回合 27~42s，必须有明确反馈，否则用户以为按钮坏了
  const [pendingTurn, setPendingTurn] = useState<number | null>(null)
  const [thinkingSeconds, setThinkingSeconds] = useState(0)

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      ;(window as any).__gameWS = ws
    }
    ws.onclose = () => {
      setConnected(false)
      ;(window as any).__gameWS = null
    }
    ws.onerror = (err) => console.error('WebSocket error:', err)

    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data)
        if (msg.type === 'state' && msg.data) {
          const next = msg.data as GameState
          setState(next)
          // 回合号推进到/超过我们等待的那一回合 → 本回合算完了，解除按钮禁用
          setPendingTurn((pending) =>
            pending !== null && next.turn >= pending ? null : pending,
          )
        } else if (msg.type === 'event') {
          console.log('[GAME]', msg.text)
        } else if (msg.type === 'error') {
          console.error('[GAME ERROR]', msg.message)
          // 出错也要解锁，否则用户会被永久禁用在"思考中"
          setPendingTurn(null)
        }
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    }

    return () => {
      ws.close()
    }
  }, [])

  // 等待计时：每秒 +1，供「AI 正在思考中（约 N 秒）」显示
  useEffect(() => {
    if (pendingTurn === null) {
      setThinkingSeconds(0)
      return
    }
    const t = setInterval(() => setThinkingSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [pendingTurn])

  // 兜底超时：后端异常时不能让按钮永久禁用
  useEffect(() => {
    if (pendingTurn === null) return
    const t = setTimeout(() => {
      console.warn('[GAME] 等待回合结果超时，强制解除按钮禁用')
      setPendingTurn(null)
    }, TURN_TIMEOUT_S * 1000)
    return () => clearTimeout(t)
  }, [pendingTurn])

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const sendCommand = useCallback((command: Record<string, unknown>) => {
    send({ type: 'command', command })
  }, [send])

  const stateTurnRef = useRef<number>(1)
  useEffect(() => {
    if (state?.turn) stateTurnRef.current = state.turn
  }, [state?.turn])

  const nextTurn = useCallback(() => {
    // 幂等：上一回合还没算完就再点，不发第二条（后端是阻塞串行，会雪上加霜）
    setPendingTurn((pending) => {
      if (pending !== null) return pending
      send({ type: 'next_turn' })
      return stateTurnRef.current + 1
    })
  }, [send])

  const toggleAuto = useCallback(() => {
    const next = !auto
    setAuto(next)
    send({ type: 'auto', enabled: next, interval_ms: 800 })
  }, [auto, send])

  const reset = useCallback((config?: Record<string, unknown>) => {
    send({ type: 'init', ...(config || {}) })
  }, [send])

  const restart = useCallback(async (options: ResetOptions): Promise<GameState | null> => {
    setRestarting(true)
    setRestartError('')
    // 重开一局前先关掉自动推进：旧的 auto_loop 还挂在旧 manager 上，
    // 不关掉会在新局上继续按 800ms 狂刷回合。
    send({ type: 'auto', enabled: false })
    setAuto(false)
    setPendingTurn(null)

    const payload: Record<string, unknown> = {
      use_llm: options.useLlm,
      model: options.model || 'deepseek-flash',
      provider: options.provider || 'deepseek',
    }
    if (options.factions.length > 0) {
      payload.factions = options.factions
    }

    try {
      const res = await fetch(`${API_BASE}/api/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = (await res.json()) as GameState
      // REST 已返回完整状态，直接落地；WS 后续推送会覆盖为更新后的状态
      setState(data)
      if (data.turn) stateTurnRef.current = data.turn
      return data
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setRestartError(`重开一局失败：${msg}（后端是否在 8000 端口运行？）`)
      return null
    } finally {
      setRestarting(false)
    }
  }, [send])

  // LLM 是否**真的**在跑：只认后端 llm_active，不认前端"我勾了 LLM"
  const llmActive = state?.llm_active === true
  const llmError = state?.llm_requested && !state?.llm_active
    ? (state?.llm_error || '后端已回退为规则 AI（原因未说明）')
    : ''

  return useMemo(() => ({
    state,
    connected,
    auto,
    sendCommand,
    nextTurn,
    toggleAuto,
    reset,
    restart,
    restarting,
    restartError,
    thinking: pendingTurn !== null,
    thinkingSeconds,
    llmActive,
    llmError,
  }), [
    state, connected, auto, sendCommand, nextTurn, toggleAuto, reset,
    restart, restarting, restartError, pendingTurn, thinkingSeconds,
    llmActive, llmError,
  ])
}
