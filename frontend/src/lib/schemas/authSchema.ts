/**
 * Auth form validation – shared with backend contract where possible.
 */

import { z } from "zod";

const phoneRegex = /^[6-9]\d{9}$/;

export const sendOTPSchema = z.object({
  phone: z.string().regex(phoneRegex, "Valid 10-digit Indian mobile required").optional(),
  email: z.string().email("Valid email required").optional(),
}).refine((data) => data.phone != null || data.email != null, {
  message: "Provide either phone or email",
  path: ["phone"],
});

export const verifyOTPSchema = z.object({
  phone: z.string().optional(),
  email: z.string().email().optional(),
  otp: z.string().min(4, "OTP must be at least 4 digits").max(8, "OTP too long"),
}).refine((data) => data.phone != null || data.email != null, {
  message: "Provide either phone or email",
  path: ["phone"],
});

export type SendOTPInput = z.infer<typeof sendOTPSchema>;
export type VerifyOTPInput = z.infer<typeof verifyOTPSchema>;
