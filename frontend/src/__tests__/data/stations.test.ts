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

describe("stations - searchStations (local placeholder)", () => {
  it("always returns empty array since search is delegated to backend", () => {
    expect(searchStations("")).toEqual([]);
    expect(searchStations("a")).toEqual([]);
    expect(searchStations("Delhi")).toEqual([]);
    expect(searchStations("NDLS")).toEqual([]);
  });

  it("trims query and stays empty", () => {
    const r1 = searchStations("  Delhi  ");
    const r2 = searchStations("Delhi");
    expect(r1).toEqual(r2);
  });
});

describe("stations - getStationByCode", () => {
  it("returns undefined for empty or missing code", () => {
    expect(getStationByCode("")).toBeUndefined();
    expect(getStationByCode(undefined as unknown as string)).toBeUndefined();
  });

  it("can return cached station when added", () => {
    const sample = { code: "XYZ", name: "Test", city: "T", state: "S" };
    addStationsToCache([sample]);
    expect(getStationByCode("XYZ")).toEqual(sample);
    expect(getStationByCode("xyz")).toEqual(sample);
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
