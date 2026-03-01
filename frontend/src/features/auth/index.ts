/**
 * Auth feature – re-exports for feature-based structure.
 * New code can import from "@/features/auth"; existing imports unchanged.
 */

export { useAuth, AuthProvider, type User } from "@/context/AuthContext";
export { AuthModal } from "@/components/AuthModal";
export {
  sendOTP,
  verifyOTP,
  googleAuth,
  telegramAuth,
  getCurrentUser,
  updateProfile,
  updateLocation,
  type AuthResponse,
  type SendOTPRequest,
  type VerifyOTPRequest,
} from "@/lib/authApi";
export { sendOTPSchema, verifyOTPSchema } from "@/lib/schemas/authSchema";
