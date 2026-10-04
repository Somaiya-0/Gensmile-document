import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

import { apiRequest, isApiError, registerTokenRefresher } from "@/lib/api"
import { getMyStaffRecord } from "@/lib/api-client"
import type {
  CurrentUserResponse,
  ForgotPasswordResponse,
  ResetPasswordResponse,
  TokenPairResponse,
} from "@/lib/api-types"

type LoginPayload = {
  email: string
  password: string
  rememberMe?: boolean
}

const REMEMBER_ME_KEY = "gensmile-remember-me"
const AUTH_STORAGE_KEY = "gensmile-auth"

// ---------------------------------------------------------------------------
// Auth persistence
// ---------------------------------------------------------------------------
// Auth state is ALWAYS written to localStorage so it survives full-page
// navigations to external origins and back. "Remember me = false" is
// enforced via a login timestamp + max-age check at rehydration time (see
// SESSION_ONLY_MAX_AGE_MS below), not by storage location.
// ---------------------------------------------------------------------------

// When the user does NOT check "remember me", treat the session as valid for
// this long since the last login.
const SESSION_ONLY_MAX_AGE_MS = 12 * 60 * 60 * 1000 // 12 hours
const LOGIN_TS_KEY = "gensmile-login-ts"

const authStorage = {
  getItem: (name: string): string | null => {
    return localStorage.getItem(name) ?? sessionStorage.getItem(name)
  },
  setItem: (name: string, value: string): void => {
    localStorage.setItem(name, value)
    sessionStorage.removeItem(name)
  },
  removeItem: (name: string): void => {
    localStorage.removeItem(name)
    sessionStorage.removeItem(name)
  },
}

type AuthState = {
  accessToken: string | null
  forgotPasswordMessage: string | null
  doctorProfile: CurrentUserResponse["doctor_profile"] | null
  error: string | null
  hydrated: boolean
  isLoading: boolean
  patientProfile: CurrentUserResponse["patient_profile"] | null
  refreshToken: string | null
  resetPasswordPreviewToken: string | null
  resetPasswordPreviewUrl: string | null
  staffPermissions: Record<string, boolean> | null
  user: CurrentUserResponse["user"] | null

  // ── Actions ───────────────────────────────────────────────────────────────
  clearAuth: () => void
  clearResetPreview: () => void
  fetchCurrentUser: () => Promise<CurrentUserResponse | null>
  setUser: (user: CurrentUserResponse["user"]) => void
  forgotPassword: (email: string) => Promise<ForgotPasswordResponse>
  login: (payload: LoginPayload) => Promise<TokenPairResponse>
  logout: () => Promise<void>
  resetPassword: (payload: {
    confirmPassword: string
    password: string
    token: string
  }) => Promise<ResetPasswordResponse>
  acceptInvitation: (payload: {
    confirmPassword: string
    password: string
    token: string
  }) => Promise<TokenPairResponse>
  refreshTokens: () => Promise<TokenPairResponse | null>
  setHydrated: (hydrated: boolean) => void
}

// Push the logged-in session to the native StoreKit bridge (iOS app only).
// Store.shared needs the doctor's user id + access token to attribute purchases
// (appAccountToken) and call /billing/iap/verify. No-op on the web.
function syncNativeSession(userId?: string | null, accessToken?: string | null) {
  if (typeof window === "undefined") return
  const bridge = (window as unknown as { GenSmileIAP?: { setSession: (u: string, t: string) => void } }).GenSmileIAP
  if (bridge && userId && accessToken) {
    try { bridge.setSession(userId, accessToken) } catch { /* ignore */ }
  }
}

function applyAuthState(
  response: TokenPairResponse | CurrentUserResponse,
  set: (partial: Partial<AuthState>) => void
) {
  if ("access_token" in response) {
    set({
      accessToken: response.access_token,
      doctorProfile: null,
      error: null,
      patientProfile: null,
      refreshToken: response.refresh_token,
      user: response.user,
    })
    syncNativeSession(response.user?.id, response.access_token)
    return
  }
  set({
    doctorProfile: response.doctor_profile,
    error: null,
    patientProfile: response.patient_profile,
    user: response.user,
  })
}

let inFlightRefresh: Promise<TokenPairResponse | null> | null = null

// If the persisted auth (shared by every tab) holds a different refresh
// token than this tab's in-memory copy, another tab has already refreshed:
// take its tokens rather than refreshing again with a revoked one.
function adoptTokensFromOtherTab(
  get: () => AuthState,
  set: (partial: Partial<AuthState>) => void
): TokenPairResponse | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const stored = (JSON.parse(raw) as { state?: Partial<AuthState> }).state
    const { user, refreshToken } = get()
    if (
      !stored?.accessToken ||
      !stored.refreshToken ||
      stored.refreshToken === refreshToken ||
      !user ||
      stored.user?.id !== user.id
    ) {
      return null
    }
    set({ accessToken: stored.accessToken, refreshToken: stored.refreshToken })
    syncNativeSession(user.id, stored.accessToken)
    return {
      access_token: stored.accessToken,
      refresh_token: stored.refreshToken,
      token_type: "bearer",
      access_token_expires_at: "",
      refresh_token_expires_at: "",
      user,
    }
  } catch {
    return null
  }
}

async function fetchMe(accessToken: string) {
  return apiRequest<CurrentUserResponse>("/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
    method: "GET",
  })
}

// ── Staff context loader ───────────────────────────────────────────────────
// Called on login and acceptInvitation for STAFF users: loads their
// permissions (e.g. patient_documents) from their StaffMember record.
async function loadStaffContext(token: string, set: (partial: Partial<AuthState>) => void) {
  const member = await getMyStaffRecord(token)
  set({ staffPermissions: member.permissions })
}

const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      forgotPasswordMessage: null,
      doctorProfile: null,
      error: null,
      hydrated: false,
      isLoading: false,
      patientProfile: null,
      refreshToken: null,
      resetPasswordPreviewToken: null,
      resetPasswordPreviewUrl: null,
      staffPermissions: null,
      user: null,

      // ── Auth actions ────────────────────────────────────────────────────

      clearAuth: () => {
        try {
          const b = (window as unknown as { GenSmileIAP?: { setSession: (u: string, t: string) => void } }).GenSmileIAP
          b?.setSession("", "")
        } catch { /* ignore */ }
        // Clear the login timestamp alongside the auth state.
        try {
          localStorage.removeItem(LOGIN_TS_KEY)
        } catch {
          // ignore (SSR / storage unavailable)
        }
        set({
          accessToken: null,
          forgotPasswordMessage: null,
          doctorProfile: null,
          error: null,
          patientProfile: null,
          refreshToken: null,
          resetPasswordPreviewToken: null,
          resetPasswordPreviewUrl: null,
          staffPermissions: null,
          user: null,
        })
      },

      clearResetPreview: () =>
        set({
          forgotPasswordMessage: null,
          resetPasswordPreviewToken: null,
          resetPasswordPreviewUrl: null,
        }),

      fetchCurrentUser: async () => {
        const currentAccessToken = get().accessToken
        if (!currentAccessToken) return null

        set({ error: null, isLoading: true })

        try {
          const response = await fetchMe(currentAccessToken)
          applyAuthState(response, set)
          return response
        } catch (error) {
          if (isApiError(error) && error.status === 401 && get().refreshToken) {
            const refreshedTokens = await get().refreshTokens()
            if (refreshedTokens?.access_token) {
              const retryResponse = await fetchMe(refreshedTokens.access_token)
              applyAuthState(retryResponse, set)
              return retryResponse
            }
            get().clearAuth()
            throw error
          }
          set({
            error:
              error instanceof Error
                ? error.message
                : "Unable to load your account right now.",
          })
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      forgotPassword: async (email) => {
        set({
          error: null,
          forgotPasswordMessage: null,
          isLoading: true,
          resetPasswordPreviewToken: null,
          resetPasswordPreviewUrl: null,
        })
        try {
          const response = await apiRequest<ForgotPasswordResponse>(
            "/auth/forgot-password",
            { body: { email }, method: "POST" },
          )
          set({
            forgotPasswordMessage: response.message,
            resetPasswordPreviewToken: response.reset_token,
            resetPasswordPreviewUrl: response.reset_url,
          })
          return response
        } catch (error) {
          set({
            error:
              error instanceof Error
                ? error.message
                : "Unable to send a password reset link.",
          })
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      login: async (payload) => {
        set({ error: null, forgotPasswordMessage: null, isLoading: true })
        localStorage.setItem(REMEMBER_ME_KEY, payload.rememberMe === false ? "false" : "true")
        // Stamp the login time so a session-only ("remember me = false") login
        // can be expired via max-age on rehydration instead of relying on
        // sessionStorage surviving an external redirect.
        try {
          localStorage.setItem(LOGIN_TS_KEY, String(Date.now()))
        } catch {
          // ignore
        }
        const { rememberMe: _rm, ...apiPayload } = payload

        try {
          const response = await apiRequest<TokenPairResponse>("/auth/login", {
            body: apiPayload,
            method: "POST",
          })

          applyAuthState(response, set)

          const role = (response.user.role as string)?.toUpperCase()

          if (role === "STAFF") {
            // Fire-and-forget — don't block the login response
            loadStaffContext(response.access_token, set)
              .catch((err) => {
                console.error("[Auth] Failed to load staff context:", err)
              })
          }

          return response
        } catch (error) {
          set({
            error:
              error instanceof Error ? error.message : "Unable to sign you in.",
          })
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      logout: async () => {
        const currentRefreshToken = get().refreshToken
        set({ error: null, isLoading: true })

        try {
          if (currentRefreshToken) {
            await apiRequest("/auth/logout", {
              body: { refresh_token: currentRefreshToken },
              method: "POST",
            })
          }
        } finally {
          get().clearAuth()
          set({ isLoading: false })
        }
      },

      resetPassword: async (payload) => {
        set({ error: null, isLoading: true })
        try {
          const response = await apiRequest<ResetPasswordResponse>(
            "/auth/reset-password",
            {
              body: {
                confirm_password: payload.confirmPassword,
                password: payload.password,
                token: payload.token,
              },
              method: "POST",
            },
          )
          set({
            forgotPasswordMessage: null,
            resetPasswordPreviewToken: null,
            resetPasswordPreviewUrl: null,
          })
          return response
        } catch (error) {
          set({
            error:
              error instanceof Error
                ? error.message
                : "Unable to reset your password.",
          })
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      acceptInvitation: async (payload) => {
        set({ error: null, forgotPasswordMessage: null, isLoading: true })

        try {
          const response = await apiRequest<TokenPairResponse>(
            "/auth/accept-invitation",
            {
              body: {
                confirm_password: payload.confirmPassword,
                password: payload.password,
                token: payload.token,
              },
              method: "POST",
            },
          )
          applyAuthState(response, set)

          // Stamp login time for invitation-accept logins too.
          try {
            localStorage.setItem(LOGIN_TS_KEY, String(Date.now()))
          } catch {
            // ignore
          }

          const role = (response.user.role as string)?.toUpperCase()
          if (role === "STAFF") {
            loadStaffContext(response.access_token, set)
              .catch((err) => {
                console.error("[Auth] Failed to load staff context after invitation:", err)
              })
          }

          return response
        } catch (error) {
          set({
            error:
              error instanceof Error
                ? error.message
                : "Unable to complete account setup.",
          })
          throw error
        } finally {
          set({ isLoading: false })
        }
      },

      refreshTokens: () => {
        // Single-flight: the backend rotates refresh tokens (each one is
        // revoked the moment it's used), so two requests that 401 at the same
        // time must share ONE refresh call. Otherwise the second call presents
        // an already-revoked token, gets a 401, and clearAuth() signs the
        // user out even though the first refresh succeeded.
        if (inFlightRefresh) return inFlightRefresh

        inFlightRefresh = (async () => {
          // Another tab may already have rotated the refresh token (it shares
          // localStorage) -- adopt its fresh pair instead of presenting our
          // now-revoked copy.
          const adopted = adoptTokensFromOtherTab(get, set)
          if (adopted) return adopted

          const currentRefreshToken = get().refreshToken
          if (!currentRefreshToken) {
            // Expired access token and nothing to renew it with: sign out
            // (the layouts then send the user to /signin) instead of leaving
            // them on a page where every request quietly 401s.
            if (get().accessToken) get().clearAuth()
            return null
          }

          try {
            const response = await apiRequest<TokenPairResponse>("/auth/refresh", {
              body: { refresh_token: currentRefreshToken },
              method: "POST",
            })
            applyAuthState(response, set)
            return response
          } catch (error) {
            if (isApiError(error) && (error.status === 401 || error.status === 400)) {
              // Lost a race with another tab that rotated the token while
              // this request was in flight -- that's not a real logout.
              const adoptedAfterRace = adoptTokensFromOtherTab(get, set)
              if (adoptedAfterRace) return adoptedAfterRace
              get().clearAuth()
            }
            return null
          }
        })().finally(() => {
          inFlightRefresh = null
        })

        return inFlightRefresh
      },

      setHydrated: (hydrated) => set({ hydrated }),
      setUser: (user) => set({ user }),
    }),
    {
      name: AUTH_STORAGE_KEY,
      onRehydrateStorage: () => (state) => {
        // Enforce session-only expiry for "remember me = false" logins.
        try {
          const remembered = localStorage.getItem(REMEMBER_ME_KEY) !== "false"
          if (!remembered && state?.accessToken) {
            const tsRaw = localStorage.getItem(LOGIN_TS_KEY)
            const ts = tsRaw ? Number(tsRaw) : 0
            const expired =
              !ts || Date.now() - ts > SESSION_ONLY_MAX_AGE_MS
            if (expired) {
              // Session has aged out — clear the rehydrated auth before the
              // app reads it.
              state.clearAuth()
            }
          }
        } catch {
          // ignore (storage unavailable)
        }
        state?.setHydrated(true)
      },
      partialize: (state) => ({
        accessToken: state.accessToken,
        doctorProfile: state.doctorProfile,
        forgotPasswordMessage: state.forgotPasswordMessage,
        patientProfile: state.patientProfile,
        refreshToken: state.refreshToken,
        resetPasswordPreviewToken: state.resetPasswordPreviewToken,
        resetPasswordPreviewUrl: state.resetPasswordPreviewUrl,
        staffPermissions: state.staffPermissions,
        user: state.user,
      }),
      storage: createJSONStorage(() => authStorage),
    },
  ),
)

registerTokenRefresher(async () => {
  const result = await useAuthStore.getState().refreshTokens()
  return result?.access_token ?? null
})

export { useAuthStore }
