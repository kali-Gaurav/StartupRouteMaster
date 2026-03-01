/**
 * Chatbot API — Rail Assistant / Disha. Pure API calls. No UI.
 * Uses getRailwayApiUrl (root path: /chat).
 */

import { getRailwayApiUrl } from "@/lib/utils";

export interface ChatAction {
  label: string;
  type: string;
  value?: string;
}

export interface ChatResponse {
  reply: string;
  message?: string;
  actions?: ChatAction[];
  state?: string;
  trigger_search?: boolean;
  collected?: { source?: string; destination?: string; from?: string; to?: string; date?: string };
  session_id?: string;
  /** Set when trigger_search is true; use for X-Correlation-Id on /routes and POST /flow/ack */
  correlation_id?: string;
}

export async function sendChatMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  const res = await fetch(getRailwayApiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message.trim(), session_id: sessionId ?? undefined }),
  });
  const data = (await res.json().catch(() => ({}))) as ChatResponse;
  if (!res.ok) {
    const reply = data.reply ?? data.message ?? "Backend error. Please try again.";
    return { ...data, reply, message: reply };
  }
  return {
    reply: data.reply ?? data.message ?? "",
    message: data.message ?? data.reply,
    actions: Array.isArray(data.actions) ? data.actions : [],
    state: data.state ?? "idle",
    trigger_search: data.trigger_search ?? false,
    collected: data.collected ?? undefined,
    session_id: data.session_id ?? sessionId,
    correlation_id: data.correlation_id ?? undefined,
  };
}
