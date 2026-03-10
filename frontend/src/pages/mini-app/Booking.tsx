import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ArrowRight, Train, IndianRupee, Info, ShieldCheck } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { BookingPaymentStep } from "@/components/booking/BookingPaymentStep";
import { BookingFlowProvider, useBookingFlowContext } from "@/context/BookingFlowContext";

interface Passenger {
  fullName: string;
  age: number;
  gender: string;
}

const MiniAppBookingContent = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { openReview, step } = useBookingFlowContext();
  
  const { route, origin, destination, date } = (location.state || {}) as {
    route: any;
    origin: any;
    destination: any;
    date: string;
  };

  const [passengers, setPassengers] = useState<Passenger[]>([
    { fullName: "", age: 30, gender: "M" }
  ]);
  const [isEnteringDetails, setIsEnteringDetails] = useState(true);

  const handleAddPassenger = () => {
    if (passengers.length < 6) {
      setPassengers([...passengers, { fullName: "", age: 30, gender: "M" }]);
    }
  };

  const handleRemovePassenger = (index: number) => {
    setPassengers(passengers.filter((_, i) => i !== index));
  };

  const updatePassenger = (index: number, field: keyof Passenger, value: any) => {
    const newPassengers = [...passengers];
    (newPassengers[index] as any)[field] = value;
    setPassengers(newPassengers);
  };

  const handleProceedToPayment = () => {
    if (passengers.some(p => !p.fullName.trim())) {
      toast({ title: "Please enter all passenger names", variant: "destructive" });
      return;
    }
    
    // Initialize the shared booking flow context with this route
    openReview({
      route: {
        ...route,
        id: route.journey_id || route.id,
        total_cost: Math.round((route.fare || 540) * passengers.length),
        segments: route.segments || []
      },
      travelDate: date,
      originName: origin?.name || "Source",
      destName: destination?.name || "Destination"
    });
    
    setIsEnteringDetails(false);
  };

  if (!isEnteringDetails) {
    return (
      <div className="min-h-screen bg-gray-50 pb-20 overflow-y-auto">
        <div className="bg-[#0f172a] text-white p-6 mb-6">
           <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" onClick={() => setIsEnteringDetails(true)} className="text-white hover:bg-white/10">
                   <ArrowLeft className="h-5 w-5" />
                </Button>
                <h1 className="text-xl font-bold">Secure Checkout</h1>
              </div>
              <div className="flex items-center gap-2 bg-emerald-500/20 px-3 py-1.5 rounded-full border border-emerald-500/30">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="text-[10px] font-bold uppercase tracking-tighter text-emerald-100">Escrow Pipeline Active</span>
              </div>
           </div>
        </div>
        <div className="max-w-5xl mx-auto px-4">
          <BookingPaymentStep serviceType="AGENT_BOOKING" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <div className="bg-blue-600 text-white p-4">
         <div className="max-w-md mx-auto flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-white hover:bg-white/10">
               <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-bold">Passenger Details</h1>
         </div>
      </div>

      <div className="max-w-md mx-auto p-4 space-y-6 mt-2">
         {/* Summary Header */}
         <Card className="shadow-sm border-none bg-white rounded-2xl overflow-hidden">
           <CardContent className="p-5 flex items-center justify-between">
              <div>
                 <p className="text-sm font-bold text-gray-900">{route?.train_name || "Express Train"}</p>
                 <p className="text-xs text-gray-500">{origin?.name} → {destination?.name}</p>
              </div>
              <div className="text-right">
                 <p className="text-xs text-gray-500">{date}</p>
                 <Badge className="bg-blue-50 text-blue-600 hover:bg-blue-100 border-none text-[10px] px-2 py-0.5 mt-1 font-bold">
                   3A - AC Economy
                 </Badge>
              </div>
           </CardContent>
         </Card>

         {/* Passenger Fields */}
         <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
               <h2 className="text-lg font-bold text-gray-900">Add Passengers</h2>
               <p className="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-md">{passengers.length}/6</p>
            </div>

            {passengers.map((p, index) => (
              <Card key={index} className="shadow-sm border-gray-100 rounded-2xl animate-in slide-in-from-bottom-2 duration-300">
                 <CardContent className="p-5 space-y-4">
                    <div className="flex justify-between items-center">
                       <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest bg-blue-50 px-2 py-0.5 rounded">Passenger {index + 1}</span>
                       {passengers.length > 1 && (
                         <Button 
                           variant="ghost" 
                           size="sm" 
                           onClick={() => handleRemovePassenger(index)}
                           className="text-red-500 h-7 px-2 text-xs font-bold hover:bg-red-50"
                         >
                            Remove
                         </Button>
                       )}
                    </div>
                    <div className="space-y-1.5">
                       <Label className="text-[10px] font-bold text-gray-400 uppercase ml-1">Full Name (as per ID)</Label>
                       <Input 
                         placeholder="MR. GAURAV NAGAR"
                         value={p.fullName}
                         onChange={(e) => updatePassenger(index, "fullName", e.target.value.toUpperCase())}
                         className="h-12 border-gray-200 focus:border-blue-500 rounded-xl font-bold placeholder:font-normal"
                       />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                       <div className="space-y-1.5">
                          <Label className="text-[10px] font-bold text-gray-400 uppercase ml-1">Age</Label>
                          <Input 
                            type="number"
                            value={p.age}
                            onChange={(e) => updatePassenger(index, "age", parseInt(e.target.value))}
                            className="h-12 border-gray-200 focus:border-blue-500 rounded-xl font-bold"
                          />
                       </div>
                       <div className="space-y-1.5">
                          <Label className="text-[10px] font-bold text-gray-400 uppercase ml-1">Gender</Label>
                          <div className="flex bg-gray-100 rounded-xl p-1 h-12">
                             {["M", "F", "O"].map(g => (
                               <button
                                 key={g}
                                 onClick={() => updatePassenger(index, "gender", g)}
                                 className={`flex-1 rounded-lg text-xs font-bold transition-all ${p.gender === g ? "bg-white text-blue-600 shadow-sm" : "text-gray-500"}`}
                               >
                                 {g === "M" ? "M" : g === "F" ? "F" : "O"}
                               </button>
                             ))}
                          </div>
                       </div>
                    </div>
                 </CardContent>
              </Card>
            ))}

            <Button 
              variant="outline" 
              onClick={handleAddPassenger} 
              disabled={passengers.length >= 6}
              className="w-full border-dashed border-2 h-14 text-blue-600 border-blue-200 bg-blue-50/30 hover:bg-blue-50 rounded-2xl font-bold transition-all"
            >
               + Add Another Passenger
            </Button>
         </div>

         <div className="bg-amber-50/50 border border-amber-100 rounded-2xl p-4 flex gap-3 stagger-1">
            <Info className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-700 leading-relaxed font-medium">
              Ticket cancellation charges apply as per Railway rules. Seats will be allocated based on your preference during payment.
            </p>
         </div>
      </div>

      {/* Bottom Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 pb-6 shadow-[0_-8px_30px_rgba(0,0,0,0.08)] z-50">
         <div className="max-w-md mx-auto flex items-center justify-between gap-6">
            <div>
               <p className="text-[10px] text-gray-400 uppercase font-black tracking-widest mb-0.5">Final Total</p>
               <div className="flex items-center text-2xl font-black text-gray-900">
                  <IndianRupee className="w-5 h-5 text-blue-600" />
                  <span>{Math.round((route?.fare || 540) * passengers.length)}</span>
               </div>
            </div>
            <Button 
               onClick={handleProceedToPayment}
               className="bg-blue-600 hover:bg-blue-700 text-white px-8 h-14 font-black rounded-2xl flex-1 shadow-lg shadow-blue-600/20 active:scale-95 transition-all text-base"
            >
               Proceed to Pay
               <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
         </div>
      </div>
    </div>
  );
};

// Wrap with Provider to ensure context is available
const MiniAppBooking = () => (
  <BookingFlowProvider>
    <MiniAppBookingContent />
  </BookingFlowProvider>
);

export default MiniAppBooking;
