/**
 * Payment Status Badge Component
 * Visual indicator for booking payment status
 */

import { CheckCircle, Clock, AlertCircle, CreditCard } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaymentStatusBadgeProps {
  paymentStatus?: string;
  bookingStatus?: string;
  className?: string;
  showIcon?: boolean;
  size?: "sm" | "md" | "lg";
}

export function PaymentStatusBadge({
  paymentStatus = "pending",
  bookingStatus = "pending",
  className,
  showIcon = true,
  size = "md",
}: PaymentStatusBadgeProps) {
  let icon = null;
  let bgColor = "";
  let textColor = "";
  let label = "";
  let borderColor = "";

  // Determine status
  const status =
    paymentStatus === "completed" ? "completed" : paymentStatus || "pending";

  switch (status) {
    case "completed":
      icon = <CheckCircle size={size === "lg" ? 16 : 12} />;
      bgColor = "bg-green-50";
      textColor = "text-green-700";
      borderColor = "border-green-200";
      label = "Paid";
      break;

    case "pending":
      icon = <Clock size={size === "lg" ? 16 : 12} />;
      bgColor = "bg-yellow-50";
      textColor = "text-yellow-700";
      borderColor = "border-yellow-200";
      label = "Pending Payment";
      break;

    case "failed":
      icon = <AlertCircle size={size === "lg" ? 16 : 12} />;
      bgColor = "bg-red-50";
      textColor = "text-red-700";
      borderColor = "border-red-200";
      label = "Payment Failed";
      break;

    case "refunded":
      icon = <CreditCard size={size === "lg" ? 16 : 12} />;
      bgColor = "bg-blue-50";
      textColor = "text-blue-700";
      borderColor = "border-blue-200";
      label = "Refunded";
      break;

    default:
      icon = <CreditCard size={size === "lg" ? 16 : 12} />;
      bgColor = "bg-gray-50";
      textColor = "text-gray-700";
      borderColor = "border-gray-200";
      label = "Unknown";
  }

  const sizeClasses = {
    sm: "px-2 py-0.5 text-[10px]",
    md: "px-3 py-1 text-xs",
    lg: "px-4 py-2 text-sm",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-semibold rounded-full border",
        bgColor,
        textColor,
        borderColor,
        sizeClasses[size],
        className
      )}
    >
      {showIcon && icon}
      {label}
    </span>
  );
}

/**
 * Payment Status Timeline
 * Shows the journey: Initiated → Pending → Verified → Confirmed
 */
interface PaymentTimelineProps {
  currentStatus: string;
  createdAt?: string;
  completedAt?: string;
}

export function PaymentTimeline({
  currentStatus,
  createdAt,
  completedAt,
}: PaymentTimelineProps) {
  const steps = [
    { id: "initiated", label: "Initiated", icon: "🔄" },
    { id: "pending", label: "Pending", icon: "⏳" },
    { id: "verified", label: "Verified", icon: "✓" },
    { id: "confirmed", label: "Confirmed", icon: "✅" },
  ];

  const currentIndex = steps.findIndex((s) => s.id === currentStatus);

  return (
    <div className="w-full">
      <div className="flex justify-between relative">
        {/* Connecting line */}
        <div
          className="absolute top-4 left-0 right-0 h-0.5 bg-gray-300"
          style={{
            width: currentIndex >= 0 ? `${(currentIndex / (steps.length - 1)) * 100}%` : "0%",
          }}
        >
          <div className="h-full bg-green-500 transition-all duration-300" />
        </div>

        {/* Steps */}
        {steps.map((step, idx) => (
          <div key={step.id} className="flex flex-col items-center relative z-10">
            <div
              className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm",
                idx <= currentIndex
                  ? "bg-green-500 text-white"
                  : "bg-gray-300 text-white"
              )}
            >
              {step.icon}
            </div>
            <span className="text-[10px] font-semibold mt-2 whitespace-nowrap text-center">
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* Timestamps */}
      <div className="mt-6 space-y-1 text-xs text-muted-foreground">
        {createdAt && (
          <div>
            Initiated: {new Date(createdAt).toLocaleString("en-IN")}
          </div>
        )}
        {completedAt && (
          <div>
            Completed: {new Date(completedAt).toLocaleString("en-IN")}
          </div>
        )}
      </div>
    </div>
  );
}
