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
  if (show) return <>{children}</>
  if (!closing && !wasShown.current) return null
  return <div className="modal-closing contents">{last.current}</div>
}
