/**
 * Design theme identifiers.
 * Add new theme ids here and define their CSS variables in index.css under [data-theme="<id>"].
 */
export type ThemeId = "default" | "premium" | "trust";

export const THEME_IDS: readonly ThemeId[] = ["default", "premium", "trust"] as const;

/** Order used when rotating themes (e.g. hourly). */
export const THEME_ROTATION_ORDER: readonly ThemeId[] = ["default", "premium", "trust"] as const;

export const THEME_LABELS: Record<ThemeId, string> = {
  default: "Warm (default)",
  premium: "Premium (navy)",
  trust: "Trust (charcoal)",
};
