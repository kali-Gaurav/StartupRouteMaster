/**
 * Flow Tracker API — Phase 6 integration orchestrator.
 * POST /flow/ack: frontend confirms a step (e.g. ROUTE_RENDERED).
 * GET /flow/status: dashboard metrics (active/completed/failed flows).
 */

import { getRailwayApiUrl } from "@/lib/utils";

export const FLOW_EVENTS = {
  ROUTE_RENDERED: "ROUTE_RENDERED",
  BOOKING_STARTED: "BOOKING_STARTED",
  PAYMENT_STARTED: "PAYMENT_STARTED",
  PAYMENT_CONFIRMED: "PAYMENT_CONFIRMED",
  UI_CONFIRMED: "UI_CONFIRMED",
} as const;

export interface FlowAckPayload {
  correlation_id: string;
  event: string;
  payload?: Record<string, unknown>;
}

export interface FlowStatusResponse {
  active_flows: number;
  completed_flows: number;
  failed_flows: number;
  avg_completion_time_sec?: number;
  active_correlation_ids?: string[];
  warnings?: string[];
}

/** Send a flow step acknowledgment (e.g. when routes are displayed). Fire-and-forget; no throw. */
export async function ackFlow(
  correlationId: string,
  event: string,
  payload?: Record<string, unknown>
): Promise<void> {
  try {
    const res = await fetch(getRailwayApiUrl("/flow/ack"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        correlation_id: correlationId,
        event,
        ...(payload && { payload }),
      }),
    });
    if (!res.ok) {
      console.debug("[flow] ack non-ok:", res.status, await res.text().catch(() => ""));
    }
  } catch (e) {
    console.debug("[flow] ack failed:", e);
  }
}

/** Fetch flow health dashboard (active/completed/failed, warnings). */
export async function getFlowStatus(): Promise<FlowStatusResponse> {
  const res = await fetch(getRailwayApiUrl("/flow/status"));
  if (!res.ok) throw new Error("Flow status failed: " + res.status);
  return res.json();
}
