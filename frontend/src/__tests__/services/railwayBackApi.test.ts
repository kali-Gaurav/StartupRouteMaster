/**
 * Railway Back API tests: mapBackendRoutesToRoutes, response shapes.
 * No live backend required (unit tests with mock data).
 */
import { describe, it, expect } from "vitest";
import {
  mapBackendRoutesToRoutes,
  type BackendRoutesResponse,
  type BackendDirectRoute,
} from "@/services/railwayBackApi";

describe("railwayBackApi - mapBackendRoutesToRoutes", () => {
  const mockDirect: BackendDirectRoute = {
    train_no: "12301",
    train_name: "Rajdhani",
    departure: "16:00:00",
    arrival: "08:30:00",
    distance: 1384,
    time_minutes: 990,
    day_diff: 1,
    fare: 2500,
    availability: "AVAILABLE",
  };

  it("returns empty array for empty routes", () => {
    const data: BackendRoutesResponse = {
      source: "NDLS",
      destination: "BCT",
      routes: {
        direct: [],
        one_transfer: [],
        two_transfer: [],
        three_transfer: [],
      },
    };
    const result = mapBackendRoutesToRoutes(data, "NDLS", "BCT");
    expect(result).toEqual([]);
  });

  it("maps direct routes to Route[]", () => {
    const data: BackendRoutesResponse = {
      source: "NDLS",
      destination: "BCT",
      routes: {
        direct: [mockDirect],
        one_transfer: [],
        two_transfer: [],
        three_transfer: [],
      },
    };
    const result = mapBackendRoutesToRoutes(data, "NDLS", "BCT");
    expect(result.length).toBe(1);
    expect(result[0].category).toBe("DIRECT");
    expect(result[0].segments.length).toBe(1);
    expect(result[0].totalTransfers).toBe(0);
    expect(result[0].segments[0].trainNumber).toBe("12301");
  });

  it("maps one_transfer routes", () => {
    const data: BackendRoutesResponse = {
      source: "NDLS",
      destination: "BCT",
      routes: {
        direct: [],
        one_transfer: [
          {
            type: "one_transfer",
            leg1: { ...mockDirect, train_no: "12301" },
            leg2: { ...mockDirect, train_no: "12302" },
            junction: "AGC",
            waiting_time_minutes: 45,
            total_distance: 1500,
            total_time_minutes: 1100,
          },
        ],
        two_transfer: [],
        three_transfer: [],
      },
    };
    const result = mapBackendRoutesToRoutes(data, "NDLS", "BCT");
    expect(result.length).toBe(1);
    expect(result[0].category).toBe("1 TRANSFER");
    expect(result[0].segments.length).toBe(2);
    expect(result[0].totalTransfers).toBe(1);
  });

  it("handles missing optional fields", () => {
    const minimal: BackendDirectRoute = {
      train_no: "999",
      departure: "00:00:00",
      arrival: "23:59:00",
    };
    const data: BackendRoutesResponse = {
      source: "A",
      destination: "B",
      routes: {
        direct: [minimal],
        one_transfer: [],
        two_transfer: [],
        three_transfer: [],
      },
    };
    const result = mapBackendRoutesToRoutes(data, "A", "B");
    expect(result.length).toBe(1);
    expect(result[0].segments[0].trainNumber).toBe("999");
    expect(result[0].segments[0].liveFare).toBe(0);
  });

  it("uses source and destination in segments", () => {
    const data: BackendRoutesResponse = {
      source: "NDLS",
      destination: "BCT",
      routes: {
        direct: [mockDirect],
        one_transfer: [],
        two_transfer: [],
        three_transfer: [],
      },
    };
    const result = mapBackendRoutesToRoutes(data, "NDLS", "BCT");
    expect(result[0].segments[0].from).toBe("NDLS");
    expect(result[0].segments[0].to).toBe("BCT");
  });
});
