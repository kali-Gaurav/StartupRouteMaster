import { describe, it, expect, vi, beforeEach } from "vitest";
import * as apiClient from "@/lib/apiClient";
import { getUnlockedRoutes } from "@/lib/paymentApi";

describe("paymentApi - getUnlockedRoutes", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls fetchWithAuth with the unlocked-routes path and returns parsed body", async () => {
    const fakeResp = { json: async () => ({ routes: ["route_1", "route_2"] }) } as any;
    const spy = vi.spyOn(apiClient, "fetchWithAuth").mockResolvedValue(fakeResp);

    const res = await getUnlockedRoutes();

    expect(spy).toHaveBeenCalledWith('/payments/unlocked-routes');
    expect(res).toEqual({ routes: ["route_1", "route_2"] });
  });
});
