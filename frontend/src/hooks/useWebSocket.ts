import { useEffect, useRef, useState, useCallback } from 'react'
import { WSMessage } from '../types'

interface UseWebSocketReturn {
  isConnected: boolean
  lastMessage: WSMessage | null
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  reconnect: () => void
}

/**
 * WebSocket Hook - 处理实时连接和消息分发
 * 自动重连机制：最多5次，指数退避
 */
export const useWebSocket = (url: string = 'ws://localhost:8000/ws'): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('disconnected')

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const MAX_RECONNECT_ATTEMPTS = 5
  const BASE_RECONNECT_DELAY = 1000 // 1秒

  // 清理定时器
  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current)
      heartbeatTimeoutRef.current = null
    }
  }, [])

  // 关闭WebSocket
  const closeWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
    clearTimers()
  }, [clearTimers])

  // 建立连接
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setConnectionStatus('connecting')

    try {
      // 处理开发环境下的代理
      const wsUrl = url.startsWith('ws://') ? url : `ws://${window.location.host}${url}`
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setConnectionStatus('connected')
        reconnectCountRef.current = 0

        // 设置心跳检测
        heartbeatTimeoutRef.current = setTimeout(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'heartbeat', timestamp: new Date().toISOString() }))
          }
        }, 30000)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data)
          setLastMessage(message)
          console.log('WS message received:', message.type)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
        setConnectionStatus('error')
      }

      wsRef.current.onclose = () => {
        console.log('WebSocket closed')
        setIsConnected(false)
        setConnectionStatus('disconnected')
        clearTimers()

        // 尝试重连
        if (reconnectCountRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = BASE_RECONNECT_DELAY * Math.pow(2, reconnectCountRef.current)
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectCountRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)
          reconnectCountRef.current += 1
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          console.error('Max reconnection attempts reached')
          setConnectionStatus('error')
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      setConnectionStatus('error')
    }
  }, [url, clearTimers])

  // 重连方法（供外部调用）
  const reconnect = useCallback(() => {
    closeWebSocket()
    reconnectCountRef.current = 0
    connect()
  }, [closeWebSocket, connect])

  // 初始化连接
  useEffect(() => {
    connect()

    return () => {
      closeWebSocket()
    }
  }, [url, connect, closeWebSocket])

  return {
    isConnected,
    lastMessage,
    connectionStatus,
    reconnect
  }
}
