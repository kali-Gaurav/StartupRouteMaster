/**
 * Safe Journey SOS - Advanced Passenger Safety System
 * Dual Mode: High-Intensity Emergency (SOS) & Proactive Safety Shield.
 * Integrated with real-time geolocation telemetry and Supabase Auth.
 */
import { useState, useEffect } from "react";
import { 
  MapPin, ShieldAlert, Loader2, CheckCircle, LogIn, 
  ShieldCheck, Navigation, Zap,
  X, PhoneCall, Volume2, VolumeX, Heart, Bell, BellOff
} from "lucide-react";
import { triggerSOS, sendLocationUpdate, endTrip } from "@/services/sosApi";
import { useAuth } from "@/context/AuthContext";
import { AuthModal } from "@/components/AuthModal";
import { LocationService } from "@/lib/locationService";
import { voiceService } from "@/services/voiceService";
import { usePushNotifications } from "@/hooks/usePushNotifications";
import { cn } from "@/lib/utils";

export default function SOSPage() {
  const { user, isAuthenticated, session } = useAuth();
  const { isSubscribed, subscribeUser, unsubscribeUser } = usePushNotifications();
  const token = session?.access_token;
  
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [isShieldActive, setIsShieldActive] = useState(false);
  const [isGuardianActive, setIsGuardianActive] = useState(false); // Added Journey Guardian state
  const [sent, setSent] = useState(false);
  const [eventId, setEventId] = useState<string | null>(null);
  const [tripEnded, setTripEnded] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [activeTab, setActiveTab] = useState<'emergency' | 'shield'>('emergency');
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  // Load initial location
  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    if (!navigator.geolocation) {
      setLocationError("Precision GPS not supported by hardware.");
      setLoading(false);
      return;
    }

    LocationService.requestLocation()
      .then((loc) => {
        if (loc) {
          setLocation({ lat: loc.latitude, lng: loc.longitude });
          setLocationError(null);
          if (token) LocationService.updateServerLocation(loc);
        }
        setLoading(false);
      })
      .catch((err: Error) => {
        setLocationError(err.message || "Precision GPS acquisition failed.");
        setLoading(false);
      });
  }, [isAuthenticated, token]);

  const startTracking = async (priority: 'high' | 'standard' | 'guardian' = 'high') => {
    if (!location || sending || !isAuthenticated || !user) return;
    
    setSending(true);
    try {
      const res = await triggerSOS({
        lat: location.lat,
        lng: location.lng,
        name: `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email || 'Anonymous',
        phone: user.phone || '',
        email: user.email || '',
        extra: priority === 'high' ? 'EMERGENCY_TRIGGER' : (priority === 'guardian' ? 'JOURNEY_GUARDIAN_ACTIVE' : 'SAFETY_SHIELD_ACTIVE'),
        trip: {
          origin: 'Real-time Telemetry',
          mode: priority === 'high' ? 'EMERGENCY' : (priority === 'guardian' ? 'GUARDIAN' : 'SHIELD'),
          boarding_time: new Date().toISOString(),
        },
      });
      
      setEventId(res.id);
      if (priority === 'high') {
        setSent(true);
        if (voiceEnabled) voiceService.speak("sos_triggered");
      } else if (priority === 'guardian') {
        setIsGuardianActive(true);
        if (voiceEnabled) voiceService.speak("guardian_active");
      } else {
        setIsShieldActive(true);
        if (voiceEnabled) voiceService.speak("shield_active");
      }
      
      LocationService.startWatching(
        async (loc) => {
          try {
            await sendLocationUpdate(res.id, loc.latitude, loc.longitude);
            if (token) await LocationService.updateServerLocation(loc);
          } catch (err) {
            console.error('Telemetry uplink failed:', err);
          }
        }
      );
    } catch (err: any) {
      setLocationError(err.message || "Uplink synchronization failed.");
    } finally {
      setSending(false);
    }
  };

  const handleEndTrip = async () => {
    if (!eventId) return;
    try {
      LocationService.stopWatching();
      await endTrip(eventId);
      setTripEnded(true);
      setIsShieldActive(false);
      setIsGuardianActive(false);
      setSent(false);
      if (voiceEnabled) voiceService.speak("trip_ended");
    } catch (err: any) {
      console.error("Trip decommissioning failed", err);
    }
  };

  const toggleVoice = () => {
    const newVal = !voiceEnabled;
    setVoiceEnabled(newVal);
    voiceService.setEnabled(newVal);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center justify-center p-8">
        <ShieldAlert className="w-20 h-20 text-red-500 mb-6 animate-pulse" />
        <h1 className="text-3xl font-black uppercase tracking-tighter text-center">Safety Uplink Required</h1>
        <p className="mt-4 text-center text-slate-400 max-w-sm font-medium">
          Real-time protection and SOS features require a verified secure session.
        </p>
        <button
          onClick={() => setShowAuthModal(true)}
          className="mt-10 w-full max-w-xs py-4 bg-white text-[#0f172a] rounded-2xl font-black uppercase tracking-widest hover:bg-slate-200 transition-all active:scale-95 flex items-center justify-center gap-3"
          aria-label="Secure Login for Safety Access"
        >
          <LogIn className="w-5 h-5" />
          Secure Login
        </button>
        <a href="/" className="mt-8 text-sm font-bold text-slate-500 hover:text-white transition-colors uppercase tracking-widest">
          ← Terminal Home
        </a>
        <AuthModal open={showAuthModal} onClose={() => setShowAuthModal(false)} />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] text-white flex flex-col items-center justify-center">
        <Loader2 className="w-16 h-16 animate-spin text-blue-500 mb-4" />
        <p className="font-mono text-xs uppercase tracking-widest text-slate-500">Acquiring Satellites...</p>
      </div>
    );
  }

  if (tripEnded) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8">
        <div className="w-24 h-24 bg-green-100 rounded-full flex items-center justify-center mb-6">
          <CheckCircle className="w-12 h-12 text-green-600" />
        </div>
        <h1 className="text-3xl font-black uppercase tracking-tighter text-slate-900">Session Secure</h1>
        <p className="mt-2 text-center text-slate-500 max-w-sm">
          Location sharing has been decommissioned. You are marked as safe.
        </p>
        <button 
          onClick={() => window.location.href = "/"}
          className="mt-10 px-10 py-4 bg-[#0f172a] text-white rounded-2xl font-black uppercase tracking-widest hover:opacity-90 active:scale-95 transition-all"
          aria-label="Return to Dashboard"
        >
          Return to Hub
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f172a] text-white selection:bg-red-500/30">
      <div className="container mx-auto max-w-md min-h-screen flex flex-col p-6">
        {/* Header */}
        <header className="flex items-center justify-between py-4 mb-8">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <span className="font-black uppercase tracking-widest text-sm">SafeGuard Hub</span>
          </div>
          <div className="flex items-center gap-2">
            <button 
              onClick={isSubscribed ? unsubscribeUser : subscribeUser}
              className={cn("p-2 rounded-full transition-colors", isSubscribed ? "text-emerald-500 bg-emerald-500/10" : "text-slate-400 hover:bg-slate-800")}
              aria-label={isSubscribed ? "Disable Safety Notifications" : "Enable Safety Notifications"}
            >
              {isSubscribed ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
            </button>
            <button 
              onClick={toggleVoice} 
              className="p-2 hover:bg-slate-800 rounded-full transition-colors text-slate-400"
              aria-label={voiceEnabled ? "Mute Voice Feedback" : "Enable Voice Feedback"}
            >
              {voiceEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
            </button>
            <button 
              onClick={() => window.history.back()} 
              className="p-2 hover:bg-slate-800 rounded-full transition-colors"
              aria-label="Go Back"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </header>

        {/* Dynamic Tab Switcher */}
        {!sent && !isShieldActive && !isGuardianActive && (
          <div className="bg-slate-900/50 p-1.5 rounded-2xl flex gap-1 border border-slate-800 mb-10">
            <button 
              onClick={() => setActiveTab('emergency')}
              className={cn(
                "flex-1 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all",
                activeTab === 'emergency' ? "bg-red-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-300"
              )}
              aria-pressed={activeTab === 'emergency'}
            >
              Emergency
            </button>
            <button 
              onClick={() => setActiveTab('shield')}
              className={cn(
                "flex-1 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all",
                activeTab === 'shield' ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-300"
              )}
              aria-pressed={activeTab === 'shield'}
            >
              Safety Shield
            </button>
          </div>
        )}

        {/* Tracking Active View */}
        {(sent || isShieldActive || isGuardianActive) ? (
          <div className="flex-1 flex flex-col items-center justify-center py-10 animate-in fade-in zoom-in duration-500">
            <div className="relative mb-12">
              <div className={cn(
                "w-48 h-48 rounded-full flex items-center justify-center border-4 relative z-10",
                sent ? "border-red-500/20" : isGuardianActive ? "border-emerald-500/20" : "border-blue-500/20"
              )}>
                <div className={cn(
                  "w-36 h-36 rounded-full flex items-center justify-center animate-pulse",
                  sent ? "bg-red-600 shadow-[0_0_60px_rgba(220,38,38,0.5)]" : 
                  isGuardianActive ? "bg-emerald-600 shadow-[0_0_60px_rgba(16,185,129,0.5)]" : 
                  "bg-blue-600 shadow-[0_0_60px_rgba(37,99,235,0.5)]"
                )}>
                  {sent ? <ShieldAlert className="w-16 h-16" /> : 
                   isGuardianActive ? <Heart className="w-16 h-16" /> : 
                   <ShieldCheck className="w-16 h-16" />}
                </div>
              </div>
              <div className={cn(
                "absolute inset-0 rounded-full animate-ping opacity-20",
                sent ? "bg-red-500" : isGuardianActive ? "bg-emerald-500" : "bg-blue-500"
              )} />
            </div>

            <div className="text-center space-y-4">
              <h2 className="text-3xl font-black uppercase tracking-tighter">
                {sent ? "Active Emergency" : isGuardianActive ? "Guardian Mode" : "Shield Active"}
              </h2>
              <p className="text-slate-400 text-sm font-medium leading-relaxed max-w-xs mx-auto">
                {sent 
                  ? "Distress signal broadcasted. Railway Police and medical responders have your coordinates."
                  : isGuardianActive ? "AI risk detection active. Family is receiving live updates and alerts." : 
                  "Continuous telemetry active. Your location is being monitored by our security engine."}
              </p>
            </div>

            <div className="mt-12 w-full space-y-4">
              <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-5 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-slate-800 rounded-xl flex items-center justify-center">
                    <Navigation className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-[10px] font-black uppercase text-slate-500">Current Fix</p>
                    <p className="text-xs font-mono tabular-nums">{location?.lat.toFixed(5)}, {location?.lng.toFixed(5)}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end">
                  <p className="text-[10px] font-black uppercase text-green-500 flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-green-500 animate-pulse" />
                    LIVE_FEED
                  </p>
                </div>
              </div>

              <button
                onClick={handleEndTrip}
                className="w-full py-5 bg-white text-[#0f172a] rounded-2xl font-black uppercase tracking-widest hover:opacity-90 active:scale-95 transition-all shadow-xl"
                aria-label="Deactivate Tracking - I am Safe"
              >
                I am Safe - End Session
              </button>
              
              {(sent || isGuardianActive) && (
                <button className="w-full py-4 border-2 border-red-600 text-red-500 rounded-2xl font-black uppercase tracking-widest flex items-center justify-center gap-3 hover:bg-red-600/10 transition-colors" aria-label="Immediately Call Rail Police">
                  <PhoneCall className="w-5 h-5" />
                  Call Rail Police
                </button>
              )}
            </div>
          </div>
        ) : (
          /* Initial Activation View */
          <div className="flex-1 flex flex-col py-4 animate-in slide-in-from-bottom-4 duration-500">
            {activeTab === 'emergency' ? (
              <div className="space-y-10">
                <div className="space-y-4">
                  <h2 className="text-5xl font-black uppercase tracking-tighter leading-none italic">
                    Critical<br />
                    Response
                  </h2>
                  <p className="text-slate-400 font-medium">Use only in case of immediate danger, theft, or medical emergency.</p>
                </div>

                <div className="flex flex-col items-center">
                  <button
                    onClick={() => startTracking('high')}
                    disabled={sending || !location}
                    className="group relative"
                    aria-label="Activate SOS Emergency Distress Signal"
                  >
                    <div className="absolute inset-0 bg-red-600 rounded-full blur-3xl opacity-20 group-hover:opacity-40 transition-opacity" />
                    <div className="w-64 h-64 rounded-full bg-red-600 flex flex-col items-center justify-center shadow-[0_0_100px_rgba(220,38,38,0.4)] relative z-10 active:scale-95 transition-transform hover:scale-105 border-8 border-white/10">
                      {sending ? <Loader2 className="w-16 h-16 animate-spin" /> : (
                        <>
                          <Zap className="w-12 h-12 mb-2 fill-current" />
                          <span className="text-4xl font-black uppercase tracking-widest italic">SOS</span>
                        </>
                      )}
                    </div>
                  </button>
                  <p className="mt-8 text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Press to signal</p>
                </div>
              </div>
            ) : (
              <div className="space-y-10">
                <div className="space-y-4">
                  <h2 className="text-5xl font-black uppercase tracking-tighter leading-none italic text-blue-500">
                    Proactive<br />
                    Shield
                  </h2>
                  <p className="text-slate-400 font-medium">Share your journey live with our ops center. Perfect for late-night travel.</p>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 space-y-6">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-blue-600/20 rounded-2xl flex items-center justify-center">
                        <ShieldCheck className="w-6 h-6 text-blue-500" />
                      </div>
                      <div>
                        <h4 className="font-black uppercase text-xs tracking-widest">Active Monitoring</h4>
                        <p className="text-slate-500 text-[10px] font-medium uppercase">Ops Center Linkage</p>
                      </div>
                    </div>
                    
                    <ul className="space-y-3">
                      <li className="flex items-center gap-3 text-xs font-bold text-slate-300 uppercase tracking-tight">
                        <CheckCircle className="w-4 h-4 text-green-500" /> 15s Location Polling
                      </li>
                      <li className="flex items-center gap-3 text-xs font-bold text-slate-300 uppercase tracking-tight">
                        <CheckCircle className="w-4 h-4 text-green-500" /> Automated Route Deviant Alert
                      </li>
                    </ul>

                    <button
                      onClick={() => startTracking('standard')}
                      disabled={sending || !location}
                      className="w-full py-4 bg-blue-600 text-white rounded-2xl font-black uppercase tracking-widest hover:bg-blue-700 transition-all active:scale-95 shadow-lg shadow-blue-600/20"
                      aria-label="Activate Proactive Safety Shield"
                    >
                      {sending ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : "Activate Shield"}
                    </button>
                  </div>

                  {/* Journey Guardian Mode */}
                  <div className="bg-emerald-950/30 border-2 border-emerald-500/30 rounded-3xl p-6 space-y-5 relative overflow-hidden group transition-all hover:bg-emerald-900/40">
                    <div className="absolute -top-6 -right-6 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <Heart className="w-24 h-24 text-emerald-500" />
                    </div>
                    
                    <div className="flex items-center gap-4 relative z-10">
                      <div className="w-12 h-12 bg-emerald-500 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
                        <Heart className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                           <h4 className="font-black uppercase text-xs tracking-widest text-emerald-500">Journey Guardian</h4>
                           <span className="px-1.5 py-0.5 rounded bg-emerald-500 text-[8px] font-black text-white uppercase tracking-tighter">Elite</span>
                        </div>
                        <p className="text-slate-500 text-[10px] font-medium uppercase">Travel Alone - Never Alone</p>
                      </div>
                    </div>
                    
                    <div className="space-y-4 relative z-10">
                      <p className="text-[11px] text-slate-300 font-medium leading-relaxed">
                        AI risk detection + automated family alerts. Our most advanced protection for solo travelers.
                      </p>
                    </div>

                    <button
                      onClick={() => startTracking('guardian')}
                      disabled={sending || !location}
                      className="w-full py-5 bg-emerald-600 text-white rounded-2xl font-black uppercase tracking-widest hover:bg-emerald-700 transition-all active:scale-95 shadow-xl shadow-emerald-600/20 relative z-10"
                      aria-label="Activate Journey Guardian Mode"
                    >
                      {sending ? <Loader2 className="w-6 h-6 animate-spin mx-auto" /> : "Enable Guardian"}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer Info */}
        {!sent && !isShieldActive && (
          <footer className="mt-auto py-6 border-t border-slate-800/50">
            <div className="flex items-center gap-4 text-slate-500">
              <MapPin className="w-4 h-4" />
              <div className="flex-1">
                <p className="text-[10px] font-black uppercase tracking-widest mb-0.5">Verified Station</p>
                <p className="text-xs font-mono">{locationError || (location ? `FIX_LAT:${location.lat.toFixed(4)} FIX_LNG:${location.lng.toFixed(4)}` : "ACQUIRING_GPS...")}</p>
              </div>
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}
