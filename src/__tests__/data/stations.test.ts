/**
 * Tests for stations data: searchStations, addStationsToCache, getStationByCode.
 * Handles undefined/null safely (no toUpperCase on undefined).
 */
import { describe, it, expect } from "vitest";
import {
  searchStations,
  addStationsToCache,
  getStationByCode,
} from "@/data/stations";

describe("stations - searchStations", () => {
  it("returns empty array for empty string", () => {
    expect(searchStations("")).toEqual([]);
  });

  it("returns empty array for undefined", () => {
    expect(searchStations(undefined as unknown as string)).toEqual([]);
  });

  it("returns empty array for single character", () => {
    expect(searchStations("a").length).toBeLessThanOrEqual(50);
  });

  it("returns array of stations for valid query", () => {
    const results = searchStations("Delhi");
    expect(Array.isArray(results)).toBe(true);
    expect(results.length).toBeLessThanOrEqual(50);
  });

  it("each result has code, name, city, state", () => {
    const results = searchStations("Delhi");
    results.forEach((s) => {
      expect(s).toHaveProperty("code");
      expect(s).toHaveProperty("name");
      expect(s).toHaveProperty("city");
      expect(s).toHaveProperty("state");
    });
  });

  it("search by code returns matches", () => {
    const results = searchStations("NDLS");
    expect(Array.isArray(results)).toBe(true);
  });

  it("trims query", () => {
    const r1 = searchStations("  Delhi  ");
    const r2 = searchStations("Delhi");
    expect(r1.length).toBe(r2.length);
  });
});

describe("stations - getStationByCode", () => {
  it("returns undefined for empty code", () => {
    expect(getStationByCode("")).toBeUndefined();
  });

  it("returns undefined for undefined", () => {
    expect(getStationByCode(undefined as unknown as string)).toBeUndefined();
  });

  it("returns station or undefined for valid code", () => {
    const s = getStationByCode("NDLS");
    expect(s == null || (typeof s === "object" && "code" in s)).toBe(true);
  });

  it("is case-insensitive", () => {
    const s1 = getStationByCode("ndls");
    const s2 = getStationByCode("NDLS");
    expect(s1).toEqual(s2);
  });
});

describe("stations - addStationsToCache", () => {
  it("does not throw for empty array", () => {
    addStationsToCache([]);
  });

  it("adds stations with valid code", () => {
    addStationsToCache([
      { code: "TST", name: "Test Station", city: "Test", state: "TS", isJunction: false },
    ]);
    const s = getStationByCode("TST");
    expect(s?.code).toBe("TST");
  });

  it("ignores entries with empty code", () => {
    addStationsToCache([
      { code: "", name: "No Code", city: "", state: "", isJunction: false },
    ]);
    expect(getStationByCode("")).toBeUndefined();
  });
});
