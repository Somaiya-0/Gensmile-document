import { useEffect, useRef } from "react"
import { Outlet, useNavigate } from "react-router-dom"
import Swal from "sweetalert2"
import { ChevronDown, LogOut } from "lucide-react"

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PageLoader } from "@/components/ui/spinner"
import { canUseDocuments, NOT_A_DOCTOR_MESSAGE } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

function initials(name: string) {
  return name.split(" ").map((part) => part[0] ?? "").slice(0, 2).join("").toUpperCase()
}

function UserMenu() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const isStaff = (user?.role as string)?.toUpperCase() === "STAFF"
  const displayName = user?.full_name ?? (isStaff ? "Staff" : "Doctor")

  const handleSignOut = async () => {
    await logout()
    navigate("/signin", { replace: true })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-full outline-none transition-colors hover:bg-[#f8fbff] sm:gap-3 sm:px-2 sm:py-1">
        <div className="hidden text-right sm:block">
          <p className="text-sm font-semibold leading-5 text-[#0f172a]">{displayName}</p>
          <p className="text-xs leading-4 text-[#475569]">{isStaff ? "Staff Account" : "Doctor"}</p>
        </div>
        <div className="flex size-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,#dbeafe,#93c5fd)] text-sm font-semibold text-[#0f172a] sm:size-10">
          {initials(displayName)}
        </div>
        <ChevronDown className="hidden size-4 text-[#94a3b8] sm:block" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="truncate text-sm font-semibold text-[#0f172a]">{displayName}</p>
          {user?.email ? <p className="truncate text-xs text-[#6c7787]">{user.email}</p> : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleSignOut} className="cursor-pointer gap-2 text-[#b42318] focus:text-[#b42318]">
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// Signed-in shell for the Documents app: a top bar (logo + profile menu) and
// the page. The session guard mirrors the full GenSmile app's DoctorLayout:
// no token -> sign in; wrong role or unfinished signup -> signed out.
export default function DocumentsLayout() {
  const token = useAuthStore((state) => state.accessToken)
  const hydrated = useAuthStore((state) => state.hydrated)
  const user = useAuthStore((state) => state.user)
  const navigate = useNavigate()
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!hydrated) return
    if (!token) {
      // Short grace period: a token refresh in another tab can briefly leave
      // this one without a token before the new one lands.
      redirectTimerRef.current = setTimeout(() => {
        if (!useAuthStore.getState().accessToken) navigate("/signin", { replace: true })
      }, 800)
      return () => {
        if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current)
      }
    }
  }, [hydrated, token, navigate])

  useEffect(() => {
    if (!hydrated || !token || !user) return
    if (!canUseDocuments(user.role) || !user.onboarding_completed) {
      const message = canUseDocuments(user.role)
        ? "Your signup isn't finished yet -- please complete it before signing in."
        : NOT_A_DOCTOR_MESSAGE
      void useAuthStore.getState().logout()
      Swal.fire({ icon: "error", title: "Can't open Documents", text: message, confirmButtonColor: "#0052cc" })
      navigate("/signin", { replace: true })
    }
  }, [hydrated, token, user, navigate])

  if (!hydrated || !token) return <PageLoader fullscreen />
  // Never render a frame of documents for an account that's about to be
  // signed out by the effect above.
  if (user && (!canUseDocuments(user.role) || !user.onboarding_completed)) return <PageLoader fullscreen />

  return (
    <main className="min-h-screen bg-[#f3f5f7]">
      <header className="sticky top-0 z-30 border-b border-[#e6ecf4]/80 bg-white/90 px-4 py-3 shadow-xs backdrop-blur-md sm:px-6">
        <div className="flex items-center justify-end gap-3">
          <UserMenu />
        </div>
      </header>
      <div className="px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </div>
    </main>
  )
}
