import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { 
  ArrowLeft, 
  User, 
  Plus, 
  Trash2, 
  ShieldCheck, 
  Zap, 
  CreditCard,
  Train,
  CheckCircle2,
  AlertCircle,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";
import { createBookingRequest, type BookingRequestPassenger } from "@/api/booking";
import { cn } from "@/lib/utils";

const MiniAppBooking = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { webApp, showBackButton, hapticFeedback, showMainButton } = useTelegramWebApp();
  const [passengers, setPassengers] = useState<BookingRequestPassenger[]>([{ name: "", age: 25, gender: "M" }]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [referenceId, setReferenceId] = useState("");

  // Extract route details from search params
  const trainNumber = searchParams.get("train") || "";
  const trainName = searchParams.get("name") || "";
  const fromCode = searchParams.get("from") || "";
  const toCode = searchParams.get("to") || "";
  const date = searchParams.get("date") || "";
  const classType = searchParams.get("class") || "SL";
  const quota = searchParams.get("quota") || "GN";

  useEffect(() => {
    const isFormValid = !loading && passengers.every(p => p.name && p.age);
    if (isFormValid && !success) {
      const hide = showMainButton("INITIALIZE BOOKING", handleBooking);
      return hide;
    }
  }, [loading, passengers, success, showMainButton]);

  useEffect(() => {
    const hide = showBackButton(() => {
      if (success) navigate("/mini-app");
      else navigate("/mini-app/search");
    });
    return hide;
  }, [showBackButton, success, navigate]);

  const addPassenger = () => {
    if (passengers.length >= 6) {
      toast.error("Maximum 6 passengers allowed");
      return;
    }
    setPassengers([...passengers, { name: "", age: 25, gender: "M" }]);
  };

  const removePassenger = (index: number) => {
    if (passengers.length === 1) return;
    setPassengers(passengers.filter((_, i) => i !== index));
  };

  const handleBooking = async () => {
    if (!trainNumber || !fromCode || !toCode || !date) {
      toast.error("Missing route information. Please search again.");
      return;
    }

    setLoading(true);
    try {
      const response = await createBookingRequest({
        source_station: fromCode,
        destination_station: toCode,
        journey_date: date,
        train_number: trainNumber,
        class_type: classType,
        quota: quota,
        passengers: passengers
      });
      
      setReferenceId(response.id);
      setSuccess(true);
      hapticFeedback?.notificationOccurred("success");
      toast.success("Booking Request Synthesized");
    } catch (error: any) {
      hapticFeedback?.notificationOccurred("error");
      toast.error(error.message || "Failed to create booking request");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-center animate-in zoom-in duration-500">
        <div className="w-24 h-24 bg-emerald-500/10 rounded-full flex items-center justify-center mb-8">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 animate-in fade-in scale-in-50 duration-700" />
        </div>
        <h2 className="text-3xl font-black uppercase tracking-tighter">Vector Confirmed</h2>
        <p className="text-muted-foreground font-bold mt-2 uppercase tracking-widest text-[10px]">Registry Node: NDLS_CORE</p>
        
        <Card className="w-full max-w-sm border-none glass bg-emerald-500/5 mt-10 overflow-hidden">
          <div className="h-1 w-full bg-emerald-500/20" />
          <CardContent className="p-6 space-y-4">
            <div className="flex justify-between text-[10px] font-black uppercase text-muted-foreground border-b border-border/50 pb-3">
              <span>REFERENCE ID</span>
              <span className="text-foreground font-mono">{referenceId.slice(0, 8).toUpperCase()}</span>
            </div>
            <p className="text-[11px] font-medium text-muted-foreground leading-relaxed">
              Your manual booking request has been queued. Our operators are synthesizing your PNR for {trainNumber} on {date}. You will receive an alert via Telegram shortly.
            </p>
          </CardContent>
        </Card>

        <Button onClick={() => navigate("/mini-app")} className="mt-10 w-full max-w-sm h-14 rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-primary/20">
          RETURN TO TERMINAL
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground">
      <div className="p-4 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app/search")} className="rounded-xl lg:hidden">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">Entity Entry</h1>
          </div>
          <Badge variant="outline" className="font-black text-[10px] bg-primary/5 border-primary/20 text-primary">STEP 1/2</Badge>
        </div>
      </div>

      <main className="flex-1 max-w-md mx-auto w-full p-4 space-y-6">
        <div className="p-4 rounded-2xl bg-secondary/30 border border-border">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm font-black uppercase">{trainNumber} - {trainName}</h3>
            <Badge variant="secondary" className="text-[10px]">{classType}</Badge>
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{fromCode} → {toCode}</span>
            <span>{date}</span>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-black uppercase tracking-widest text-muted-foreground">Passenger Log</h2>
            <Button variant="ghost" size="sm" onClick={addPassenger} className="h-8 rounded-xl font-black text-[10px] gap-1 hover:bg-primary/10 hover:text-primary">
              <Plus className="h-3 w-3" /> ADD ENTITY
            </Button>
          </div>

          <div className="space-y-3">
            {passengers.map((p, index) => (
              <Card key={index} className="border-none glass overflow-hidden animate-in slide-in-from-right-4 duration-300" style={{ animationDelay: `${index * 100}ms` }}>
                <CardContent className="p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase text-muted-foreground opacity-50">ENTITY #{index + 1}</span>
                    {passengers.length > 1 && (
                      <Button variant="ghost" size="icon" onClick={() => removePassenger(index)} className="h-6 w-6 rounded-lg text-muted-foreground hover:text-red-500">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-12 gap-3">
                    <div className="col-span-12 relative group">
                      <User className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                      <Input
                        placeholder="Legal Name"
                        className="pl-10 h-12 rounded-xl border-2 bg-muted/30 focus:bg-background transition-all font-bold text-sm"
                        value={p.name}
                        onChange={(e) => {
                          const newP = [...passengers];
                          newP[index].name = e.target.value;
                          setPassengers(newP);
                        }}
                      />
                    </div>
                    <div className="col-span-5 relative">
                      <Input
                        type="number"
                        placeholder="Age"
                        className="h-12 rounded-xl border-2 bg-muted/30 focus:bg-background transition-all font-bold text-sm"
                        value={p.age}
                        onChange={(e) => {
                          const newP = [...passengers];
                          newP[index].age = parseInt(e.target.value) || 0;
                          setPassengers(newP);
                        }}
                      />
                    </div>
                    <div className="col-span-7 flex bg-muted/30 rounded-xl p-1 border-2 border-transparent">
                      {['M', 'F', 'O'].map((g) => (
                        <button
                          key={g}
                          onClick={() => {
                            const newP = [...passengers];
                            newP[index].gender = g as "M" | "F" | "O";
                            setPassengers(newP);
                          }}
                          className={cn(
                            "flex-1 h-10 rounded-lg text-[10px] font-black transition-all",
                            p.gender === g ? "bg-background shadow-md text-primary" : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {g === 'M' ? 'MALE' : g === 'F' ? 'FEMALE' : 'OTHER'}
                        </button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div className="pt-4 pb-10 space-y-4">
          <Card className="border-none glass bg-blue-500/5">
            <CardContent className="p-5 flex items-start gap-4">
              <ShieldCheck className="h-5 w-5 text-blue-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-[10px] font-black uppercase text-blue-600">Identity Protection</p>
                <p className="text-[9px] font-bold text-muted-foreground uppercase leading-relaxed mt-1">Entity data is encrypted via AES-256 and purged post-journey synthesis.</p>
              </div>
            </CardContent>
          </Card>

          {!webApp && (
            <Button 
              disabled={loading || passengers.some(p => !p.name || !p.age)} 
              onClick={handleBooking}
              className="w-full h-16 rounded-2xl font-black uppercase tracking-widest shadow-xl shadow-primary/20 active:scale-95 transition-all group"
            >
              {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : (
                <div className="flex items-center gap-2">
                  <span>INITIALIZE BOOKING</span>
                  <Zap className="h-4 w-4 fill-current group-hover:animate-pulse" />
                </div>
              )}
            </Button>
          )}
        </div>
      </main>
    </div>
  );
};

export default MiniAppBooking;
