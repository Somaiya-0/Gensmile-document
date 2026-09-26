import { Suspense, useMemo, useState } from "react"

import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Eye, EyeOff } from "lucide-react"

import { AuthPageFrame } from "@/components/auth/auth-page-frame"
import { Button } from "@/components/ui/button"
import { FormMessage } from "@/components/ui/form-message"
import { Input } from "@/components/ui/input"
import { getFieldErrors, resetPasswordSchema } from "@/lib/validation"
import { useAuthStore } from "@/stores/auth-store"

function PasswordValidationIcon() {
  return (
    <div className="flex size-16 items-center justify-center text-[#0052cc]">
      <svg
        viewBox="0 0 64 64"
        aria-hidden="true"
        className="size-16"
        fill="none"
      >
        <rect
          x="16"
          y="8"
          width="28"
          height="18"
          rx="6"
          stroke="currentColor"
          strokeWidth="2.8"
        />
        <path
          d="M23 17h.01M37 17h.01"
          stroke="currentColor"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M48 35.2a12 12 0 1 1-7.35 2.52"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="m45.3 35.54 3.77-.34-.34-3.78"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="m37.4 42.48 3.66 3.66 7.34-7.34"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

function PasswordField({
  error,
  helperText,
  label,
  onChange,
  value,
}: {
  error?: string
  helperText?: string
  label: string
  onChange: (value: string) => void
  value: string
}) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className="flex w-full flex-col gap-1">
      <label className="text-base leading-6 text-slate-600">{label}</label>
      <div className="relative">
        <Input
          type={isVisible ? "text" : "password"}
          value={value}
          aria-invalid={Boolean(error)}
          placeholder="••••••••"
          onChange={(event) => onChange(event.target.value)}
          className={`pr-12 tracking-[0.3em] ${
            error ? "border-[#c10007] focus-visible:border-[#c10007]" : ""
          }`}
        />
        <button
          type="button"
          aria-label={`${isVisible ? "Hide" : "Show"} ${label.toLowerCase()}`}
          onClick={() => setIsVisible((visible) => !visible)}
          className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-slate-400 transition-colors hover:text-slate-500"
        >
          {isVisible ? (
            <EyeOff className="size-5" strokeWidth={1.8} />
          ) : (
            <Eye className="size-5" strokeWidth={1.8} />
          )}
        </button>
      </div>
      <FormMessage>{error}</FormMessage>
      {helperText ? (
        <p className="text-sm leading-5 text-[#6c7787]">{helperText}</p>
      ) : null}
    </div>
  )
}

function ResetPasswordPageContent() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams])
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<
    Partial<Record<"password" | "confirmPassword" | "token", string>>
  >({})
  const error = useAuthStore((state) => state.error)
  const isLoading = useAuthStore((state) => state.isLoading)
  const resetPassword = useAuthStore((state) => state.resetPassword)

  async function handleSubmit() {
    const validation = resetPasswordSchema.safeParse({
      confirmPassword,
      password,
      token,
    })

    if (!validation.success) {
      setFieldErrors(getFieldErrors(validation.error))
      setSuccessMessage(null)
      return
    }

    setFieldErrors({})
    await resetPassword(validation.data)
    setSuccessMessage("Your password has been reset. You can now sign in with your new password.")
    setTimeout(() => {
      navigate("/")
    }, 1200)
  }

  return (
    <AuthPageFrame contentClassName="gap-6">
      <div className="flex w-full flex-col items-center gap-4">
        <div className="flex w-full flex-col items-center gap-2 text-center">
          <PasswordValidationIcon />
          <div className="space-y-1">
            <h1 className="text-2xl font-bold leading-10 text-slate-900 sm:text-[32px]">
              Create new password
            </h1>
            <p className="text-base leading-6 text-slate-600">
              Please enter your new security credentials below.
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
          <PasswordField
            label="Password"
            value={password}
            error={fieldErrors.password}
            onChange={setPassword}
          />
          <PasswordField
            label="Confirm Password"
            value={confirmPassword}
            error={fieldErrors.confirmPassword}
            onChange={setConfirmPassword}
          />

          <FormMessage>{fieldErrors.token}</FormMessage>
          <FormMessage>{error}</FormMessage>
          <FormMessage tone="muted">{successMessage}</FormMessage>
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
          {isLoading ? "Resetting..." : "Reset password"}
        </Button>
        <p className="text-center text-base leading-6 text-[#6c7787]">
          Remember your password?{" "}
          <Link
            to="/"
            className="font-semibold text-[#0052cc] transition-colors hover:text-[#003b94]"
          >
            Sign In
          </Link>
        </p>
      </div>
    </AuthPageFrame>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordPageContent />
    </Suspense>
  )
}
