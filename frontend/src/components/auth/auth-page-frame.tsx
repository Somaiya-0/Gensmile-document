import * as React from "react"

import { cn } from "@/lib/utils"

type AuthPageFrameProps = {
  children: React.ReactNode
  contentClassName?: string
  contentWidthClassName?: string
  sectionClassName?: string
}

function AuthPageFrame({
  children,
  contentClassName,
  contentWidthClassName = "max-w-[432px]",
  sectionClassName,
}: AuthPageFrameProps) {
  return (
    <main className="min-h-screen bg-[#f3f5f7] px-4 py-4 sm:px-6 sm:py-6 lg:px-12">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[1312px] flex-col items-center justify-center gap-4">
        <section
          className={cn(
            "flex w-full flex-1 rounded-[24px] border border-[#e6ecf4] bg-white px-5 py-6 shadow-[0_8px_30px_rgba(15,23,42,0.03)] sm:px-8 lg:px-16 lg:py-8",
            sectionClassName
          )}
        >
          <div
            className={cn(
              "mx-auto flex w-full flex-col items-center justify-center",
              contentWidthClassName,
              contentClassName
            )}
          >
            {children}
          </div>
        </section>
      </div>
    </main>
  )
}

export { AuthPageFrame }
