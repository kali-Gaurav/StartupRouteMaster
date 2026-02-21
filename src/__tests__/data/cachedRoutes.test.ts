/**
 * Tests for route cache: normalizeDate, getCachedRoutes, getCacheMeta.
 * Dates matter: cache keys are ORIG_DEST_YYYY-MM-DD.
 */
import { describe, it, expect } from "vitest";
import {
  normalizeDate,
  getCachedRoutes,
  getCacheMeta,
  CACHED_PAIRS,
} from "@/data/cachedRoutes";

describe("cachedRoutes - normalizeDate", () => {
  it("returns empty string for undefined", () => {
    expect(normalizeDate(undefined)).toBe("");
  });

  it("returns empty string for empty string", () => {
    expect(normalizeDate("")).toBe("");
  });

  it("returns empty string for whitespace-only", () => {
    expect(normalizeDate("   ")).toBe("");
  });

  it("returns YYYY-MM-DD as-is", () => {
    expect(normalizeDate("2026-02-15")).toBe("2026-02-15");
  });

  it("normalizes DD/MM/YYYY to YYYY-MM-DD", () => {
    expect(normalizeDate("15/02/2026")).toBe("2026-02-15");
  });

  it("normalizes DD-MM-YYYY to YYYY-MM-DD", () => {
    expect(normalizeDate("15-02-2026")).toBe("2026-02-15");
  });

  it("pads single-digit day and month", () => {
    expect(normalizeDate("5/3/2026")).toBe("2026-03-05");
  });

  it("returns empty for invalid format", () => {
    expect(normalizeDate("not-a-date")).toBe("");
  });

  it("trims input", () => {
    expect(normalizeDate("  2026-02-15  ")).toBe("2026-02-15");
  });
});

describe("cachedRoutes - getCachedRoutes", () => {
  it("returns null when origin is empty", () => {
    expect(getCachedRoutes("", "BCT", "2026-02-15")).toBeNull();
  });

  it("returns null when dest is empty", () => {
    expect(getCachedRoutes("NDLS", "", "2026-02-15")).toBeNull();
  });

  it("returns null when date is empty", () => {
    expect(getCachedRoutes("NDLS", "BCT", "")).toBeNull();
  });

  it("returns null for invalid date", () => {
    expect(getCachedRoutes("NDLS", "BCT", "invalid")).toBeNull();
  });

  it("accepts valid codes and date (may return null if cache empty)", () => {
    const result = getCachedRoutes("NDLS", "BCT", "2026-02-15");
    expect(result === null || (typeof result === "object" && "routes" in result)).toBe(true);
  });

  it("is case-insensitive for codes (normalized to upper in key)", () => {
    const r1 = getCachedRoutes("ndls", "bct", "2026-02-15");
    const r2 = getCachedRoutes("NDLS", "BCT", "2026-02-15");
    expect(r1).toBe(r2);
  });

  it("uses normalized date for lookup", () => {
    const r1 = getCachedRoutes("NDLS", "BCT", "15/02/2026");
    const r2 = getCachedRoutes("NDLS", "BCT", "2026-02-15");
    expect(r1).toBe(r2);
  });
});

describe("cachedRoutes - getCacheMeta", () => {
  it("returns meta object with generatedAt, pairs, dates", () => {
    const meta = getCacheMeta();
    expect(meta).toBeDefined();
    expect("generatedAt" in meta).toBe(true);
    expect("pairs" in meta).toBe(true);
    expect("dates" in meta).toBe(true);
    expect(Array.isArray(meta.pairs)).toBe(true);
    expect(Array.isArray(meta.dates)).toBe(true);
  });
});

describe("cachedRoutes - CACHED_PAIRS", () => {
  it("has at least one pair", () => {
    expect(CACHED_PAIRS.length).toBeGreaterThanOrEqual(1);
  });

  it("each pair has origin, dest, originName, destName", () => {
    CACHED_PAIRS.forEach((p) => {
      expect(p).toHaveProperty("origin");
      expect(p).toHaveProperty("dest");
      expect(p).toHaveProperty("originName");
      expect(p).toHaveProperty("destName");
    });
  });
});
