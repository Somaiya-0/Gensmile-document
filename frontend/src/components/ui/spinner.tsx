import { motion } from "motion/react"
import { cn } from "@/lib/utils"

export function Spinner({ className, size = 20 }: { className?: string; size?: number }) {
  return (
    <motion.span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block shrink-0 rounded-full border-2 border-current border-t-transparent",
        className
      )}
      style={{ width: size, height: size }}
      animate={{ rotate: 360 }}
      transition={{ duration: 0.7, repeat: Infinity, ease: "linear" }}
    />
  )
}

export function PageLoader({
  label = "Loading…",
  className,
  fullscreen = false,
}: {
  label?: string
  className?: string
  fullscreen?: boolean
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-12 text-sm text-[#64748b]",
        fullscreen && "min-h-screen",
        className
      )}
    >
      <Spinner className="text-[#0052cc]" size={28} />
      <span>{label}</span>
    </motion.div>
  )
}

/**
 * Fades new content in whenever `keyId` changes (e.g. per route). Deliberately
 * does NOT use AnimatePresence/exit animations here: `children` is typically a
 * live, context-reading element (react-router's <Outlet/>), and keeping an
 * "exiting" copy of it mounted during an exit transition re-renders it against
 * the *new* route instead of preserving the old page — it doesn't freeze like a
 * snapshot. A plain key-change forces an immediate, clean unmount/remount
 * instead, which is what makes the entrance animation below safe to rely on.
 */
export function FadeIn({
  children,
  className,
  keyId,
}: {
  children: React.ReactNode
  className?: string
  keyId: string | number
}) {
  return (
    <motion.div
      key={keyId}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
