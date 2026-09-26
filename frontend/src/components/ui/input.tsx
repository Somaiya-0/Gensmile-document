import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(
        "flex h-11 w-full rounded-xl border border-[#e6ecf4] bg-white px-4 py-3 text-base text-slate-900 shadow-none outline-none transition-[border-color,box-shadow] placeholder:text-[#848d9b] focus-visible:border-[#b5c9ea] focus-visible:ring-4 focus-visible:ring-[#0052cc]/10 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Input }
