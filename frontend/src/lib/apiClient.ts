/**
 * Unified API client with Performance Upgrades:
 * - Brotli/Gzip Compression Headers (Suggestion #10)
 */

import { supabase } from "./supabase";
import {
  normalizeApiError,
  AuthError,
} from "./errors";

// Task 4: Dynamic API Mapping
// In development, we use relative paths to leverage the Vite proxy (/api -> localhost:8000)
// In production, we can inject a specific API URL via environment variables.
const API_BASE = import.meta.env.PROD 
  ? (import.meta.env.VITE_API_URL || import.meta.env.RAILWAY_BACKEND_URL || "")
  : ""; // Empty string in dev ensures we use the relative proxy path

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

export async function fetchWithAuth(
  pathOrUrl: string,
  init?: RequestInit,
  retryCount: number = 0 // [34.3]
): Promise<Response> {
  // Task 4: Resolve the URL properly
  let url = pathOrUrl;
  if (!url.startsWith("http")) {
    const p = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
    // Ensure we have the /api prefix if the backend expects it
    const apiPath = p.startsWith("/api") ? p : `/api${p}`;
    url = API_BASE ? `${API_BASE.replace(/\/$/, "")}${apiPath}` : apiPath;
  }

  const { data: { session } } = await supabase.auth.getSession();
  let accessToken = session?.access_token || null;
  const legacyToken = localStorage.getItem("supabase.auth.token") || localStorage.getItem("sb-vclitvpgmqzntscvshje-auth-token");
  if (!accessToken && legacyToken) {
    accessToken = legacyToken;
  }

  const headers = new Headers(init?.headers);
  const adminToken = localStorage.getItem("admin_token");

  // Subtask 1.6: Prioritize specialized admin terminal token for /admin paths
  if (url.includes("/admin") && adminToken) {
    headers.set("Authorization", `Bearer ${adminToken}`);
  } else if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  
  // Suggestion #10: Explicitly request compressed payloads for mobile efficiency
  headers.set("Accept-Encoding", "br, gzip");

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (cause) {
    throw await normalizeApiError(null, cause);
  }

  if (res.status === 401 && retryCount < 1) {
    // [34.3] Attempt token refresh ONLY ONCE
    try {
      const { data, error } = await supabase.auth.refreshSession();
      if (error || !data?.session?.access_token) {
        // Refresh failed - user must re-login
        on401();
        throw new AuthError("Session expired", 401);
      }
      
      // Retry with new token and increment counter
      headers.set("Authorization", `Bearer ${data.session.access_token}`);
      return fetchWithAuth(pathOrUrl, init, retryCount + 1);
    } catch {
      on401();
      throw new AuthError("Session expired", 401);
    }
  }
  
  if (res.status === 429) {
    on429();
  }
  if (!res.ok) throw await normalizeApiError(res);
  return res;
}

export interface V3Response<T> {
  status: string;
  success: boolean;
  data: T;
  request_id?: string;
  metadata?: Record<string, any>;
}

export async function v3Fetch<T>(
  pathOrUrl: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetchWithAuth(pathOrUrl, init);
  const json = await res.json() as V3Response<T> | T;
  
  // If it's a V3 response and success is true, return the data
  if (json && typeof json === "object" && "success" in json && "data" in json) {
    if (json.success) {
      return json.data;
    } else {
      // Handle the case where success is false but it's a 200 OK (unlikely with our backend protocol but safe)
      throw new Error((json as any).message || "API operation failed");
    }
  }
  
  // Fallback for legacy V1/V2 responses that aren't wrapped
  return json as T;
}

export function getApiBase(): string {
  return API_BASE.replace(/\/$/, "");
}
