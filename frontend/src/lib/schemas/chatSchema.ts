/**
 * Zod schemas for chatbot API responses. Validate backend responses to fail early on contract drift.
 */

import { z } from "zod";

export const ChatActionSchema = z.object({
  label: z.string(),
  type: z.string(),
  value: z.string().optional(),
});

export const ChatCollectedSchema = z
  .object({
    source: z.string().optional(),
    destination: z.string().optional(),
    from: z.string().optional(),
    to: z.string().optional(),
    date: z.string().optional(),
  })
  .optional();

export const ChatResponseSchema = z.object({
  reply: z.string(),
  message: z.string().optional(),
  actions: z.array(ChatActionSchema).optional(),
  state: z.string().optional(),
  trigger_search: z.boolean().optional(),
  collected: ChatCollectedSchema,
  session_id: z.string().optional(),
});

export type ChatResponse = z.infer<typeof ChatResponseSchema>;
export type ChatAction = z.infer<typeof ChatActionSchema>;

/**
 * Parse and validate chat API response. Throws ZodError if backend shape changed.
 */
export function parseChatResponse(data: unknown): ChatResponse {
  return ChatResponseSchema.parse(data);
}

/**
 * Safe parse; returns { success: true, data } or { success: false, error }.
 */
export function safeParseChatResponse(data: unknown): z.SafeParseReturnType<unknown, ChatResponse> {
  return ChatResponseSchema.safeParse(data);
}
