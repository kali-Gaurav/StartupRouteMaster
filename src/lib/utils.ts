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

/**
 * Get the Railway Backend API base URL (backend FastAPI).
 * Development: http://localhost:8000 + path.
 * Production: VITE_RAILWAY_API_URL + path, or /api + path for API routes when same-origin.
 */
export const getRailwayApiUrl = (path: string): string => {
  const p = path.startsWith("/") ? path : `/${path}`;
  // Ensure /api prefix if not already present, except for absolute URLs
  const useApiPrefix = !p.startsWith("/api") && !p.startsWith("http");
  const apiPath = useApiPrefix ? `/api${p}` : p;
  
  const base = import.meta.env.VITE_RAILWAY_API_URL;
  if (base) {
    return base.replace(/\/$/, "") + (base.includes("/api") ? p : apiPath);
  }
  
  if (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
    return `http://localhost:8000${apiPath}`;
  }
  
  return apiPath;
};
