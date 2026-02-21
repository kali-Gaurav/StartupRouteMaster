import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useBookingFlowContext,
  bookingStepsForProgress,
  bookingStepIndex,
} from "@/context/BookingFlowContext";

export function BookingStepProgress() {
  const { step } = useBookingFlowContext();
  const steps = bookingStepsForProgress();
  const currentIdx = bookingStepIndex(step);

  return (
    <nav aria-label="Booking progress" className="w-full">
      <ol className="flex items-center gap-0">
        {steps.map((s, idx) => {
          const isComplete = idx < currentIdx;
          const isCurrent = step === s.id;
          return (
            <li key={s.id} className="flex flex-1 items-center">
              <div
                className={cn(
                  "flex items-center gap-2 rounded-full px-2 sm:px-3 py-1.5 text-sm font-medium transition-colors shrink-0 whitespace-nowrap",
                  isComplete && "bg-primary text-primary-foreground",
                  isCurrent && "bg-primary/20 text-primary ring-2 ring-primary",
                  !isComplete && !isCurrent && "bg-muted text-muted-foreground"
                )}
              >
                {isComplete ? (
                  <Check className="h-4 w-4 shrink-0" />
                ) : (
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-current/20 text-xs font-semibold">
                    {idx + 1}
                  </span>
                )}
                <span className="hidden sm:inline">{s.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-0.5 mx-0.5 min-w-[4px] rounded",
                    idx < currentIdx ? "bg-primary" : "bg-muted"
                  )}
                  aria-hidden
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
