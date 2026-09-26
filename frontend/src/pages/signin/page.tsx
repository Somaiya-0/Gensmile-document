import { useEffect, useRef, useState } from "react"

import { useNavigate, useSearchParams } from "react-router-dom"
import { Eye, EyeOff, UserRoundCheck } from "lucide-react"

import { AuthPageFrame } from "@/components/auth/auth-page-frame"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { FormMessage } from "@/components/ui/form-message"
import { Input } from "@/components/ui/input"
import { canUseDashboard, destinationForRole, NOT_A_DOCTOR_MESSAGE } from "@/lib/auth-routing"
import { getFieldErrors, loginSchema } from "@/lib/validation"
import { handleEnterFieldNav } from "@/lib/form-enter-nav"
import { useAuthStore } from "@/stores/auth-store"

type LoginFormState = {
  email: string
  password: string
  rememberMe: boolean
}

const initialFormState: LoginFormState = {
  email: "",
  password: "",
  rememberMe: true,
}

// Only ever hand back an internal path (e.g. a doctor-to-doctor share link
// that redirected here to sign in first) -- never an absolute/external URL,
// which an attacker could otherwise use this page to bounce a victim through.
function sanitizeRedirect(target: string | null): string | null {
  if (!target) return null
  if (!target.startsWith("/") || target.startsWith("//")) return null
  return target
}

export default function Home() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirectTarget = sanitizeRedirect(searchParams.get("redirect"))
  const [form, setForm] = useState<LoginFormState>(initialFormState)
  const [errors, setErrors] = useState<Partial<Record<keyof LoginFormState, string>>>(
    {}
  )
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)
  const [incompleteError, setIncompleteError] = useState<string | null>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const accessToken = useAuthStore((state) => state.accessToken)
  const error = useAuthStore((state) => state.error)
  const hydrated = useAuthStore((state) => state.hydrated)
  const isLoading = useAuthStore((state) => state.isLoading)
  const login = useAuthStore((state) => state.login)

  useEffect(() => {
    if (!hydrated) {
      return
    }

    if (accessToken) {
      const user = useAuthStore.getState().user
      // A signup that never finished, or an account that can't use this app,
      // isn't "already logged in" here -- DashboardLayout signs these back
      // out on its own, and without this check the two pages would keep
      // bouncing the user between /signin and /dashboard forever.
      if (user && (!user.onboarding_completed || !canUseDashboard(user.role))) return
      navigate(redirectTarget || destinationForRole(user?.role), { replace: true })
    }
  }, [accessToken, hydrated, navigate, redirectTarget])

  async function handleSubmit() {
    const validation = loginSchema.safeParse(form)

    if (!validation.success) {
      setErrors(getFieldErrors(validation.error))
      return
    }

    setErrors({})
    setIncompleteError(null)
    let response
    try {
      response = await login({ ...validation.data, rememberMe: form.rememberMe })
    } catch {
      // login() already recorded a message in the store's `error` field
      // (shown below) -- just stop here instead of an unhandled rejection.
      return
    }

    if (!response.user.onboarding_completed) {
      void useAuthStore.getState().logout()
      setIncompleteError("Your signup isn't finished yet -- please complete it before signing in.")
      return
    }

    if (!canUseDashboard(response.user.role)) {
      void useAuthStore.getState().logout()
      setIncompleteError(NOT_A_DOCTOR_MESSAGE)
      return
    }

    navigate(redirectTarget || destinationForRole(response.user.role))
  }

  return (
    <AuthPageFrame contentClassName="gap-6">
      <div className="flex w-full flex-col items-center gap-4">
        <div className="flex flex-col items-center gap-2 text-center">
          <UserRoundCheck
            aria-hidden="true"
            className="size-16 text-[#0052cc]"
            strokeWidth={1.8}
          />
          <div className="space-y-1">
            <h1 className="text-2xl font-bold leading-10 text-slate-900 sm:text-[32px]">
              Sign In
            </h1>
            <p className="text-base leading-6 text-slate-600">
              Welcome back! Sign in to continue
            </p>
          </div>
        </div>


        <form
          className="flex w-full flex-col gap-3"
          action="#"
          onSubmit={(event) => {
            event.preventDefault()
            void handleSubmit()
          }}
        >
          <label className="flex flex-col gap-1 text-base leading-6 text-slate-600">
            <span>Email Address</span>
            <Input
              ref={emailRef}
              type="email"
              value={form.email}
              placeholder="your.email@example.com"
              aria-invalid={Boolean(errors.email)}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
              onKeyDown={(event) =>
                handleEnterFieldNav(
                  event,
                  [
                    { ref: emailRef, value: form.email },
                    { ref: passwordRef, value: form.password },
                  ],
                  () => void handleSubmit()
                )
              }
              className={errors.email ? "border-[#c10007] focus-visible:border-[#c10007]" : ""}
            />
            <FormMessage>{errors.email}</FormMessage>
          </label>

          <div className="flex flex-col gap-1">
            <label className="text-base leading-6 text-slate-600">
              Password
            </label>
            <div className="relative">
              <Input
                ref={passwordRef}
                type={isPasswordVisible ? "text" : "password"}
                value={form.password}
                placeholder="••••••••"
                aria-invalid={Boolean(errors.password)}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    password: event.target.value,
                  }))
                }
                onKeyDown={(event) =>
                  handleEnterFieldNav(
                    event,
                    [
                      { ref: emailRef, value: form.email },
                      { ref: passwordRef, value: form.password },
                    ],
                    () => void handleSubmit()
                  )
                }
                className={`pr-12 tracking-[0.3em] ${
                  errors.password
                    ? "border-[#c10007] focus-visible:border-[#c10007]"
                    : ""
                }`}
              />
              <button
                type="button"
                aria-label={isPasswordVisible ? "Hide password" : "Show password"}
                onClick={() => setIsPasswordVisible((visible) => !visible)}
                className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-slate-400 transition-colors hover:text-slate-500"
              >
                {isPasswordVisible ? (
                  <EyeOff className="size-5" strokeWidth={1.8} />
                ) : (
                  <Eye className="size-5" strokeWidth={1.8} />
                )}
              </button>
            </div>
            <FormMessage>{errors.password}</FormMessage>

            <div className="flex flex-col gap-2 pt-1 text-base sm:flex-row sm:items-center">
              <label className="flex cursor-pointer items-center gap-2 text-[#6c7787]">
                <Checkbox
                  checked={form.rememberMe}
                  onCheckedChange={(checked) =>
                    setForm((current) => ({
                      ...current,
                      rememberMe: checked === true,
                    }))
                  }
                />
                <span>Remember me</span>
              </label>
            </div>
          </div>

          <FormMessage>{incompleteError ?? error}</FormMessage>
        </form>
      </div>

      <div className="flex w-full flex-col items-center gap-4">
        <Button
          type="button"
          onClick={() => {
            void handleSubmit()
          }}
          disabled={isLoading}
          className="h-11 w-full rounded-full bg-[#0052cc] text-base font-medium tracking-[-0.01em] text-white hover:bg-[#0047b3] sm:w-[308px]"
        >
          {isLoading ? "Signing In..." : "Continue"}
        </Button>
      </div>
    </AuthPageFrame>
  )
}
