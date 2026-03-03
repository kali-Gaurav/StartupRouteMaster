/**
 * Unified API client with Performance Upgrades:
 * - Brotli/Gzip Compression Headers (Suggestion #10)
 */

import { supabase } from "./supabase";
import {
  normalizeApiError,
  AuthError,
} from "./errors";

const API_BASE = import.meta.env.VITE_API_URL || import.meta.env.RAILWAY_BACKEND_URL || "http://localhost:8000";

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
  init?: RequestInit
): Promise<Response> {
  const url = pathOrUrl.startsWith("http") ? pathOrUrl : ensureSlash(pathOrUrl);
  const { data: { session } } = await supabase.auth.getSession();
  
  const headers = new Headers(init?.headers);
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  
  // Suggestion #10: Explicitly request compressed payloads for mobile efficiency
  headers.set("Accept-Encoding", "br, gzip");

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (cause) {
    throw await normalizeApiError(null, cause);
  }

  if (res.status === 401) {
    on401();
    throw new AuthError("Session expired", 401);
  }
  if (res.status === 429) {
    on429();
  }
  if (!res.ok) throw await normalizeApiError(res);
  return res;
}

function ensureSlash(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const base = API_BASE.replace(/\/$/, "");
  return base + (base.endsWith("/api") ? p : p.startsWith("/api") ? p : `/api${p}`);
}

export function getApiBase(): string {
  return API_BASE.replace(/\/$/, "");
}
