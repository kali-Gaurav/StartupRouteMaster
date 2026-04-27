import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { Loader2, CreditCard, ShieldCheck, AlertTriangle } from "lucide-react";

async function loadRazorpayScript(): Promise<void> {
  if ((window as any).Razorpay) return;

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Razorpay checkout script."));
    document.body.appendChild(script);
  });
}

interface CreateOrderResponse {
  order_id: string;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  key_id: string;
}

export default function RazorpayCheckout() {
  const [amount, setAmount] = useState("1.00");
  const [receipt, setReceipt] = useState("rzp_receipt_" + Date.now());
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const razorpayKeyId = useMemo(
    () => import.meta.env.VITE_RAZORPAY_KEY_ID || "",
    []
  );

  useEffect(() => {
    if (!window.Razorpay) {
      loadRazorpayScript().catch((error) => {
        console.error(error);
        setErrorMessage("Unable to load Razorpay checkout. Please try again later.");
      });
    }
  }, []);

  const createOrder = async (): Promise<CreateOrderResponse> => {
    const amountPaise = Math.max(100, Math.round(Number(amount) * 100));

    const response = await fetch("/api/razorpay/create-order", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem("token")}` // Ensure auth header is present
      },
      body: JSON.stringify({
        amount: amountPaise,
        currency: "INR",
        receipt,
        notes: {
          description: "Razorpay Standard Checkout Test",
        },
      }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || payload?.message || "Failed to create order.");
    }

    return response.json();
  };

  const verifyOrder = async (payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }) => {
    const response = await fetch("/api/razorpay/verify-payment", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem("token")}`
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.detail || payload?.message || "Payment verification failed.");
    }

    return response.json();
  };

  const openCheckout = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setLoading(true);

    if (!razorpayKeyId) {
      setErrorMessage("Missing Razorpay public key. Please configure VITE_RAZORPAY_KEY_ID.");
      setLoading(false);
      return;
    }

    try {
      await loadRazorpayScript();
      const order = await createOrder();
      const keyId = razorpayKeyId || order.key_id;

      const RazorpayCheckoutConstructor = (window as any).Razorpay;
      if (!RazorpayCheckoutConstructor) {
        throw new Error("Razorpay checkout is unavailable.");
      }

      const options = {
        key: keyId,
        amount: order.amount,
        currency: order.currency,
        name: "RouteMaster Checkout",
        description: "Standard Razorpay payment",
        order_id: order.razorpay_order_id,
        theme: { color: "#2563eb" },
        modal: {
          ondismiss: () => {
            toast({ title: "Payment cancelled", description: "You dismissed the payment modal.", variant: "default" });
            setLoading(false);
          },
        },
        handler: async (response: Record<string, string>) => {
          try {
            await verifyOrder({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });
            setSuccessMessage("Payment verified successfully.");
            toast({ title: "Payment verified", description: "Your payment signature is valid.", variant: "default" });
          } catch (error: any) {
            setErrorMessage(error?.message || "Unable to verify payment.");
          } finally {
            setLoading(false);
          }
        },
      };

      const checkout = new RazorpayCheckoutConstructor(options);
      checkout.open();
    } catch (error: any) {
      console.error(error);
      setErrorMessage(error?.message || "Checkout failed.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-primary">Payments</p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">Razorpay Standard Checkout</h1>
          <p className="mt-4 text-sm text-muted-foreground">This page demonstrates order creation, Razorpay modal launch, and backend signature verification.</p>
        </div>

        <Card className="shadow-lg border border-border/50">
          <CardContent className="space-y-6 p-8">
            <div className="grid gap-6 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-semibold">Amount (INR)</span>
                <Input
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  type="number"
                  min="1"
                  step="0.01"
                  aria-label="Amount in rupees"
                />
              </label>
              <label className="space-y-2">
                <span className="text-sm font-semibold">Receipt ID</span>
                <Input
                  value={receipt}
                  onChange={(event) => setReceipt(event.target.value)}
                  aria-label="Unique receipt identifier"
                />
              </label>
            </div>

            <div className="rounded-2xl border border-border/70 bg-muted p-4 text-sm text-muted-foreground">
              <p className="font-semibold">Notes</p>
              <p className="mt-2">Payment will be created using Razorpay standard checkout. Amount must be at least ₹1.00 (100 paise).</p>
              <p className="mt-2">The secret key is never exposed to the frontend. Only the public key is used in the checkout modal.</p>
            </div>

            {errorMessage ? (
              <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <p>{errorMessage}</p>
                </div>
              </div>
            ) : null}

            {successMessage ? (
              <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 shrink-0" />
                  <p>{successMessage}</p>
                </div>
              </div>
            ) : null}

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Public Key</p>
                <p className="mt-1 text-sm text-foreground">{razorpayKeyId || "Not configured"}</p>
              </div>
              <Button
                onClick={openCheckout}
                disabled={loading}
                className="inline-flex items-center justify-center gap-2 h-14 px-6 rounded-xl"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
                {loading ? "Starting checkout..." : "Pay with Razorpay"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
