/**
 * Unified API client: base URL, auth header, 401/429 handling, normalized errors, request cancellation.
 * Configure once from AuthProvider.
 *
 * Token strategy: token is read from getToken() (e.g. localStorage). For production,
 * prefer HTTP-only cookies + same-origin API to reduce XSS token theft; if using
 * localStorage, ensure no raw user content is rendered (XSS) and CSP is set.
 */

import { supabase } from "./supabase";
import {
  normalizeApiError,
  AuthError,
  RateLimitError,
} from "./errors";

const API_BASE = import.meta.env.RAILWAY_BACKEND_URL || "http://localhost:8000";

type On401 = () => void;
type On429 = () => void;

let on401: On401 = () => {};
let on429: On429 = () => {};

export function configureApiClient(config: {
  on401: On401;
  on429?: On429;
}) {
  on401 = config.on401;
  if (config.on429) on429 = config.on429;
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
 * Uses Supabase JWT for the Authorization header.
 */
export async function fetchWithAuth(
  pathOrUrl: string,
  init?: FetchWithAuthInit
): Promise<Response> {
  const url = pathOrUrl.startsWith("http") ? pathOrUrl : ensureSlash(pathOrUrl);
  
  // Get the current session from Supabase
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

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

  if (res.status === 401) {
    on401();
    throw new AuthError("Session expired. Please log in again.", 401);
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
