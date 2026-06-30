import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'

const WebSocketContext = createContext()
const RECONNECT_DELAY = 5000

export function WebSocketContextProvider({ children }) {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef(null)
  const listenersRef = useRef({})
  const reconnectTimerRef = useRef(null)
  const mountedRef = useRef(false)

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null
      const token = localStorage.getItem('auth_token')
      if (token && mountedRef.current) {
        connect()
      }
    }, RECONNECT_DELAY)
  }, [])

  const connect = useCallback(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) return

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) return

    const wsUrl = `ws://${window.location.host}/ws/dashboard/?token=${token}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    const cleanup = () => {
      if (wsRef.current === ws) wsRef.current = null
    }

    ws.onopen = () => {
      if (wsRef.current !== ws) { ws.close(); return }
      setIsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const type = data.type
        if (type && listenersRef.current[type]) {
          listenersRef.current[type].forEach((cb) => cb(data))
        }
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    ws.onclose = () => {
      cleanup()
      setIsConnected(false)
      scheduleReconnect()
    }
  }, [scheduleReconnect])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    mountedRef.current = true
    const token = localStorage.getItem('auth_token')
    if (token) {
      connect()
    }
    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [connect, disconnect])

  const subscribe = useCallback((messageType, callback) => {
    if (!listenersRef.current[messageType]) {
      listenersRef.current[messageType] = []
    }
    listenersRef.current[messageType].push(callback)
    return () => {
      listenersRef.current[messageType] = listenersRef.current[messageType].filter(
        (cb) => cb !== callback
      )
    }
  }, [])

  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return (
    <WebSocketContext.Provider value={{ isConnected, subscribe, sendMessage }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export const useWebSocket = () => useContext(WebSocketContext)
