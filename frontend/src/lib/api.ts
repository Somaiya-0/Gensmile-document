const DIRECT_API_BASE_URL = "https://api.gensmile.ai/api/v1"

// Auth store registers this so apiRequest can auto-refresh on 401
type TokenRefresher = () => Promise<string | null>
let _tokenRefresher: TokenRefresher | null = null
export function registerTokenRefresher(fn: TokenRefresher) {
  _tokenRefresher = fn
}

class ApiError extends Error {
  detail: unknown
  status: number

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

function getApiBaseUrl() {
  // No server-side rewrite proxy in a Vite SPA — call the backend directly.
  // The backend's CORS allowlist (app/main.py) already covers gensmile.ai and
  // localhost:3000, which is why the Vite dev server is pinned to port 3000.
  // `||` (not `??`) is deliberate: an env var present but left blank on the
  // host (empty string, not unset) must still fall back to the default --
  // otherwise every request silently becomes relative to the current page
  // origin instead of the API (e.g. a 405 posting to www.gensmile.ai/auth/login).
  return import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || DIRECT_API_BASE_URL
}

function getApiOrigin() {
  return new URL(getApiBaseUrl()).origin
}

function resolveApiAssetUrl(path: string | null | undefined) {
  if (!path) {
    return null
  }

  if (/^https?:\/\//i.test(path)) {
    return path
  }

  return new URL(path.startsWith("/") ? path : `/${path}`, `${getApiOrigin()}/`)
    .toString()
}

function buildHeaders(headers: HeadersInit | undefined, hasJsonBody: boolean) {
  const requestHeaders = new Headers(headers)

  if (hasJsonBody && !requestHeaders.has("Content-Type")) {
    requestHeaders.set("Content-Type", "application/json")
  }

  if (!requestHeaders.has("Accept")) {
    requestHeaders.set("Accept", "application/json")
  }

  return requestHeaders
}

function getErrorMessage(detail: unknown) {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail
  }

  if (Array.isArray(detail)) {
    const firstMessage = detail.find(
      (item): item is { msg?: string } =>
        typeof item === "object" && item !== null && "msg" in item
    )

    if (firstMessage?.msg) {
      return firstMessage.msg
    }
  }

  if (typeof detail === "object" && detail !== null && "detail" in detail) {
    return getErrorMessage(detail.detail)
  }

  return "Something went wrong. Please try again."
}

// Reads a fetch Response body safely. Endpoints that reply 204 No Content
// (e.g. DELETE /affiliate/invites/{id}) have no body at all, but some proxy
// layers still label the response as application/json — blindly calling
// response.json() on an empty body throws a SyntaxError, which would surface
// as a false "request failed" error even though the request succeeded.
// Reading as text first and only parsing non-empty JSON bodies avoids that.
async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get("content-type") ?? ""
  const isJson = contentType.includes("application/json")
  const rawText = await response.text()

  if (!rawText) {
    return null
  }

  return isJson ? JSON.parse(rawText) : rawText
}

// Transient failures (a proxy/edge cold start, a dropped connection, a
// momentary 502/503/504 from the gateway) happen most often on the very
// first request of a session and otherwise look identical to a real
// failure — the only difference is that trying again immediately succeeds.
// Retrying here, once, covers that case everywhere apiRequest is used
// instead of requiring every call site to notice and retry itself.
const RETRYABLE_STATUS = new Set([502, 503, 504])
const MAX_ATTEMPTS = 3
const RETRY_DELAY_MS = [300, 900]

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

const DEFAULT_TIMEOUT_MS = 120_000

async function fetchWithTimeout(fullUrl: string, init: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const signal = init.signal
    ? (typeof AbortSignal.any === "function"
        ? AbortSignal.any([init.signal, controller.signal])
        : controller.signal)
    : controller.signal

  try {
    return await fetch(fullUrl, { ...init, signal })
  } catch (err) {
    if ((err as Error).name === "AbortError") {
      if (init.signal?.aborted) {
        throw err
      }
      throw new ApiError("Request timed out. Please try again.", 408, {})
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

async function fetchWithRetry(fullUrl: string, init: RequestInit, isIdempotent: boolean) {
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const isLastAttempt = attempt === MAX_ATTEMPTS
    try {
      const response = await fetchWithTimeout(fullUrl, init)
      // A response we got at all means the request reached the server, so
      // retrying a non-idempotent request from here on risks double-submitting
      // it — only GET/HEAD are retried once we have a real (bad) response.
      if (!isLastAttempt && isIdempotent && RETRYABLE_STATUS.has(response.status)) {
        await sleep(RETRY_DELAY_MS[attempt - 1])
        continue
      }
      return response
    } catch (err) {
      // If error is ApiError with status other than 408/502/503/504, don't retry
      if (err instanceof ApiError && !RETRYABLE_STATUS.has(err.status) && err.status !== 408) {
        throw err
      }
      if (isLastAttempt) throw err
      await sleep(RETRY_DELAY_MS[attempt - 1])
    }
  }
  // Unreachable: the loop always returns or throws on its last attempt.
  throw new ApiError("Request failed. Please try again.", 0, {})
}

async function apiRequest<TResponse>(
  path: string,
  init?: Omit<RequestInit, "body"> & { body?: BodyInit | object | null }
) {
  const hasJsonBody =
    init?.body !== undefined &&
    init.body !== null &&
    !(init.body instanceof FormData) &&
    typeof init.body !== "string" &&
    !(init.body instanceof URLSearchParams)

  const requestBody: BodyInit | undefined = hasJsonBody
    ? JSON.stringify(init?.body)
    : (init?.body as BodyInit | undefined)

  const fullUrl = `${getApiBaseUrl()}${path}`
  const method = (init?.method ?? "GET").toUpperCase()
  const isIdempotent = method === "GET" || method === "HEAD"
  const requestHeaders = buildHeaders(init?.headers, hasJsonBody)
  // Only an authenticated call (one that actually sent a Bearer token) can
  // plausibly be failing because that token expired -- /auth/login and
  // /auth/refresh itself never send one. Without this check, a 401 from
  // either of those (wrong password, no such account, an invalid/stale
  // refresh token) triggers _tokenRefresher(), which calls apiRequest on
  // /auth/refresh again, which 401s again, which calls _tokenRefresher()
  // again... an unbounded loop that never resolves.
  const isAuthenticatedRequest = requestHeaders.has("Authorization")

  const response = await fetchWithRetry(
    fullUrl,
    { ...init, body: requestBody, headers: requestHeaders },
    isIdempotent
  )

  const payload = await parseResponseBody(response)

  if (!response.ok) {
    // Auto-refresh on 401 and retry once
    if (response.status === 401 && isAuthenticatedRequest && _tokenRefresher) {
      const newToken = await _tokenRefresher()
      if (newToken) {
        // Inject the new token into headers and retry
        const retryHeaders = new Headers(requestHeaders)
        retryHeaders.set("Authorization", `Bearer ${newToken}`)
        const retryController = new AbortController()
        const retryTimeout = setTimeout(() => retryController.abort(), 30000)
        const retryResponse = await fetch(fullUrl, {
          ...init,
          body: requestBody,
          headers: retryHeaders,
          signal: retryController.signal,
        }).finally(() => clearTimeout(retryTimeout))
        const retryPayload = await parseResponseBody(retryResponse)
        if (!retryResponse.ok) {
          throw new ApiError(
            getErrorMessage(retryPayload),
            retryResponse.status,
            typeof retryPayload === "string" ? { detail: retryPayload } : retryPayload
          )
        }
        return retryPayload as TResponse
      }
    }
    throw new ApiError(
      getErrorMessage(payload),
      response.status,
      typeof payload === "string" ? { detail: payload } : payload
    )
  }

  return payload as TResponse
}

// For the few callers that must use a raw fetch (binary downloads, multipart
// uploads) and so miss apiRequest's own 401 handling.
async function refreshAccessToken(): Promise<string | null> {
  return _tokenRefresher ? _tokenRefresher() : null
}

function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

function getWsBaseUrl() {
  return getApiBaseUrl().replace(/^http/, "ws")
}

export { ApiError, apiRequest, getApiBaseUrl, getApiOrigin, getWsBaseUrl, isApiError, refreshAccessToken, resolveApiAssetUrl }
