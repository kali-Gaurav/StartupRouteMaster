import { describe, it, expect } from "vitest";

const BACKEND_URL = "http://localhost:8000";

describe("Real System Integration - Frontend to Backend", () => {
  
  it("verifies root backend connectivity", async () => {
    const res = await fetch(`${BACKEND_URL}/`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.message).toContain("RouteMaster");
  });

  it("verifies health check endpoint", async () => {
    const res = await fetch(`${BACKEND_URL}/health`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.status).toBe("healthy");
  });

  it("verifies API status health (DB + Engine)", async () => {
    const res = await fetch(`${BACKEND_URL}/api/status/health`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.status).toBe("ok");
    expect(data.components.database).toBe("ok");
  });

  it("tests live train tracking endpoint with real data", async () => {
    const trainNo = "12002"; // Bhopal Shatabdi
    const res = await fetch(`${BACKEND_URL}/api/v2/live/train/${trainNo}`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.train_no).toBe(trainNo);
    expect(data.status).toBeDefined();
  });

  it("tests station board endpoint", async () => {
    const stationCode = "NDLS";
    const res = await fetch(`${BACKEND_URL}/api/v2/live/station/${stationCode}`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.station).toBe(stationCode);
    expect(Array.isArray(data.departures)).toBe(true);
  });

  it("verifies SOS system health", async () => {
    const res = await fetch(`${BACKEND_URL}/api/sos/health`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.status).toBe("ok");
  });

  it("verifies flow status endpoint", async () => {
    const res = await fetch(`${BACKEND_URL}/api/api/flow/status`);
    const data = await res.json();
    expect(res.status).toBe(200);
    expect(data.active_flows).toBeDefined();
  });

});
