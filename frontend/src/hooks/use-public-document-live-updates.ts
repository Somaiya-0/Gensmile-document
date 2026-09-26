import { useEffect, useRef } from "react"

import { getWsBaseUrl } from "@/lib/api"

const MAX_RECONNECT_DELAY_MS = 30_000

// Live updates for a public, no-login "share" page (the patient fill-in
// link, the doctor-to-doctor read-only link): calls `onChange` the moment
// the server says THIS ONE document changed -- see
// /patient-document/{fill_token}/ws and
// /doctor-to-doctor/documents/{share_token}/ws on the backend.
//
// No auth handshake here (unlike the doctor-side hook) -- the token already
// in `wsPath` is the credential, same as every other request these pages
// make. Reconnects on its own if the connection drops.
export function usePublicDocumentLiveUpdates(wsPath: string | null, onChange: () => unknown) {
  const onChangeRef = useRef(onChange)
  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  useEffect(() => {
    if (!wsPath) return

    let socket: WebSocket | null = null
    let stopped = false
    let attempt = 0
    let hasConnectedBefore = false
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined

    const scheduleReconnect = () => {
      if (stopped) return
      const delay = Math.min(1_000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS)
      attempt += 1
      reconnectTimer = setTimeout(connect, delay)
    }

    function connect() {
      if (stopped) return
      socket = new WebSocket(`${getWsBaseUrl()}${wsPath}`)

      socket.onmessage = (event) => {
        let message: { type?: string }
        try {
          message = JSON.parse(event.data)
        } catch {
          return
        }
        if (message.type === "ready") {
          attempt = 0
          if (hasConnectedBefore) void onChangeRef.current()
          hasConnectedBefore = true
        } else if (message.type === "document_updated") {
          void onChangeRef.current()
        }
      }

      socket.onclose = (event) => {
        if (event.code === 4404) return // link no longer active -- nothing to retry
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      stopped = true
      clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [wsPath])
}
