/**
 * Booking / payment form validation – aligned with backend payloads.
 */

import { z } from "zod";

export const bookingRedirectSchema = z.object({
  payment_order_id: z.string().min(1, "Payment order ID required"),
  origin: z.string().min(1, "Origin station required"),
  destination: z.string().min(1, "Destination station required"),
  train_no: z.string().min(1, "Train number required"),
  travel_date: z.string().min(1, "Travel date required"),
  travel_class: z.string().optional(),
});

export const createOrderSchema = z.object({
  route_origin: z.string().min(1),
  route_destination: z.string().min(1),
  train_no: z.string().optional(),
  travel_date: z.string().optional(),
});

export type BookingRedirectInput = z.infer<typeof bookingRedirectSchema>;
export type CreateOrderInput = z.infer<typeof createOrderSchema>;
