import { useEffect, useRef } from "react"

import { subscribeToDocumentEvents } from "@/lib/documents-live-updates"

// Calls `onEvent` the moment the server pushes a message of the given
// `type` on the shared Documents live-update connection (see
// lib/documents-live-updates.ts) -- e.g. "document_updated" when a document
// changed, "patients_updated" when a new patient appeared in the "existing
// patient" picker. Multiple components can each call this with a different
// type; they share one WebSocket connection rather than opening one each.
export function useDocumentsLiveUpdates(type: string, onEvent: () => unknown) {
  const onEventRef = useRef(onEvent)
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => subscribeToDocumentEvents(type, () => void onEventRef.current()), [type])
}
