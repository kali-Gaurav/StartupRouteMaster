/**
 * Persist state to localStorage so it survives refresh.
 * Use for filters, sort order, UI preferences (not sensitive data).
 */

import { useState, useEffect, useCallback } from "react";

function safeGet<T>(key: string, defaultValue: T, parse: (s: string) => T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null) return defaultValue;
    return parse(raw);
  } catch {
    return defaultValue;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (e: unknown) {
    console.warn("[usePersistedState] setItem failed:", e instanceof Error ? e.message : 'Unknown error');
  }
}

/**
 * State that syncs to localStorage. Use for non-sensitive preferences (e.g. sortBy, filters).
 * @param key localStorage key (prefix with app prefix if needed, e.g. "rm_sortBy").
 * @param defaultValue initial value when no stored value exists.
 */
export function usePersistedState<T extends string>(
  key: string,
  defaultValue: T
): [T, (value: T) => void] {
  const [state, setState] = useState<T>(() =>
    safeGet(key, defaultValue, (s) => s as T)
  );

  useEffect(() => {
    const stored = safeGet(key, defaultValue, (s) => s as T);
    if (stored !== state) setState(stored);
  }, [key, defaultValue, state]);

  const setValue = useCallback(
    (value: T) => {
      setState(value);
      safeSet(key, value);
    },
    [key]
  );

  return [state, setValue];
}
