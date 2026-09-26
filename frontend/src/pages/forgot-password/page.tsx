import { useState } from "react"

import { Link } from "react-router-dom"

import { AuthPageFrame } from "@/components/auth/auth-page-frame"
import { Button } from "@/components/ui/button"
import { FormMessage } from "@/components/ui/form-message"
import { Input } from "@/components/ui/input"
import { forgotPasswordSchema, getFieldErrors } from "@/lib/validation"
import { useAuthStore } from "@/stores/auth-store"

function ResetPasswordIcon() {
  return (
    <div className="flex size-16 items-center justify-center text-[#0052cc]">
      <svg
        viewBox="0 0 64 64"
        aria-hidden="true"
        className="size-16"
        fill="none"
      >
        <path
          d="M47.32 22.54a19.86 19.86 0 1 0 2.16 22.08"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M43.94 14.8h8.52v8.52"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M25.8 27.06v-2.04c0-3.97 2.98-7.22 6.66-7.22s6.66 3.25 6.66 7.22v2.04"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <rect
          x="20.2"
          y="27.06"
          width="24.52"
          height="18.82"
          rx="7.2"
          stroke="currentColor"
          strokeWidth="2.8"
        />
        <path
          d="M32.46 33.2v6.52"
          stroke="currentColor"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [fieldError, setFieldError] = useState<string | null>(null)
  const error = useAuthStore((state) => state.error)
  const forgotPassword = useAuthStore((state) => state.forgotPassword)
  const forgotPasswordMessage = useAuthStore(
    (state) => state.forgotPasswordMessage
  )
  const isLoading = useAuthStore((state) => state.isLoading)

  async function handleSubmit() {
    const validation = forgotPasswordSchema.safeParse({ email })

    if (!validation.success) {
      setFieldError(getFieldErrors(validation.error).email ?? "Enter a valid email address.")
      return
    }

    setFieldError(null)
    try {
      await forgotPassword(validation.data.email)
    } catch {
      // forgotPassword() already recorded a message in the store's `error`
      // field (shown below), e.g. "No account found with this email."
    }
  }

  return (
    <AuthPageFrame contentClassName="gap-6">
      <div className="flex w-full flex-col items-center gap-4">
        <div className="flex w-full flex-col items-center gap-2 text-center">
          <ResetPasswordIcon />
          <div className="space-y-1">
            <h1 className="text-2xl font-bold leading-10 text-slate-900 sm:text-[32px]">
              Forget password
            </h1>
            <p className="text-base leading-6 text-slate-600">
              Enter your email and we&apos;ll send you a reset link
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
              type="email"
              value={email}
              aria-invalid={Boolean(fieldError)}
              placeholder="your.email@example.com"
              onChange={(event) => setEmail(event.target.value)}
              className={
                fieldError
                  ? "border-[#c10007] focus-visible:border-[#c10007]"
                  : ""
              }
            />
          </label>

          <FormMessage>{fieldError}</FormMessage>
          <FormMessage>{error}</FormMessage>
          <FormMessage tone="muted">{forgotPasswordMessage}</FormMessage>
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
          {isLoading ? "Sending..." : "Send Reset Link"}
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
