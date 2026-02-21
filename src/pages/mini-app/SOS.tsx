import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertTriangle, Phone, ArrowLeft, Loader2, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "@/hooks/use-toast";

interface SOSType {
  id: string;
  label: string;
  icon: string;
  color: string;
  description: string;
}

const SOS_TYPES: SOSType[] = [
  {
    id: "medical",
    label: "Medical Emergency",
    icon: "🚑",
    color: "bg-red-100 border-red-300",
    description: "Need medical assistance"
  },
  {
    id: "police",
    label: "Police / Safety",
    icon: "🚨",
    color: "bg-blue-100 border-blue-300",
    description: "Report crime or safety issue"
  },
  {
    id: "fire",
    label: "Fire / Accident",
    icon: "🔥",
    color: "bg-orange-100 border-orange-300",
    description: "Fire or accident situation"
  },
  {
    id: "general",
    label: "General Help",
    icon: "🆘",
    color: "bg-yellow-100 border-yellow-300",
    description: "Other emergency assistance"
  }
];

const EMERGENCY_NUMBERS = {
  "112": "All India Emergency",
  "108": "Ambulance Service",
  "100": "Police",
  "101": "Fire Brigade"
};

const MiniAppSOS = () => {
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [sosInitiated, setSOSInitiated] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [hasLocationPermission, setHasLocationPermission] = useState(false);
  const [userLocation, setUserLocation] = useState<{ latitude: number; longitude: number } | null>(null);

  useEffect(() => {
    // Request location permission
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          });
          setHasLocationPermission(true);
        },
        (error) => {
          console.warn("Location access denied:", error);
          setHasLocationPermission(false);
        }
      );
    }
  }, []);

  const handleSOSSubmit = async () => {
    if (!selectedType) {
      toast({
        title: "Select Emergency Type",
        description: "Please select what type of help you need",
        variant: "destructive"
      });
      return;
    }

    setIsLoading(true);
    try {
      const sosData = {
        type: "SOS",
        emergency_type: selectedType,
        location: userLocation,
        timestamp: new Date().toISOString(),
        user_id: window.Telegram?.WebApp?.initDataUnsafe?.user?.id
      };

      // Send to Telegram bot
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.sendData(JSON.stringify(sosData));

        // Show success state
        setSOSInitiated(true);

        toast({
          title: "SOS Initiated ✓",
          description: "Emergency responders have been notified. Help is on the way.",
        });

        // Auto-navigate after success
        setTimeout(() => {
          navigate("/mini-app/home");
        }, 3000);
      }
    } catch (error) {
      console.error("SOS error:", error);
      toast({
        title: "Error",
        description: "Failed to send SOS. Calling emergency directly.",
        variant: "destructive"
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (sosInitiated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-100 p-4 flex items-center justify-center">
        <div className="max-w-md w-full">
          <Card className="shadow-2xl border-0">
            <CardContent className="p-8 text-center space-y-6">
              <div className="flex justify-center">
                <div className="rounded-full bg-green-100 p-6 animate-pulse">
                  <CheckCircle2 className="h-12 w-12 text-green-600" />
                </div>
              </div>

              <div className="space-y-2">
                <h2 className="text-2xl font-bold text-gray-900">Help is on the way!</h2>
                <p className="text-gray-600">Emergency responders have been notified with your location.</p>
              </div>

              <Alert className="bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">
                  <p className="font-semibold mb-2">🛡️ You are not alone</p>
                  <p className="text-sm">Emergency services are responding to your location. Stay safe and stay where you are if possible.</p>
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <p className="text-sm font-semibold text-gray-700">If you can, also call:</p>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(EMERGENCY_NUMBERS).map(([number]) => (
                    <Button
                      key={number}
                      variant="outline"
                      className="border-2"
                      onClick={() => {
                        const tel = `tel:${number}`;
                        window.location.href = tel;
                      }}
                    >
                      <Phone className="h-4 w-4 mr-2" />
                      {number}
                    </Button>
                  ))}
                </div>
              </div>

              <Button
                onClick={() => navigate("/mini-app/home")}
                className="w-full bg-green-600 hover:bg-green-700"
              >
                Return to Home
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-100 p-4">
      <div className="max-w-md mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/mini-app/home")}
            className="hover:bg-red-200"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Emergency SOS</h1>
            <p className="text-sm text-gray-600">Get immediate help</p>
          </div>
        </div>

        {/* Legal Disclaimer */}
        <Alert className="bg-red-50 border-red-300">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800 mt-2">
            <p className="font-semibold mb-2">⚠️ Important Notice</p>
            <p className="text-sm">
              This is NOT an official government emergency service. For life-threatening emergencies, immediately call <strong>112</strong>.
            </p>
            <div className="mt-3 space-y-1 text-sm">
              <p><strong>National Emergency Numbers (India):</strong></p>
              <p>🚑 108 - Ambulance</p>
              <p>🚨 100 - Police</p>
              <p>🔥 101 - Fire Brigade</p>
              <p>📞 112 - Universal Emergency (Best for life-threatening situations)</p>
            </div>
          </AlertDescription>
        </Alert>

        {/* Emergency Type Selection */}
        <Card className="shadow-lg border-0">
          <CardHeader>
            <CardTitle>Select Emergency Type</CardTitle>
            <CardDescription>What type of help do you need?</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {SOS_TYPES.map((sosType) => (
              <button
                key={sosType.id}
                onClick={() => setSelectedType(sosType.id)}
                className={`w-full p-4 rounded-lg border-2 transition-all ${
                  selectedType === sosType.id
                    ? "bg-white border-red-500 shadow-lg"
                    : "bg-white border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-start space-x-4">
                  <div className="text-3xl">{sosType.icon}</div>
                  <div className="flex-1 text-left">
                    <p className="font-semibold text-gray-900">{sosType.label}</p>
                    <p className="text-sm text-gray-600">{sosType.description}</p>
                  </div>
                  {selectedType === sosType.id && (
                    <div className="flex-shrink-0">
                      <Badge className="bg-red-600">Selected</Badge>
                    </div>
                  )}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Location Status */}
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-4">
            <div className="flex items-center space-x-3">
              <div className={`h-3 w-3 rounded-full ${hasLocationPermission ? 'bg-green-500' : 'bg-gray-300'}`} />
              <div>
                <p className="text-sm font-semibold text-gray-700">
                  {hasLocationPermission ? "📍 Location shared" : "📍 Location not available"}
                </p>
                <p className="text-xs text-gray-600">
                  {hasLocationPermission ? "Your coordinates will be sent to responders" : "Enable location for faster response"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Reassurance Message */}
        <Card className="bg-amber-50 border-amber-200">
          <CardContent className="pt-4">
            <p className="text-sm font-semibold text-amber-900 mb-2">🛡️ Your Safety is Our Priority</p>
            <p className="text-xs text-amber-800 leading-relaxed">
              By sending this SOS, you're enabling responders to locate you quickly. Your information will be shared with local emergency services and railway authorities.
            </p>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1 border-2"
            onClick={() => navigate("/mini-app/home")}
          >
            Cancel
          </Button>
          <Button
            onClick={() => setShowConfirm(true)}
            disabled={!selectedType || isLoading}
            className="flex-1 bg-red-600 hover:bg-red-700 text-white h-12 font-semibold"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Sending...
              </>
            ) : (
              "Send Emergency Alert"
            )}
          </Button>
        </div>

        {/* Final Confirmation Dialog */}
        {showConfirm && (
          <Card className="border-2 border-red-500 bg-white">
            <CardContent className="pt-6">
              <h3 className="text-lg font-bold text-gray-900 mb-2">Confirm Emergency Alert?</h3>
              <p className="text-sm text-gray-600 mb-4">
                Your location and emergency type will be immediately shared with responders.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setShowConfirm(false)}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                  onClick={handleSOSSubmit}
                >
                  Yes, Send SOS
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default MiniAppSOS;