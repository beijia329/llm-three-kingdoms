import { useCallback, useEffect, useRef, useState } from 'react'
import type { GameState, WebSocketMessage } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/game'

export interface UseGameReturn {
  state: GameState | null
  connected: boolean
  auto: boolean
  sendCommand: (command: Record<string, unknown>) => void
  nextTurn: () => void
  toggleAuto: () => void
  reset: (config?: Record<string, unknown>) => void
}

export function useGame(): UseGameReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [state, setState] = useState<GameState | null>(null)
  const [connected, setConnected] = useState(false)
  const [auto, setAuto] = useState(false)

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
          setState(msg.data as GameState)
        } else if (msg.type === 'event') {
          console.log('[GAME]', msg.text)
        } else if (msg.type === 'error') {
          console.error('[GAME ERROR]', msg.message)
        }
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    }

    return () => {
      ws.close()
    }
  }, [])

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const sendCommand = useCallback((command: Record<string, unknown>) => {
    send({ type: 'command', command })
  }, [send])

  const nextTurn = useCallback(() => {
    send({ type: 'next_turn' })
  }, [send])

  const toggleAuto = useCallback(() => {
    const next = !auto
    setAuto(next)
    send({ type: 'auto', enabled: next, interval_ms: 800 })
  }, [auto, send])

  const reset = useCallback((config?: Record<string, unknown>) => {
    send({ type: 'init', ...(config || {}) })
  }, [send])

  return {
    state,
    connected,
    auto,
    sendCommand,
    nextTurn,
    toggleAuto,
    reset,
  }
}
