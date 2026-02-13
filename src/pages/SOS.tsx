/**
 * Safe Journey SOS - Passenger page
 * Integrated with real user authentication and location
 * Shares real-time location until trip ends
 */
import { useState, useEffect, useRef } from "react";
import { MapPin, ShieldAlert, Loader2, CheckCircle, LogIn } from "lucide-react";
import { triggerSOS, sendLocationUpdate, endTrip } from "@/services/sosApi";
import { useAuth } from "@/context/AuthContext";
import { AuthModal } from "@/components/AuthModal";
import { LocationPrompt } from "@/components/LocationPrompt";
import { LocationService } from "@/lib/locationService";

export default function SOSPage() {
  const { user, isAuthenticated, token } = useAuth();
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [eventId, setEventId] = useState<string | null>(null);
  const [tripEnded, setTripEnded] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showLocationPrompt, setShowLocationPrompt] = useState(false);
  const locationIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Check authentication first
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    // Check location
    if (!navigator.geolocation) {
      setLocationError("Location not supported in this browser.");
      setLoading(false);
      return;
    }

    // Get current location
    LocationService.requestLocation()
      .then((loc) => {
        setLocation({ lat: loc.latitude, lng: loc.longitude });
        setLocationError(null);
        
        // Update server location
        if (token) {
          LocationService.updateServerLocation(loc);
        }
        
        setLoading(false);
      })
      .catch((err) => {
        setLocationError(err.message || "Could not get location.");
        setLoading(false);
      });
  }, [isAuthenticated, token]);

  const handleSOS = async () => {
    if (!location || sending || !isAuthenticated || !user) return;
    
    setSending(true);
    try {
      // Send SOS with real user data
      const res = await triggerSOS({
        lat: location.lat,
        lng: location.lng,
        name: `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'User',
        phone: user.phone || '',
        email: user.email || '',
        trip: {
          origin: 'Current Location',
          destination: 'Unknown',
          mode: 'Unknown',
          vehicle_number: '',
          driver_name: '',
          boarding_time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
          eta: 'N/A',
        },
      });
      
      setEventId(res.id);
      setSent(true);
      
      // Start location tracking
      LocationService.startWatching(
        async (loc) => {
          try {
            await sendLocationUpdate(res.id, loc.latitude, loc.longitude);
            
            // Also update server
            if (token) {
              await LocationService.updateServerLocation(loc);
            }
          } catch (err) {
            console.error('Location update failed:', err);
          }
        },
        (error) => {
          console.error('Location watch error:', error);
        }
      );
    } catch (err: any) {
      setLocationError(err.message || "Failed to send SOS. Check connection.");
    } finally {
      setSending(false);
    }
  };

  const handleEndTrip = async () => {
    if (!eventId) return;
    try {
      // Stop location watching
      LocationService.stopWatching();
      
      if (locationIntervalRef.current) {
        clearInterval(locationIntervalRef.current);
        locationIntervalRef.current = null;
      }
      
      await endTrip(eventId);
      setTripEnded(true);
    } catch (err: any) {
      setLocationError(err.message || "Failed to end trip.");
    }
  };

  useEffect(() => {
    return () => {
      LocationService.stopWatching();
      if (locationIntervalRef.current) {
        clearInterval(locationIntervalRef.current);
      }
    };
  }, []);

  // Show auth modal if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
        <ShieldAlert className="w-16 h-16 text-primary mb-4" />
        <h1 className="text-2xl font-bold text-center">Login Required</h1>
        <p className="mt-2 text-center text-muted-foreground max-w-sm">
          Please login to use emergency SOS features
        </p>
        <button
          onClick={() => setShowAuthModal(true)}
          className="mt-6 px-6 py-3 bg-primary text-white rounded-lg font-semibold hover:bg-primary/90 transition-colors flex items-center gap-2"
        >
          <LogIn className="w-5 h-5" />
          Login to Continue
        </button>
        <a href="/" className="mt-8 text-sm text-primary hover:underline">
          ← Back to home
        </a>
        
        <AuthModal
          open={showAuthModal}
          onClose={() => setShowAuthModal(false)}
          onSuccess={() => {
            setShowAuthModal(false);
            setLoading(true);
          }}
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
        <Loader2 className="w-12 h-12 animate-spin text-primary" />
        <p className="mt-4 text-muted-foreground">Getting your location...</p>
      </div>
    );
  }

  if (locationError && !location) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
        <ShieldAlert className="w-16 h-16 text-destructive mb-4" />
        <h1 className="text-xl font-bold text-center">Location Required</h1>
        <p className="mt-2 text-center text-muted-foreground max-w-sm">{locationError}</p>
        <p className="mt-4 text-sm text-muted-foreground">Please allow location access and refresh.</p>
      </div>
    );
  }

  if (tripEnded) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
        <CheckCircle className="w-20 h-20 text-green-500 mb-4" />
        <h1 className="text-2xl font-bold text-center">You're safe</h1>
        <p className="mt-2 text-center text-muted-foreground max-w-sm">
          Trip ended. Location sharing stopped. Thank you for using Safe Journey.
        </p>
        <a href="/" className="mt-8 text-sm text-primary hover:underline">← Back to home</a>
      </div>
    );
  }

  if (sent) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
        <div className="flex items-center gap-2 text-green-500 mb-4">
          <span className="relative flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500" />
          </span>
          <span className="font-medium">Sharing location</span>
        </div>
        <h1 className="text-2xl font-bold text-center">Help is on the way</h1>
        <p className="mt-2 text-center text-muted-foreground max-w-sm">
          Your live location is being shared until you tap &quot;I&apos;m Safe&quot;. Our team can see you on the map.
        </p>
        <button
          onClick={handleEndTrip}
          className="mt-8 px-8 py-4 rounded-xl bg-green-500 text-white font-bold hover:bg-green-600 transition-colors"
        >
          I&apos;m Safe — End Trip
        </button>
        <a href="/" className="mt-6 text-sm text-muted-foreground hover:text-foreground">← Back to home</a>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6">
      <div className="flex flex-col items-center max-w-md w-full">
        <div className="flex items-center gap-2 text-primary mb-6">
          <ShieldAlert className="w-8 h-8" />
          <h1 className="text-2xl font-bold">Safe Journey</h1>
        </div>

        {location && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
            <MapPin className="w-4 h-4 text-green-500" />
            <span>
              Location ready: {location.lat.toFixed(5)}, {location.lng.toFixed(5)}
            </span>
          </div>
        )}

        <p className="text-center text-muted-foreground mb-8">
          Press the button below if you need immediate help. Your live location will be shared.
        </p>

        <button
          onClick={handleSOS}
          disabled={sending || !location}
          className={`
            w-48 h-48 rounded-full text-white font-bold text-xl
            flex items-center justify-center
            transition-all duration-200
            ${sending ? "opacity-70 cursor-not-allowed" : "hover:scale-105 active:scale-95"}
            bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/30
          `}
        >
          {sending ? (
            <Loader2 className="w-12 h-12 animate-spin" />
          ) : (
            <>SOS</>
          )}
        </button>

        {user && (
          <div className="mt-6 p-4 bg-muted/50 rounded-lg text-sm text-muted-foreground text-center">
            <p className="font-medium">Logged in as:</p>
            <p className="mt-1">
              {user.first_name || user.last_name 
                ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                : user.phone || user.email}
            </p>
          </div>
        )}

        <a href="/" className="mt-8 text-sm text-primary hover:underline">
          ← Back to home
        </a>
      </div>
      
      <LocationPrompt
        open={showLocationPrompt}
        onClose={() => setShowLocationPrompt(false)}
        reason="sos"
      />
    </div>
  );
}
