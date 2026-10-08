import { useEffect, useRef, useState, type ReactNode } from "react"

const EXIT_MS = 180 // keep in sync with .modal-closing in index.css

// Keeps a modal on screen for its closing animation after `show` turns false,
// then unmounts it. Wrap the conditional render site:
//   <ModalExit show={open}>{open && <MyModal />}</ModalExit>
// While closing it re-renders the last children it saw, so the modal looks
// exactly as it did; the .modal-closing class plays the fade-out (see the
// .modal-in rules in index.css).
export function ModalExit({ show, children }: { show: boolean; children: ReactNode }) {
  const [closing, setClosing] = useState(false)
  const wasShown = useRef(show)
  const last = useRef<ReactNode>(children)
  if (show) last.current = children

  useEffect(() => {
    if (show) {
      wasShown.current = true
      setClosing(false)
      return
    }
    if (!wasShown.current) return
    wasShown.current = false
    setClosing(true)
    const t = setTimeout(() => setClosing(false), EXIT_MS)
    return () => clearTimeout(t)
  }, [show])

  // The frame between show turning false and the effect above running would
  // otherwise unmount the modal for a flash -- render the closing copy then too.
  if (!show && !closing && !wasShown.current) return null
  // Same wrapper element open and closing: a different wrapper made React
  // throw the open modal away and remount a fresh copy for the fade-out, so
  // its state reset (spinners, refetches, blank fields) as it closed.
  return <div className={show ? "contents" : "modal-closing contents"}>{show ? children : last.current}</div>
}
