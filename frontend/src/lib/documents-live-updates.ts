import { getWsBaseUrl, refreshAccessToken } from "@/lib/api"
import { useAuthStore } from "@/stores/auth-store"

const PING_INTERVAL_MS = 25_000 // keeps proxies/load balancers from idling the socket out
const MAX_RECONNECT_DELAY_MS = 30_000

type Listener = () => void

// One shared WebSocket connection for the whole Documents page, backing
// however many components want to know about live changes (the document
// list, the "existing patient" picker, ...) -- see /patient-documents/ws on
// the backend. Each interested piece of UI subscribes by event type via the
// useDocumentsLiveUpdates hook below; the connection itself opens only while
// at least one component is subscribed, and is shared rather than opening a
// second socket per subscriber.
//
// Events pushed by the server: "document_updated" (a document was created,
// edited, deleted, shared, or a file/logo/fill-in change happened -- from
// this app or the legacy GenSmile app writing the same database) and
// "patients_updated" (a new patient appeared in the "existing patient"
// picker). On reconnect after a drop, every subscribed type is notified to
// catch up on whatever happened while offline, since we don't know which
// kind of change (if any) was missed.
class DocumentsLiveUpdatesManager {
  private socket: WebSocket | null = null
  private connecting = false
  private attempt = 0
  private hasConnectedBefore = false
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined
  private pingTimer: ReturnType<typeof setInterval> | undefined
  private listeners = new Map<string, Set<Listener>>()

  subscribe(type: string, listener: Listener): () => void {
    let set = this.listeners.get(type)
    if (!set) {
      set = new Set()
      this.listeners.set(type, set)
    }
    set.add(listener)
    this.ensureConnected()
    return () => {
      set!.delete(listener)
      if (set!.size === 0) this.listeners.delete(type)
      if (this.listeners.size === 0) this.teardown()
    }
  }

  private ensureConnected() {
    if (this.socket || this.connecting || this.reconnectTimer) return
    if (!useAuthStore.getState().accessToken) return
    this.connect()
  }

  private teardown() {
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = undefined
    clearInterval(this.pingTimer)
    this.connecting = false
    this.socket?.close()
    this.socket = null
  }

  private scheduleReconnect() {
    if (this.listeners.size === 0) return
    const delay = Math.min(1_000 * 2 ** this.attempt, MAX_RECONNECT_DELAY_MS)
    this.attempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined
      this.connect()
    }, delay)
  }

  private connect() {
    this.connecting = true
    const socket = new WebSocket(`${getWsBaseUrl()}/patient-documents/ws`)
    this.socket = socket

    // Authenticate with the first message instead of a ?token= query
    // parameter, which would be written to server access logs.
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", token: useAuthStore.getState().accessToken }))
    }

    socket.onmessage = (event) => {
      let message: { type?: string }
      try {
        message = JSON.parse(event.data)
      } catch {
        return
      }
      if (message.type === "ready") {
        this.connecting = false
        this.attempt = 0
        if (this.hasConnectedBefore) this.notifyAll()
        this.hasConnectedBefore = true
        clearInterval(this.pingTimer)
        this.pingTimer = setInterval(() => {
          if (this.socket?.readyState === WebSocket.OPEN) this.socket.send("ping")
        }, PING_INTERVAL_MS)
      } else if (message.type) {
        this.notify(message.type)
      }
    }

    socket.onclose = (event) => {
      clearInterval(this.pingTimer)
      this.connecting = false
      this.socket = null
      if (this.listeners.size === 0) return
      if (event.code === 4403) return // this account can't use Documents -- nothing to retry
      if (event.code === 4401) {
        // Expired access token: refresh it. A successful refresh's new token
        // is picked up by the next connect() call below; a rejected refresh
        // signs the user out (DocumentsLayout sends them to sign in, and
        // subscribers unmounting tears this down). If the refresh just
        // didn't go through (e.g. offline), retry later either way.
        void refreshAccessToken().finally(() => this.scheduleReconnect())
        return
      }
      this.scheduleReconnect()
    }
  }

  private notify(type: string) {
    this.listeners.get(type)?.forEach((listener) => listener())
  }

  private notifyAll() {
    this.listeners.forEach((set) => set.forEach((listener) => listener()))
  }
}

const manager = new DocumentsLiveUpdatesManager()

export function subscribeToDocumentEvents(type: string, listener: Listener): () => void {
  return manager.subscribe(type, listener)
}
