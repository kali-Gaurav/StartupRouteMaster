/**
 * Zod schemas for routes API responses. Validate backend responses to fail early on contract drift.
 */

import { z } from "zod";

const RouteSegmentSchema = z.object({
  train_no: z.number(),
  train_name: z.string().optional(),
  train_type: z.string().optional(),
  departure: z.string().optional(),
  arrival: z.string().optional(),
  distance: z.number().optional(),
  time_minutes: z.number().optional(),
  time_str: z.string().optional(),
  day_diff: z.number().optional(),
  fare: z.number().nullable().optional(),
  availability: z.string().nullable().optional(),
});

const RoutesMapSchema = z.object({
  direct: z.array(RouteSegmentSchema),
  one_transfer: z.array(z.any()),
  two_transfer: z.array(z.any()),
  three_transfer: z.array(z.any()),
});

const StationInfoSchema = z.object({
  code: z.string(),
  name: z.string(),
  city: z.string(),
  state: z.string(),
});

export const RoutesResponseSchema = z.object({
  source: z.string(),
  destination: z.string(),
  routes: RoutesMapSchema,
  stations: z.record(z.string(), StationInfoSchema).optional(),
  journey_message: z.string().optional(),
  booking_tips: z.array(z.string()).optional(),
  message: z.string().optional(),
});

export type RoutesResponse = z.infer<typeof RoutesResponseSchema>;

/**
 * Parse and validate routes API response. Throws ZodError if backend shape changed.
 */
export function parseRoutesResponse(data: unknown): RoutesResponse {
  return RoutesResponseSchema.parse(data);
}

/**
 * Safe parse; returns { success: true, data } or { success: false, error }.
 */
export function safeParseRoutesResponse(data: unknown): z.SafeParseReturnType<unknown, RoutesResponse> {
  return RoutesResponseSchema.safeParse(data);
}

const StationSchema = z.object({
  station_code: z.string(),
  station_name: z.string().optional(),
  city: z.string().optional(),
  state: z.string().optional(),
});

export const StationsSearchResponseSchema = z.object({
  stations: z.array(StationSchema),
});

export type StationsSearchResponse = z.infer<typeof StationsSearchResponseSchema>;

export function parseStationsSearchResponse(data: unknown): StationsSearchResponse {
  return StationsSearchResponseSchema.parse(data);
}
