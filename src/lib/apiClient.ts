/**
 * Unified API client: base URL, auth header, 401/429 handling, normalized errors, request cancellation.
 * Configure once from AuthProvider.
 *
 * Token strategy: token is read from getToken() (e.g. localStorage). For production,
 * prefer HTTP-only cookies + same-origin API to reduce XSS token theft; if using
 * localStorage, ensure no raw user content is rendered (XSS) and CSP is set.
 */

import {
  normalizeApiError,
  AuthError,
  RateLimitError,
} from "./errors";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

type GetToken = () => string | null;
type On401 = () => void;
type On429 = () => void;
type OnTokenRefresh = (token: string, refreshToken?: string) => void;

let getToken: GetToken = () => null;
let on401: On401 = () => {};
let on429: On429 = () => {};
let onTokenRefresh: OnTokenRefresh = () => {};

export function configureApiClient(config: {
  getToken: GetToken;
  on401: On401;
  on429?: On429;
  onTokenRefresh?: OnTokenRefresh;
}) {
  getToken = config.getToken;
  on401 = config.on401;
  if (config.on429) on429 = config.on429;
  if (config.onTokenRefresh) onTokenRefresh = config.onTokenRefresh;
}

function ensureSlash(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const base = API_BASE.replace(/\/$/, "");
  return base + (base.endsWith("/api") ? p : p.startsWith("/api") ? p : `/api${p}`);
}

export interface FetchWithAuthInit extends RequestInit {
  /** Pass AbortSignal for request cancellation (e.g. from TanStack Query). */
  signal?: AbortSignal;
}

/**
 * Fetch with base URL, Authorization, 401/429 handling, and normalized errors.
 * Supports request cancellation via init.signal.
 * Throws AuthError, RateLimitError, ValidationError, or NetworkError on failure.
 */
export async function fetchWithAuth(
  pathOrUrl: string,
  init?: FetchWithAuthInit
): Promise<Response> {
  const url = pathOrUrl.startsWith("http") ? pathOrUrl : ensureSlash(pathOrUrl);
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (cause) {
    throw await normalizeApiError(null, cause);
  }

  // helper to attempt refresh and retry once
  const tryRefreshAndRetry = async (): Promise<Response> => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      return res; // nothing to do
    }
    try {
      const base = API_BASE.replace(/\/$/, '');
      const refreshRes = await fetch(base + '/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!refreshRes.ok) {
        return res; // unable to refresh
      }
      const data = await refreshRes.json();
      if (data.token) {
        // update storage and notify
        localStorage.setItem('auth_token', data.token);
        if (data.refresh_token) {
          localStorage.setItem('refresh_token', data.refresh_token);
        }
        onTokenRefresh(data.token, data.refresh_token);
        // retry original request with new token
        headers.set('Authorization', `Bearer ${data.token}`);
        return await fetch(url, { ...init, headers });
      }
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (_error: unknown) {
      // ignore and fall through
    }
    return res;
  };

  if (res.status === 401 && token) {
    // try refreshing once
    const newRes = await tryRefreshAndRetry();
    if (newRes !== res && newRes.status !== 401) {
      res = newRes;
    } else {
      on401();
      throw new AuthError("Session expired. Please log in again.", 401);
    }
  }
  if (res.status === 429) {
    on429();
    const retryAfter = res.headers.get("Retry-After");
    throw new RateLimitError(
      retryAfter ? `Too many requests. Please try again after ${retryAfter} seconds.` : "Too many requests. Please try again in a moment.",
      retryAfter ? parseInt(retryAfter, 10) : undefined
    );
  }
  if (!res.ok) {
    throw await normalizeApiError(res);
  }
  return res;
}

export function getApiBase(): string {
  return API_BASE.replace(/\/$/, "");
}
