import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { GameState, HexTile, WebSocketMessage } from '../types'

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

/** 单条命令等待上限（秒）。超时则解除按钮禁用并提示，避免命令按钮永久转圈 */
const COMMAND_TIMEOUT_S = 20

/** 命令执行结果（命令按钮的可见反馈；成功/失败都要给用户一个交代） */
export interface CommandResult {
  success: boolean
  description: string
  /** 后端命令 type，如 recruit/develop/attack */
  type: string
  /** 自增序号，供前端判断"这是最新一次结果" */
  seq: number
}

export interface ResetOptions {
  /** true = LLM 围观模式；false = CLI 规则 AI */
  useLlm: boolean
  /** 参战势力 id 列表；空 = 全部 12 方 */
  factions: string[]
  model?: string
  provider?: string
  /** v4.0.1：势力 id → 模型名。用于「不同大模型同台竞技」（大乱斗的核心）。
   *  未列出的势力回退到 model。 */
  factionModels?: Record<string, string>
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
  /** 正在执行的命令（按钮禁用 + 转圈）；null 表示空闲 */
  commandPending: { type: string; label: string } | null
  /** 最近一次命令的执行结果（成功/失败都回显） */
  commandResult: CommandResult | null
  /** 执行一条命令：立即进入 pending，收到 command_result 或超时后解除 */
  runCommand: (command: Record<string, unknown>, label: string) => void
  /** 「下一回合」当前不可用的原因；空串 = 可用。用于把置灰理由写进界面 */
  nextTurnBlockedReason: string
  /** 最近一次「操作被前端拦下」的原因（断网点按钮等），空串 = 无 */
  actionBlockedReason: string
}

/**
 * hex_map 缓存结构。
 *
 * 后端不再每次回传整图：版本未变则不入包，占领回合只回传**增量**。
 * 前端必须持有完整 tiles 与「q,r → 下标」索引，才能在增量到来时打补丁。
 */
interface HexCache {
  version?: string
  width?: number
  height?: number
  tiles?: HexTile[]
  index?: Map<string, number>
}

function cacheFullHex(version: string | undefined, map: GameState['hex_map']): HexCache {
  if (!map) return {}
  const index = new Map<string, number>()
  map.tiles.forEach((t, i) => index.set(`${t.q},${t.r}`, i))
  return { version, width: map.width, height: map.height, tiles: map.tiles, index }
}

/** 把增量补丁应用到 tiles（生成新数组，保证 React 能看到引用变化） */
function applyDeltaToCache(cache: HexCache, delta: NonNullable<GameState['hex_map_delta']>): boolean {
  if (!cache.tiles || !cache.index) return false
  // 基线不匹配（缓存不是 delta 期望的版本）→ 无法安全打补丁
  if (cache.version !== delta.base_version) return false
  const nextTiles = cache.tiles.slice()
  for (const t of delta.tiles) {
    const i = cache.index.get(`${t.q},${t.r}`)
    if (i === undefined) continue
    nextTiles[i] = { ...nextTiles[i], faction: t.faction, owner_city_id: t.owner_city_id }
  }
  cache.tiles = nextTiles
  cache.version = delta.version
  return true
}

function mapFromCache(cache: HexCache): GameState['hex_map'] {
  if (!cache.tiles) return undefined
  return { width: cache.width ?? 0, height: cache.height ?? 0, tiles: cache.tiles }
}

/**
 * 兜底拉取完整 hex_map（后端 `/api/hex_map`）。
 *
 * 正常路径下 WS 会携带整图或增量；本函数只在「缓存缺失」或「增量基线不匹配」
 * 时兜底，保证长时间观战/重连后地图不会停留在过期状态。
 */
async function fetchHexMap(
  setState: Dispatch<SetStateAction<GameState | null>>,
  cacheRef: MutableRefObject<HexCache>,
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/api/hex_map`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as {
      version?: string
      width: number
      height: number
      tiles: HexTile[]
    }
    cacheRef.current = cacheFullHex(data.version, {
      width: data.width, height: data.height, tiles: data.tiles,
    })
    const map = mapFromCache(cacheRef.current)
    setState((prev) => (prev ? { ...prev, hex_map: map, hex_map_version: data.version } : prev))
  } catch (e) {
    console.error('拉取 hex_map 失败（地图将保持上一版本）:', e)
  }
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
  // 命令执行中/结果：城市详情卡的「征兵/发展/出征」按钮据此转圈并回显成败
  const [commandPending, setCommandPending] = useState<{ type: string; label: string } | null>(null)
  const [commandResult, setCommandResult] = useState<CommandResult | null>(null)
  // 🔴 A5：「操作被前端拦下」的原因。断网点「下一回合」时 send() 静默 return，
  // 界面却已经进入"思考中"并锁死 240s（TURN_TIMEOUT_S）——观感是"点了没反应，
  // 还把按钮搞坏了"。改为：拦住并把原因显示出来。
  const [actionBlockedReason, setActionBlockedReason] = useState('')
  const commandSeqRef = useRef(0)

  // hex_map 缓存（性能核心，2026-10-03）：后端整图/增量/空三态，前端据此维护缓存。
  const hexCacheRef = useRef<HexCache>({})

  // 🔴 A5：auto 的最新值镜像。onopen 补发消息要读它 —— 见 onopen 内注释。
  const autoRef = useRef(auto)
  useEffect(() => {
    autoRef.current = auto
  }, [auto])

  const applyIncoming = useCallback((next: GameState) => {
    // 1. 整图（首帧 / 重连 / 跨多版）
    if (next.hex_map) {
      hexCacheRef.current = cacheFullHex(next.hex_map_version, next.hex_map)
      setState(next)
      return
    }
    // 2. 增量（占领回合：只带变化格子）
    if (next.hex_map_delta) {
      const delta = next.hex_map_delta
      if (applyDeltaToCache(hexCacheRef.current, delta)) {
        setState({ ...next, hex_map: mapFromCache(hexCacheRef.current), hex_map_version: delta.version })
        return
      }
      // 基线不匹配 → 落状态并拉整图兜底
      setState(next)
      void fetchHexMap(setState, hexCacheRef)
      return
    }
    // 3. 空：版本未变，复用缓存
    const cached = mapFromCache(hexCacheRef.current)
    if (cached) {
      setState({ ...next, hex_map: cached })
    } else {
      setState(next)
      void fetchHexMap(setState, hexCacheRef)
    }
  }, [])

  useEffect(() => {
    let disposed = false
    let reconnectDelay = 1000
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      if (disposed) return
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectDelay = 1000
        setConnected(true)
        ;(window as any).__gameWS = ws
        // 🔴 A5：重连后必须补发 auto 状态。
        // 后端的 auto_loop 是**连接级局部变量**（api/server.py 的 auto_task），
        // WS 一断就随协程一起没了 —— 新连接里的 auto_task 是 None，
        // 即后端根本没在自动推进。而前端 auto 仍是 true → 界面显示
        //「自动推进中」、「下一回合」被永久禁用，实际一步没走。
        // 这里用**最新的 auto 状态**（autoRef）而不是闭包捕获值：
        // 本 effect 的依赖是 [applyIncoming]，若直接读 auto 会拿到首次挂载时的
        // 快照，之后用户切换 A 键也不会反映到补发消息里。
        const wantAuto = autoRef.current
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'auto', enabled: wantAuto, interval_ms: 800 }))
        }
      }
      // 断线自动重连（指数退避，上限 10s）。此前只置 connected=false，
      // 用户必须手动刷新页面 —— 对「长时间观战」场景等于白屏。
      ws.onclose = () => {
        setConnected(false)
        ;(window as any).__gameWS = null
        if (disposed) return
        reconnectTimer = setTimeout(connect, reconnectDelay)
        reconnectDelay = Math.min(reconnectDelay * 2, 10000)
      }
      ws.onerror = (err) => console.error('WebSocket error:', err)

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data)
          if (msg.type === 'state' && msg.data) {
            const next = msg.data as GameState
            applyIncoming(next)
            // 回合号推进到/超过我们等待的那一回合 → 本回合算完了，解除按钮禁用
            setPendingTurn((pending) =>
              pending !== null && next.turn >= pending ? null : pending,
            )
          } else if (msg.type === 'command_result') {
            // 后端 execute_command 的真实回执：{ success, type, description }
            const r = (msg.data || {}) as {
              success?: boolean
              type?: string
              description?: string
              error?: string
            }
            commandSeqRef.current += 1
            setCommandResult({
              success: r.success === true,
              type: r.type || '',
              description: r.description || r.error || (r.success ? '执行成功' : '执行失败'),
              seq: commandSeqRef.current,
            })
            setCommandPending(null)
          } else if (msg.type === 'event') {
            console.log('[GAME]', msg.text)
          } else if (msg.type === 'auto_stopped') {
            // 🔴 A5：后端主动告知「自动推进真的停了」及其原因。
            // 不置 false 的话：后端已 break、前端 auto 仍为 true →
            // 「下一回合」/「空格」因 auto 恒真被永久禁用，而后端一步没推进。
            setAuto(false)
            setPendingTurn(null)
            const reason = msg.reason === 'game_over'
              ? '对局已结束'
              : (msg.text || '后端已停止自动推进')
            setActionBlockedReason(`自动推进已停止：${reason}`)
            console.log('[GAME] auto_stopped:', msg.reason, msg.text)
          } else if (msg.type === 'error') {
            console.error('[GAME ERROR]', msg.message)
            // 出错也要解锁，否则用户会被永久禁用在"思考中"
            setPendingTurn(null)
            setCommandPending(null)
          }
        } catch (e) {
          console.error('Failed to parse message:', e)
        }
      }
    }

    connect()

    return () => {
      disposed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [applyIncoming])

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

  // 🔴 A5：对局结束 → 自动推进必须复位。
  // 后端的 auto_loop 在 game_over 时会 break 并回 auto_stopped（A5 新增），
  // 但**不能只依赖那一条消息**：断网/重连窗口内它可能收不到。
  // state.game_over 是后端权威状态，收到就无条件复位 auto —— 三方对齐的兜底。
  useEffect(() => {
    if (state?.game_over) setAuto(false)
  }, [state?.game_over])

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
      return true
    }
    return false
  }, [])

  const sendCommand = useCallback((command: Record<string, unknown>) => {
    send({ type: 'command', command })
  }, [send])

  /**
   * 执行一条命令并进入可见的 pending 态。
   *
   * 🔴 为什么不让调用方直接用 sendCommand：命令是**异步**的（后端处理后才回
   * `command_result`），若按钮点了不改任何状态，观感就是"点了没反应"——
   * 正是玩家最恨的那类控件。这里统一切到 pending、禁用按钮、转圈，
   * 收到回执或超时后再解除，并把后端的人类可读 description 回显出来。
   *
   * 🔴 A5：断网时**不能**进入 pending。原实现先 setCommandPending 再 send，
   * 而 send 在 readyState != OPEN 时静默 return → 按钮转圈 20s
   * （COMMAND_TIMEOUT_S）后才报"超时"，观感是"点了没反应还把按钮搞坏了"。
   * 现在改为：拦住 + 显示原因，且**不动** UI 的 pending 状态。
   */
  const runCommand = useCallback((command: Record<string, unknown>, label: string) => {
    if (!connected) {
      setActionBlockedReason(`未连接到后端，「${label}」未发送（正在自动重连，可稍后再试）`)
      return
    }
    setActionBlockedReason('')
    const type = String(command?.type || '')
    setCommandResult(null)
    setCommandPending({ type, label })
    sendCommand(command)
  }, [connected, sendCommand])

  // 命令超时兜底：后端异常/未回执时不能永久转圈
  useEffect(() => {
    if (!commandPending) return
    const t = setTimeout(() => {
      commandSeqRef.current += 1
      setCommandResult({
        success: false,
        type: commandPending.type,
        description: '命令超时未收到后端回执（后端可能繁忙或已断开）',
        seq: commandSeqRef.current,
      })
      setCommandPending(null)
    }, COMMAND_TIMEOUT_S * 1000)
    return () => clearTimeout(t)
  }, [commandPending])

  const stateTurnRef = useRef<number>(1)
  useEffect(() => {
    if (state?.turn) stateTurnRef.current = state.turn
  }, [state?.turn])

  // 回合推进后，上一条命令的回显已过时（资源/守军都变了），清掉避免误导
  useEffect(() => {
    setCommandResult(null)
  }, [state?.turn])

  /**
   * 推进一个回合。
   *
   * 🔴 A5：入口必须检查连接状态。原实现只靠 `send()` 里的
   * `readyState != OPEN → 静默 return`：断网点「下一回合」时，
   * `setPendingTurn` 照样把 UI 切成"思考中"并设 240s（TURN_TIMEOUT_S）超时 ——
   * 消息根本没发出去，按钮却被锁死 4 分钟。现在：拦住 + 显示原因，
   * 且**不动**任何 UI 状态（不清 pending、不进 thinking）。
   */
  const nextTurn = useCallback(() => {
    if (!connected) {
      setActionBlockedReason('未连接到后端，「下一回合」未发送（正在自动重连，可稍后再试）')
      return
    }
    setActionBlockedReason('')
    // 幂等：上一回合还没算完就再点，不发第二条（后端是阻塞串行，会雪上加霜）
    setPendingTurn((pending) => {
      if (pending !== null) return pending
      send({ type: 'next_turn' })
      return stateTurnRef.current + 1
    })
  }, [connected, send])

  const toggleAuto = useCallback(() => {
    const next = !auto
    setAuto(next)
    if (!send({ type: 'auto', enabled: next, interval_ms: 800 }) && next) {
      // 开了但没发出去：界面会显示"自动推进中"而后端没动 —— 必须说清楚。
      // 注意 auto 仍置 true：onopen 会在重连后按当前 auto 补发（A5 要求 2），
      // 用户的意图不丢，这里只负责告知"还没生效"。
      setActionBlockedReason('未连接到后端，自动推进尚未开始（重连成功后将自动恢复）')
    } else {
      setActionBlockedReason('')
    }
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
    // v4.0.1：按势力分配模型（多模型对战）。只传非空项，未指定的由后端回退默认模型。
    if (options.factionModels && Object.keys(options.factionModels).length > 0) {
      payload.faction_models = options.factionModels
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
      // 新一局地图全变 → 重置缓存，避免沿用作废的旧地图
      if (data.hex_map) {
        hexCacheRef.current = cacheFullHex(data.hex_map_version, data.hex_map)
      }
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

  /**
   * 🔴 A5：「下一回合」当前不可用的原因（空串 = 可用）。
   *
   * 纪律：**不做假控件** —— 按钮置灰必须同时写明为什么。
   * 原实现 disabled={auto || thinking} 只有一个光秃秃的 disabled，
   * 界面无法区分"在思考"、"在自动推进"和"已断网"，用户只能靠猜。
   * 顺序按用户最可能关心的问题排：断网 > 思考中 > 自动推进中 > 终局。
   */
  const nextTurnBlockedReason = !connected
    ? '未连接后端'
    : pendingTurn !== null
      ? '正在推进上一回合'
      : auto
        ? '自动推进中（如需手动推进请先停止）'
        : state?.game_over
          ? '对局已结束'
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
    commandPending,
    commandResult,
    runCommand,
    nextTurnBlockedReason,
    actionBlockedReason,
  }), [
    state, connected, auto, sendCommand, nextTurn, toggleAuto, reset,
    restart, restarting, restartError, pendingTurn, thinkingSeconds,
    llmActive, llmError, commandPending, commandResult, runCommand,
    nextTurnBlockedReason, actionBlockedReason,
  ])
}
