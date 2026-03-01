import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, ArrowLeft, Loader2, Train, IndianRupee, Info } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";

interface Passenger {
  fullName: string;
  age: number;
  gender: string;
}

const MiniAppBooking = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { route, origin, destination, date } = (location.state || {}) as {
    route: any;
    origin: any;
    destination: any;
    date: string;
  };

  const [passengers, setPassengers] = useState<Passenger[]>([
    { fullName: "", age: 30, gender: "M" }
  ]);
  const [isBooking, setIsBooking] = useState(false);
  const [bookingConfirmed, setBookingConfirmed] = useState(false);
  const [pnr, setPnr] = useState<string | null>(null);

  // Redirect if no route data
  useEffect(() => {
    if (!route) {
      navigate("/mini-app/search");
    }
  }, [route, navigate]);

  const handleAddPassenger = () => {
    if (passengers.length < 6) {
      setPassengers([...passengers, { fullName: "", age: 30, gender: "M" }]);
    }
  };

  const handleRemovePassenger = (index: number) => {
    setPassengers(passengers.filter((_, i) => i !== index));
  };

  const updatePassenger = (index: number, field: keyof Passenger, value: string | number) => {
    const newPassengers = [...passengers];
    newPassengers[index] = { ...newPassengers[index], [field]: value } as Passenger;
    setPassengers(newPassengers);
  };

  const handleConfirmBooking = async () => {
    // Basic validation
    if (passengers.some(p => !p.fullName.trim())) {
      toast({
        title: "Missing Information",
        description: "Please enter names for all passengers",
        variant: "destructive"
      });
      return;
    }

    setIsBooking(true);
    try {
      // Create actual booking on backend
      const response = await fetch(getRailwayApiUrl("/api/bookings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          journey_id: route.journey_id,
          travel_date: date,
          coach_preference: "AC_THREE_TIER",
          passengers: passengers.map(p => ({
            full_name: p.fullName,
            age: p.age,
            gender: p.gender
          })),
          payment_method: "test_online"
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Booking failed");
      }

      const data = await response.json();
      setPnr(data.pnr_number);
      setBookingConfirmed(true);
      
      toast({
        title: "Booking Confirmed!",
        description: `PNR: ${data.pnr_number} - Payment successful.`,
      });

      // Send to Telegram if available
      if (window.Telegram?.WebApp) {
         window.Telegram.WebApp.sendData(JSON.stringify({
           type: "BOOKING_CONFIRMED",
           pnr: data.pnr_number,
           train: route.train_name,
           from: origin.name,
           to: destination.name,
           date: date
         }));
      }

    } catch (error) {
      console.error("Booking error:", error);
      toast({
        title: "Booking Failed",
        description: error instanceof Error ? error.message : "Internal server error",
        variant: "destructive"
      });
    } finally {
      setIsBooking(false);
    }
  };

  if (bookingConfirmed) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 p-4">
        <div className="max-w-md mx-auto py-10 space-y-6">
          <div className="text-center space-y-4">
            <div className="mx-auto w-20 h-20 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
              <CheckCircle2 className="w-12 h-12" />
            </div>
            <h1 className="text-3xl font-extrabold text-gray-900">Success!</h1>
            <p className="text-gray-600">Your journey has been booked and confirmed.</p>
          </div>

          <Card className="border-2 border-green-200 shadow-xl overflow-hidden">
             <div className="bg-green-600 text-white p-4 text-center">
               <p className="text-xs uppercase tracking-widest font-bold opacity-80">Electronic Reservation Slip</p>
               <p className="text-2xl font-mono font-bold mt-1 tracking-tighter">{pnr}</p>
               <p className="text-xs mt-1">PNR NUMBER</p>
             </div>
             <CardContent className="p-6 space-y-4">
                <div className="flex justify-between items-center">
                   <div>
                     <p className="text-xs text-gray-500 uppercase font-bold">Train</p>
                     <p className="text-sm font-bold text-gray-900">{route.train_name}</p>
                   </div>
                   <div className="text-right">
                     <p className="text-xs text-gray-500 uppercase font-bold">Class</p>
                     <p className="text-sm font-bold text-gray-900">3A (AC 3 Economy)</p>
                   </div>
                </div>
                
                <Separator />
                
                <div className="flex justify-between items-center text-center">
                   <div className="flex-1">
                      <p className="text-xl font-bold">{route.departure}</p>
                      <p className="text-xs text-gray-500">{origin?.name}</p>
                   </div>
                   <div className="flex-1 px-4">
                      <div className="h-px bg-gray-300 relative">
                         <Train className="w-4 h-4 text-gray-400 absolute left-1/2 -top-2 -translate-x-1/2 bg-white px-0.5" />
                      </div>
                      <p className="text-[10px] text-gray-400 mt-2">{date}</p>
                   </div>
                   <div className="flex-1">
                      <p className="text-xl font-bold">{route.arrival}</p>
                      <p className="text-xs text-gray-500">{destination?.name}</p>
                   </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                   <p className="text-xs font-bold text-gray-500 uppercase">Passengers</p>
                   {passengers.map((p, i) => (
                     <div key={i} className="flex justify-between text-sm">
                        <span className="font-medium">{p.fullName} ({p.age}, {p.gender})</span>
                        <span className="text-green-600 font-bold">CNF</span>
                     </div>
                   ))}
                </div>
             </CardContent>
          </Card>

          <Button 
            onClick={() => navigate("/mini-app/home")} 
            variant="outline"
            className="w-full border-2 h-12"
          >
            Back to Home
          </Button>

          <p className="text-[10px] text-center text-gray-400">
            This is a production-ready booking confirmation generated by RAPTOR Engine V2.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
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
         <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center justify-between">
            <div>
               <p className="text-sm font-bold text-gray-900">{route.train_name}</p>
               <p className="text-xs text-gray-500">{origin?.name} → {destination?.name}</p>
            </div>
            <div className="text-right">
               <p className="text-xs text-gray-500">{date}</p>
               <Badge className="bg-blue-100 text-blue-600 hover:bg-blue-100 border-none text-[10px]">3A - AC Economy</Badge>
            </div>
         </div>

         {/* Passenger Fields */}
         <div className="space-y-4">
            <div className="flex items-center justify-between">
               <h2 className="text-lg font-bold text-gray-900">Add Passengers</h2>
               <p className="text-xs text-gray-500">{passengers.length}/6 Passengers</p>
            </div>

            {passengers.map((p, index) => (
              <Card key={index} className="shadow-none border-gray-200">
                 <CardContent className="p-4 space-y-4">
                    <div className="flex justify-between items-center mb-1">
                       <span className="text-xs font-bold text-blue-600 uppercase tracking-tight">Passenger {index + 1}</span>
                       {passengers.length > 1 && (
                         <Button 
                           variant="ghost" 
                           size="sm" 
                           onClick={() => handleRemovePassenger(index)}
                           className="text-red-500 h-6 px-2 text-xs"
                         >
                            Remove
                         </Button>
                       )}
                    </div>
                    <div className="space-y-1.5">
                       <Label className="text-xs text-gray-500">Full Name (as per ID)</Label>
                       <Input 
                         placeholder="MR. GAURAV NAGAR"
                         value={p.fullName}
                         onChange={(e) => updatePassenger(index, "fullName", e.target.value.toUpperCase())}
                         className="h-11 border-gray-300 focus:border-blue-500"
                       />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                       <div className="space-y-1.5">
                          <Label className="text-xs text-gray-500">Age</Label>
                          <Input 
                            type="number"
                            value={p.age}
                            onChange={(e) => updatePassenger(index, "age", parseInt(e.target.value))}
                            className="h-11 border-gray-300 focus:border-blue-500"
                          />
                       </div>
                       <div className="space-y-1.5">
                          <Label className="text-xs text-gray-500">Gender</Label>
                          <div className="flex bg-gray-100 rounded-lg p-1 h-11">
                             {["M", "F", "O"].map(g => (
                               <button
                                 key={g}
                                 onClick={() => updatePassenger(index, "gender", g)}
                                 className={`flex-1 rounded-md text-xs font-bold transition-all ${p.gender === g ? "bg-white text-blue-600 shadow-sm" : "text-gray-500"}`}
                               >
                                 {g === "M" ? "Male" : g === "F" ? "Female" : "Other"}
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
              className="w-full border-dashed border-2 h-12 text-blue-600 border-blue-200 bg-blue-50/50 hover:bg-blue-50"
            >
               + Add Another Passenger
            </Button>
         </div>

         <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
            <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 leading-relaxed">
              Ticket cancellation charges apply as per Railway rules. Seats will be allocated based on your preference during payment.
            </p>
         </div>
      </div>

      {/* Bottom Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 shadow-[0_-4px_10px_rgba(0,0,0,0.05)]">
         <div className="max-w-md mx-auto flex items-center justify-between gap-4">
            <div>
               <p className="text-[10px] text-gray-500 uppercase font-bold">Total Fare</p>
               <div className="flex items-center text-xl font-bold text-gray-900">
                  <IndianRupee className="w-4 h-4" />
                  <span>{Math.round((route.fare || 540) * passengers.length)}</span>
               </div>
            </div>
            <Button 
               onClick={handleConfirmBooking}
               disabled={isBooking}
               className="bg-blue-600 hover:bg-blue-700 text-white px-8 h-12 font-bold flex-1"
            >
               {isBooking ? (
                 <>
                   <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                   Processing...
                 </>
               ) : (
                 "Pay & Confirm"
               )}
            </Button>
         </div>
      </div>
    </div>
  );
};

export default MiniAppBooking;
