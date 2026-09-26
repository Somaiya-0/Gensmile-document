import { useEffect, useRef } from "react"

// Re-runs `refresh` on an interval while the tab is visible, and right away
// when the user comes back to the tab/window -- so data that changes outside
// this page (e.g. a patient submitting their form from a fill link) shows up
// without a manual reload. Skips a tick if the previous refresh is still in
// flight, and collapses the focus + visibilitychange pair that fire together
// on tab return into a single call.
export function useAutoRefresh(
  refresh: () => unknown,
  { intervalMs = 10_000, enabled = true }: { intervalMs?: number; enabled?: boolean } = {},
) {
  const refreshRef = useRef(refresh)
  useEffect(() => {
    refreshRef.current = refresh
  }, [refresh])

  useEffect(() => {
    if (!enabled) return
    let inFlight = false
    let lastRunAt = 0

    const run = async () => {
      if (document.visibilityState !== "visible" || inFlight) return
      if (Date.now() - lastRunAt < 1_000) return
      inFlight = true
      lastRunAt = Date.now()
      try {
        await refreshRef.current()
      } finally {
        inFlight = false
      }
    }

    const intervalId = window.setInterval(run, intervalMs)
    document.addEventListener("visibilitychange", run)
    window.addEventListener("focus", run)
    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener("visibilitychange", run)
      window.removeEventListener("focus", run)
    }
  }, [intervalMs, enabled])
}
