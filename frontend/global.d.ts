declare global {
  interface Window {
    __audioUn?: boolean
    __pendingAudio?: (() => void)[]
  }
}

// init once
if (typeof window !== "undefined") {
  window.__pendingAudio = window.__pendingAudio || []
}
