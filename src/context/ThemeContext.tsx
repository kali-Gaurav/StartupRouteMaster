import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { THEME_ROTATION_ORDER, type ThemeId } from "@/lib/themes/tokens";

const THEME_STORAGE_KEY = "route-master-theme";
const ROTATION_DISABLED_KEY = "route-master-theme-rotation-disabled";
const HOUR_MS = 60 * 60 * 1000;

function getStoredTheme(): ThemeId | null {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    if (v && THEME_ROTATION_ORDER.includes(v as ThemeId)) return v as ThemeId;
  } catch {
    /* ignore */
  }
  return null;
}

function setStoredTheme(id: ThemeId) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}

/** Default: rotation OFF so theme does not change over time. User can enable "Rotate theme hourly" in Navbar. */
function isRotationDisabled(): boolean {
  try {
    const v = localStorage.getItem(ROTATION_DISABLED_KEY);
    return v !== "false"; // true when "true", or when not set (default off)
  } catch {
    return true;
  }
}

function setRotationDisabled(disabled: boolean) {
  try {
    localStorage.setItem(ROTATION_DISABLED_KEY, disabled ? "true" : "false");
  } catch {
    /* ignore */
  }
}

/** Theme index from a base time (e.g. start of day UTC), advancing every hour. */
function themeIndexForTime(now: number, baseTime: number, intervalMs: number): number {
  const elapsed = Math.max(0, now - baseTime);
  const index = Math.floor(elapsed / intervalMs) % THEME_ROTATION_ORDER.length;
  return index;
}

type ThemeContextValue = {
  theme: ThemeId;
  setTheme: (id: ThemeId) => void;
  /** When true, hourly rotation is off (e.g. user picked a theme). */
  rotationDisabled: boolean;
  setRotationDisabled: (disabled: boolean) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const HOUR_MS_NUM = HOUR_MS;
/** In dev, rotate every 15s so you can see all themes; in prod, every hour. */
const ROTATION_INTERVAL_MS =
  typeof import.meta.env !== "undefined" && import.meta.env.DEV ? 15_000 : HOUR_MS_NUM;

const isDev = typeof import.meta.env !== "undefined" && import.meta.env.DEV;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const stored = getStoredTheme();
    if (stored) return stored;
    const rotationOff = isRotationDisabled();
    if (rotationOff) return THEME_ROTATION_ORDER[0];
    const now = Date.now();
    const base = isDev ? 0 : new Date(new Date().toISOString().slice(0, 10)).getTime();
    const idx = themeIndexForTime(now, base, ROTATION_INTERVAL_MS);
    return THEME_ROTATION_ORDER[idx];
  });

  const [rotationDisabled, setRotationDisabledState] = useState(isRotationDisabled);

  const setTheme = useCallback((id: ThemeId) => {
    setThemeState(id);
    setStoredTheme(id);
  }, []);

  const setRotationDisabled = useCallback((disabled: boolean) => {
    setRotationDisabledState(disabled);
    setRotationDisabled(disabled);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (rotationDisabled) return;
    const base = isDev ? 0 : new Date(new Date().toISOString().slice(0, 10)).getTime();
    const update = () => {
      const now = Date.now();
      const idx = themeIndexForTime(now, base, ROTATION_INTERVAL_MS);
      const next = THEME_ROTATION_ORDER[idx];
      setThemeState((prev) => (prev === next ? prev : next));
      setStoredTheme(next);
    };
    update();
    const pollMs = ROTATION_INTERVAL_MS <= 60_000 ? Math.max(1000, Math.floor(ROTATION_INTERVAL_MS / 2)) : 60_000;
    const t = setInterval(update, pollMs);
    return () => clearInterval(t);
  }, [rotationDisabled]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, setTheme, rotationDisabled, setRotationDisabled }),
    [theme, setTheme, rotationDisabled, setRotationDisabled]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
