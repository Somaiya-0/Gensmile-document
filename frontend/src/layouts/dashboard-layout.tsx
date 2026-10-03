import { useEffect, useRef } from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import Swal from "sweetalert2"
import { ChevronDown, FileText, LayoutDashboard, LogOut, Menu, Share2, Stethoscope, UserRound, Users } from "lucide-react"

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PageLoader } from "@/components/ui/spinner"
import { canUseDashboard, isAdmin, NOT_A_DOCTOR_MESSAGE } from "@/lib/auth-routing"
import { useAuthStore } from "@/stores/auth-store"

function initials(name: string) {
  return name.split(" ").map((part) => part[0] ?? "").slice(0, 2).join("").toUpperCase()
}

function UserMenu() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()

  const role = (user?.role as string)?.toUpperCase()
  const roleLabel = role === "STAFF" ? "Staff Account" : role === "ADMIN" ? "Admin" : "Doctor"
  const displayName = user?.full_name ?? roleLabel

  const handleSignOut = async () => {
    await logout()
    navigate("/signin", { replace: true })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-full outline-none transition-colors hover:bg-[#f8fbff] sm:gap-3 sm:px-2 sm:py-1">
        <div className="hidden text-right sm:block">
          <p className="text-sm font-semibold leading-5 text-[#0f172a]">{displayName}</p>
          <p className="text-xs leading-4 text-[#475569]">{roleLabel}</p>
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

type NavItem = { to: string; label: string; icon: typeof Users }

const DOCTOR_NAV_ITEMS: NavItem[] = [
  { to: "/dashboard/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/dashboard/documents", label: "Document", icon: FileText },
  { to: "/dashboard/doctor-to-doctor", label: "Doctor to Doctor", icon: Stethoscope },
  { to: "/dashboard/doctor-to-patient", label: "Doctor to Patient", icon: Users },
]

// Doctors/staff only -- "shared with me" has no meaning for an admin account.
const SHARED_NAV_ITEM: NavItem = { to: "/dashboard/shared", label: "Shared Documents", icon: Share2 }

const ADMIN_NAV_ITEMS: NavItem[] = [
  { to: "/dashboard/doctors", label: "Doctors", icon: UserRound },
]

function useNavItems(): NavItem[] {
  const user = useAuthStore((state) => state.user)
  // Admins see everything doctors/staff see (Overview, Doctor to Doctor,
  // Doctor to Patient) plus their own doctor-management section -- the
  // pages themselves render a read-only, cross-doctor view for admins.
  return isAdmin(user?.role) ? [...DOCTOR_NAV_ITEMS, ...ADMIN_NAV_ITEMS] : [...DOCTOR_NAV_ITEMS, SHARED_NAV_ITEM]
}

function MobileNav() {
  const items = useNavItems()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex size-9 items-center justify-center rounded-lg text-[#475569] outline-none transition-colors hover:bg-[#f8fbff] sm:hidden">
        <Menu className="size-5" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {items.map(({ to, label, icon: Icon }) => (
          <DropdownMenuItem
            key={to}
            onClick={() => navigate(to)}
            className={[
              "cursor-pointer gap-2",
              pathname.startsWith(to) ? "text-[#0052cc]" : "",
            ].join(" ")}
          >
            <Icon className="size-4" /> {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Sidebar() {
  const items = useNavItems()

  return (
    <aside className="hidden w-60 shrink-0 border-r border-[#e6ecf4] bg-white sm:block print:hidden">
      <div className="px-4 py-5">
        <p className="px-2 text-lg font-semibold text-[#0f172a]">ShareTheFile</p>
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-[#eaf1ff] text-[#0052cc]"
                  : "text-[#475569] hover:bg-[#f8fbff] hover:text-[#0f172a]",
              ].join(" ")
            }
          >
            <Icon className="size-4.5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

// Signed-in shell for the Documents app: a left sidebar (Doctor-to-Doctor /
// Doctor-to-Patient for doctors & staff, Doctors for admins), a top bar
// (logo + profile menu), and the page. The session guard mirrors the full
// GenSmile app's DoctorLayout: no token -> sign in; wrong role or unfinished
// signup -> signed out.
export default function DashboardLayout() {
  const token = useAuthStore((state) => state.accessToken)
  const hydrated = useAuthStore((state) => state.hydrated)
  const user = useAuthStore((state) => state.user)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // Come back to this exact page after signing in (e.g. a doctor-to-doctor share link).
  const signinUrl = `/signin?redirect=${encodeURIComponent(pathname)}`
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!hydrated) return
    if (!token) {
      // Short grace period: a token refresh in another tab can briefly leave
      // this one without a token before the new one lands.
      redirectTimerRef.current = setTimeout(() => {
        if (!useAuthStore.getState().accessToken) navigate(signinUrl, { replace: true })
      }, 800)
      return () => {
        if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current)
      }
    }
  }, [hydrated, token, navigate, signinUrl])

  useEffect(() => {
    if (!hydrated || !token || !user) return
    if (!canUseDashboard(user.role) || !user.onboarding_completed) {
      const message = canUseDashboard(user.role)
        ? "Your signup isn't finished yet -- please complete it before signing in."
        : NOT_A_DOCTOR_MESSAGE
      void useAuthStore.getState().logout()
      Swal.fire({ icon: "error", title: "Can't open Documents", text: message, confirmButtonColor: "#0052cc" })
      navigate(signinUrl, { replace: true })
    }
  }, [hydrated, token, user, navigate, signinUrl])

  if (!hydrated || !token) return <PageLoader fullscreen />
  // Never render a frame of the dashboard for an account that's about to be
  // signed out by the effect above.
  if (user && (!canUseDashboard(user.role) || !user.onboarding_completed)) return <PageLoader fullscreen />

  return (
    <div className="flex min-h-screen bg-[#f3f5f7]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-[#e6ecf4]/80 bg-white/90 px-4 py-3 shadow-xs backdrop-blur-md sm:px-6 print:hidden">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 sm:hidden">
              <MobileNav />
              <p className="text-base font-semibold text-[#0f172a]">ShareTheFile</p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <UserMenu />
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
