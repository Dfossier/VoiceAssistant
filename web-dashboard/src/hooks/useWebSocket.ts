import { useEffect, useRef, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  onOpen?: () => void
  onClose?: () => void
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export const useWebSocket = (url: string, options: UseWebSocketOptions = {}) => {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<any>(null)
  const ws = useRef<WebSocket | null>(null)
  const reconnectCount = useRef(0)
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null)

  const {
    onOpen,
    onClose,
    onMessage,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options

  const connect = useCallback(() => {
    try {
      // For development, connect directly to backend WebSocket
      // This bypasses Vite proxy issues
      let wsUrl: string
      if (url.startsWith('ws://') || url.startsWith('wss://')) {
        wsUrl = url
      } else if (process.env.NODE_ENV === 'development') {
        // In development, connect directly to backend
        wsUrl = `ws://localhost:8000${url}`
      } else {
        // In production, use relative URL
        wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${url}`
      }
      console.log('Attempting WebSocket connection to:', wsUrl)
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        console.log('WebSocket connected successfully!')
        setIsConnected(true)
        reconnectCount.current = 0
        onOpen?.()
      }

      ws.current.onclose = (event) => {
        console.log('WebSocket closed, code:', event.code, 'reason:', event.reason)
        setIsConnected(false)
        onClose?.()

        // Only reconnect on unexpected closures (not normal close)
        if (event.code !== 1000 && reconnectCount.current < maxReconnectAttempts) {
          console.log(`Attempting reconnect ${reconnectCount.current + 1}/${maxReconnectAttempts}`)
          reconnectTimeout.current = setTimeout(() => {
            reconnectCount.current++
            connect()
          }, reconnectInterval)
        }
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
          onMessage?.(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error)
        console.error('WebSocket readyState:', ws.current?.readyState)
        onError?.(error)
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
    }
  }, [url, onOpen, onClose, onMessage, onError, reconnectInterval, maxReconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current)
    }
    ws.current?.close()
    ws.current = null
    setIsConnected(false)
  }, [])

  const sendMessage = useCallback((data: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    lastMessage,
    sendMessage,
    reconnect: connect,
  }
}