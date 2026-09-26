import { cn } from "@/lib/utils"

function FormMessage({
  children,
  className,
  tone = "error",
}: {
  children?: string | null
  className?: string
  tone?: "error" | "muted"
}) {
  if (!children) {
    return null
  }

  return (
    <p
      className={cn(
        "text-sm leading-5",
        tone === "error" ? "text-[#c10007]" : "text-[#6c7787]",
        className
      )}
    >
      {children}
    </p>
  )
}

export { FormMessage }
