import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { THEME_ROTATION_ORDER, type ThemeId } from "../lib/themes/tokens";

type ThemeMode = "light" | "dark";

type ThemeContextValue = {
  theme: ThemeId;
  mode: ThemeMode;
  isDarkMode: boolean;
  setTheme: (theme: ThemeId) => void;
  setMode: (mode: ThemeMode) => void;
  toggleMode: () => void;
  rotationDisabled: boolean;
  setRotationDisabled: (disabled: boolean) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Theme ID (e.g., default, premium, trust)
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const saved = localStorage.getItem("rm-theme-id") as ThemeId;
    if (saved && THEME_ROTATION_ORDER.includes(saved)) return saved;
    return "default";
  });

  // Mode (light vs dark)
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem("rm-theme-mode") as ThemeMode;
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  const [rotationDisabled, setRotationDisabledState] = useState(() => {
    const saved = localStorage.getItem("rm-rotation-disabled");
    return saved === "true";
  });

  const setTheme = useCallback((id: ThemeId) => {
    setThemeState(id);
    localStorage.setItem("rm-theme-id", id);
  }, []);

  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    localStorage.setItem("rm-theme-mode", newMode);
  }, []);

  const toggleMode = useCallback(() => {
    setMode(mode === "light" ? "dark" : "light");
  }, [mode, setMode]);

  const setRotationDisabled = useCallback((disabled: boolean) => {
    setRotationDisabledState(disabled);
    localStorage.setItem("rm-rotation-disabled", disabled ? "true" : "false");
  }, []);

  // Handle hourly rotation if not disabled (rotates THEME, not MODE)
  useEffect(() => {
    if (rotationDisabled) return;

    const rotate = () => {
      const hour = new Date().getHours();
      const index = hour % THEME_ROTATION_ORDER.length;
      setThemeState(THEME_ROTATION_ORDER[index]);
    };

    rotate(); 
    const interval = setInterval(rotate, 1000 * 60 * 15);
    return () => clearInterval(interval);
  }, [rotationDisabled]);

  // Apply both theme and mode to document element
  useEffect(() => {
    const root = window.document.documentElement;
    
    // 1. Manage Theme Classes/Data
    THEME_ROTATION_ORDER.forEach((id) => {
      root.classList.remove(`theme-${id}`);
    });
    root.classList.add(`theme-${theme}`);
    root.setAttribute("data-theme", theme);
    
    // 2. Manage Dark Mode Class
    if (mode === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme, mode]);

  const isDarkMode = mode === "dark";

  const value = useMemo<ThemeContextValue>(
    () => ({ 
      theme, 
      mode,
      isDarkMode,
      setTheme, 
      setMode,
      toggleMode,
      rotationDisabled, 
      setRotationDisabled 
    }),
    [theme, mode, isDarkMode, setTheme, setMode, toggleMode, rotationDisabled, setRotationDisabled]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
