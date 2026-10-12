// src/services/sseService.js
// 受管的 SSE 连接：全应用只允许一条流；断线自动重连（指数退避）；
// 页面关闭时用 sendBeacon 退订；手动 connect() 会先关旧连接，杜绝多路重复消费。

import { ref } from 'vue'

export const sseStatus = ref('idle') // idle | connecting | connected | reconnecting | error

const KEEP_ALIVE_MS = 25000 // < 后端 30s 活跃阈值

let eventSource = null
let keepAliveTimer = null
let reconnectTimer = null
let beaconCleanup = null
let attempt = 0
let clientId = null
let handlers = { onMessage: null, onError: null }

function baseUrl() {
  return import.meta.env.VITE_API_BASE_URL || ''
}

function closeAll() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer)
    keepAliveTimer = null
  }
  if (eventSource) {
    eventSource.onerror = null
    eventSource.close()
    eventSource = null
  }
}

function handlePayload(event) {
  try {
    const data = JSON.parse(event.data)
    handlers.onMessage?.(data)
  } catch (err) {
    console.error('Failed to parse SSE message:', err)
    handlers.onError?.(err)
  }
}

function scheduleReconnect() {
  if (reconnectTimer || eventSource) return
  const delay = Math.min(1000 * 2 ** attempt, 10000)
  attempt += 1
  sseStatus.value = 'reconnecting'
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    subscribe()
  }, delay)
}

// 页面关闭/跳走时退订，避免服务端订阅残留
function installBeaconCleanup() {
  if (beaconCleanup) return
  beaconCleanup = () => {
    const id = clientId || localStorage.getItem('clientId')
    if (id && navigator.sendBeacon) {
      navigator.sendBeacon(`${baseUrl()}/api/v1/unsubscribe/${id}`)
    }
  }
  window.addEventListener('beforeunload', beaconCleanup)
}

// 建立新流前先把旧的彻底关掉（手动刷新订阅 / 重连都会走到这里）
function subscribe() {
  closeAll()
  sseStatus.value = 'connecting'
  installBeaconCleanup()

  fetch(`${baseUrl()}/api/v1/get-client-id`)
    .then((response) => {
      if (!response.ok) throw new Error(`get-client-id HTTP ${response.status}`)
      return response.json()
    })
    .then((data) => {
      clientId = data.client_id
      localStorage.setItem('clientId', clientId)

      const es = new EventSource(`${baseUrl()}/stream?channel=${clientId}`)
      eventSource = es

      es.addEventListener('data', handlePayload)
      es.addEventListener('initial_data', handlePayload)

      es.onopen = async () => {
        attempt = 0
        sseStatus.value = 'connected'
        // 连接建立后通知服务端补发初始数据
        try {
          await fetch(`${baseUrl()}/api/v1/notify-connection`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clientId, type: 'connect' }),
          })
        } catch (err) {
          console.error('Failed to send connect notification:', err)
        }
      }

      es.onerror = () => {
        closeAll() // EventSource 断开后原地重连，指数退避
        scheduleReconnect()
      }

      keepAliveTimer = setInterval(async () => {
        try {
          await fetch(`${baseUrl()}/api/v1/notify-connection`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clientId, type: 'keepalive' }),
          })
        } catch (err) {
          console.error('Keep-alive notification failed:', err)
        }
      }, KEEP_ALIVE_MS)
    })
    .catch((err) => {
      console.error('Failed to establish SSE subscription:', err)
      handlers.onError?.(err)
      sseStatus.value = 'error'
      scheduleReconnect()
    })
}

export function connect({ onMessage, onError } = {}) {
  handlers = {
    onMessage: onMessage || handlers.onMessage,
    onError: onError || handlers.onError,
  }
  attempt = 0
  subscribe()
}
