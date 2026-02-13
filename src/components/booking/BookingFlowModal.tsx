import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useBookingFlowContext } from "@/context/BookingFlowContext";
import { useAuth } from "@/context/AuthContext";
import { BookingStepProgress } from "@/components/booking/BookingStepProgress";
import { BookingReviewStep } from "@/components/booking/BookingReviewStep";
import { AvailabilityCheckStep } from "@/components/booking/AvailabilityCheckStep";
import { BookingPaymentStep } from "@/components/booking/BookingPaymentStep";
import { BookingConfirmationStep } from "@/components/booking/BookingConfirmationStep";
import { AuthModal } from "@/components/AuthModal";

export function BookingFlowModal() {
  const { open, step, close } = useBookingFlowContext();
  const { isAuthenticated } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  const needsAuth = step === "payment" && !isAuthenticated;

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !o && close()}>
        <DialogContent
          className="sm:max-w-lg max-h-[90vh] overflow-y-auto"
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="sr-only">Booking</DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            <BookingStepProgress />

            {step === "review" && <BookingReviewStep />}

            {step === "availability" && <AvailabilityCheckStep />}

            {step === "payment" && (
              <>
                {needsAuth ? (
                  <div className="space-y-4 py-4">
                    <p className="text-muted-foreground text-center">
                      Sign in to complete payment and get your IRCTC booking link.
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowAuthModal(true)}
                      className="w-full py-3 px-4 rounded-lg font-semibold bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
                    >
                      Sign in to continue
                    </button>
                  </div>
                ) : (
                  <BookingPaymentStep />
                )}
              </>
            )}

            {step === "confirmation" && <BookingConfirmationStep />}
          </div>
        </DialogContent>
      </Dialog>

      <AuthModal
        open={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={() => setShowAuthModal(false)}
      />
    </>
  );
}
