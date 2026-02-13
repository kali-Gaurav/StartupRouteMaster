import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Mini App / website base URL. Prefer current origin so the app works when served from any domain (avoids ERR_NAME_NOT_RESOLVED for routemaster.ai). */
export const getAppBaseUrl = (): string => {
  const base = import.meta.env.VITE_APP_BASE_URL;
  if (base) return base.replace(/\/$/, "");
  if (typeof window !== "undefined") return window.location.origin;
  return "";
};

/** Allowed paths for safe redirect from Mini App to website (anti-phishing). */
const SAFE_REDIRECT_PATHS = ["/", "/bookings", "/dashboard", "/sos", "/ticket", "/mini-app"];

/**
 * Build a safe URL for "Open in browser" from Mini App. Only allowlisted paths.
 * Use for payment return or opening the full site from Telegram.
 */
export const getSafeRedirectUrl = (path: string = "/"): string => {
  const base = getAppBaseUrl();
  const p = path.startsWith("/") ? path : `/${path}`;
  const allowed = SAFE_REDIRECT_PATHS.some((safe) => p === safe || p.startsWith(`${safe}/`));
  const safePath = allowed ? p : "/";
  return `${base}${safePath}`;
};

/** Backend root-level paths (no /api prefix). Backend mounts these at root (app.py or api/main). */
const ROOT_PATHS = ["/routes", "/fares", "/stations", "/trains", "/chat", "/sos", "/health", "/metrics", "/stats"];
const isRootPath = (p: string) => {
  const pathOnly = p.split("?")[0];
  return ROOT_PATHS.some((r) => pathOnly === r || pathOnly.startsWith(r + "/"));
};

/**
 * Get the Railway Backend API base URL (backend FastAPI).
 * Path: /chat, /health (root) or /user/123/stats (becomes /api/user/...).
 * Development: http://localhost:8000 + path.
 * Production: VITE_RAILWAY_API_URL + path, or /api + path for API routes when same-origin.
 */
export const getRailwayApiUrl = (path: string): string => {
  const p = path.startsWith("/") ? path : `/${path}`;
  const useApiPrefix = !p.startsWith("/api") && !isRootPath(p);
  const apiPath = useApiPrefix ? `/api${p}` : p;
  const base = import.meta.env.VITE_RAILWAY_API_URL;
  if (base) return base.replace(/\/$/, "") + (base.includes("/api") ? p : apiPath);
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return `http://localhost:8000${useApiPrefix ? `/api${p}` : p}`;
  }
  return apiPath;
};
