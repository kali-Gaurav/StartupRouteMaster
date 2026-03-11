import { useState, useEffect, useRef } from "react";
import { AlertTriangle, X, ShieldAlert, MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { LocationService } from "@/lib/locationService";

export function SOSWidget() {
  const [isActive, setIsActive] = useState(false);
  const [countdown, setCountdown] = useState(10);
  const [isTriggered, setIsTriggered] = useState(false);
  const [longPressActive, setLongPressActive] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const pressTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 1. Long Press Logic (Prevent accidental triggers)
  const handlePressStart = () => {
    setLongPressActive(true);
    pressTimerRef.current = setTimeout(() => {
      setIsActive(true);
      setLongPressActive(false);
    }, 2000); // 2 second hold
  };

  const handlePressEnd = () => {
    if (pressTimerRef.current) clearTimeout(pressTimerRef.current);
    setLongPressActive(false);
  };

  // 2. Countdown Logic
  useEffect(() => {
    if (isActive && countdown > 0 && !isTriggered) {
      timerRef.current = setTimeout(() => setCountdown(c => c - 1), 1000);
    } else if (isActive && countdown === 0 && !isTriggered) {
      triggerSOS();
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isActive, countdown, isTriggered]);

  const [offlineDirectory, setOfflineDirectory] = useState<any[]>([]);
  const [showSMSFallback, setShowSMSFallback] = useState(false);

  // 1. Predictive Connectivity Buffer (Task 19)
  const syncOfflineDirectory = async (lat: number, lng: number) => {
    try {
      const res = await fetch(`/api/v2/live/dead-zone?lat=${lat}&lng=${lng}`);
      if (res.ok) {
        const data = await res.json();
        if (data.offline_directory) {
          setOfflineDirectory(data.offline_directory);
          // Subtask 19.3: Persistence
          localStorage.setItem('offline_emergency_directory', JSON.stringify(data.offline_directory));
        }
      }
    } catch (e) { console.error("Buffer sync failed", e); }
  };

  useEffect(() => {
    // Periodically sync directory if online
    if (navigator.onLine) {
      LocationService.requestLocation()
        .then((loc) => {
          if (loc) syncOfflineDirectory(loc.latitude, loc.longitude);
        })
        .catch((error) => {
          // Task 19: Gracefully handle location rejection
          // code 1 means PERMISSION_DENIED. We don't want to spam the console for a user choice.
          if (error.code !== 1) {
            console.warn("Location unavailable for offline directory sync:", error);
          }
        });
    }
  }, []);

  const [adminMessages, setAdminMessages] = useState<any[]>([]);
  const adminChatWs = useRef<WebSocket | null>(null);

  // 2. High-Priority Admin Chat Listener (Task 36)
  useEffect(() => {
    if (isTriggered && !adminChatWs.current) {
      const eventId = "current-sos-id"; // In real app, get from trigger response
      const wsUrl = `ws://${window.location.hostname}:8000/api/v2/ws/sos/chat/${eventId}`;
      adminChatWs.current = new WebSocket(wsUrl);

      adminChatWs.current.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "admin_chat" && payload.data.sender === "OPS_ADMIN") {
          setAdminMessages(prev => [...prev, payload.data]);
          // Optional: Trigger system beep or TTS
        }
      };
    }
    return () => adminChatWs.current?.close();
  }, [isTriggered]);

  const [isCovertMode, setIsCovertMode] = useState(false);

  const triggerSOS = async (mode: "normal" | "covert" = "normal") => {
    setIsTriggered(true);
    if (mode === "covert") setIsCovertMode(true);
    
    try {
      const loc = await LocationService.requestLocation();
      
      // Get chat history from session (if available)
      const session_id = localStorage.getItem('chat_session_id');
      let chatHistory = [];
      if (session_id) {
        const historyRes = await fetch(`/api/chat/history?session_id=${session_id}`);
        if (historyRes.ok) {
          const historyData = await historyRes.json();
          chatHistory = historyData.messages?.slice(-5) || [];
        }
      }

      if (loc) {
        const payload = {
          lat: loc.latitude,
          lng: loc.longitude,
          extra: "One-Tap Widget Triggered",
          chat_history: chatHistory
        };

        const res = await fetch("/api/sos/", {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "X-SOS-Priority": "true" 
          },
          body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Server failed");
      }
    } catch (err) {
      console.error("Failed to trigger SOS, suggesting SMS fallback:", err);
      setShowSMSFallback(true);
    }
  };

  const sendSMSFallback = async () => {
    const loc = await LocationService.requestLocation();
    const coords = loc ? `${loc.latitude},${loc.longitude}` : "Unknown Location";
    const body = `EMERGENCY SOS: Help requested at ${coords}. Track me at: https://www.google.com/maps/search/?api=1&query=${coords}`;
    // EMERGENCY_CONTACT_NUMBER should be fetched from user context
    const smsUri = `sms:?body=${encodeURIComponent(body)}`;
    window.location.href = smsUri;
  };

  const cancelSOS = () => {
    setIsActive(false);
    setCountdown(10);
    setIsTriggered(false);
  };

  if (isTriggered) {
    return (
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] w-[90%] max-w-md space-y-3">
        <div className="bg-red-600 text-white p-4 rounded-2xl shadow-2xl flex items-center gap-4 border-4 border-white animate-in slide-in-from-top-4">
          <ShieldAlert className="w-10 h-10" />
          <div>
            <div className="font-black text-lg uppercase">SOS ACTIVE</div>
            <div className="text-sm opacity-90">Responders are being dispatched.</div>
          </div>
        </div>

        {/* Admin Message Ticker */}
        {adminMessages.length > 0 && (
          <div className="bg-slate-900 text-white p-4 rounded-2xl shadow-xl border-2 border-primary animate-in zoom-in duration-300">
            <div className="flex items-center gap-2 mb-2 text-primary font-black text-[10px] uppercase tracking-widest">
              <MessageCircle className="w-3 h-3" /> Incoming Command
            </div>
            <div className="text-sm font-bold leading-tight italic">
              "{adminMessages[adminMessages.length - 1].content}"
            </div>
          </div>
        )}
      </div>
    );
  }

  if (isActive) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-6">
        <div className="bg-white dark:bg-muted rounded-3xl p-8 w-full max-w-sm text-center shadow-2xl animate-in zoom-in duration-300">
          <div className="w-24 h-24 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-12 h-12 text-red-600 animate-pulse" />
          </div>
          <h2 className="text-2xl font-black mb-2">Emergency SOS</h2>
          <p className="text-muted-foreground mb-8">Broadcasting your location in...</p>
          
          <div className="text-7xl font-black text-red-600 mb-10 tabular-nums">
            {countdown}
          </div>

          <button
            onClick={() => triggerSOS("covert")}
            className="w-full py-4 rounded-2xl bg-slate-900 text-white font-bold mb-3 shadow-lg flex items-center justify-center gap-2"
          >
            <ShieldAlert className="w-5 h-5 text-primary" />
            CAN'T TALK (COVERT MODE)
          </button>

          {showSMSFallback && (
            <button
              onClick={sendSMSFallback}
              className="w-full py-4 rounded-2xl bg-primary text-white font-black mb-3 shadow-lg flex items-center justify-center gap-2 animate-bounce"
            >
              <AlertTriangle className="w-5 h-5" />
              SEND SOS VIA SMS (OFFLINE)
            </button>
          )}

          <button
            onClick={cancelSOS}
            className="w-full py-4 rounded-2xl bg-muted hover:bg-muted/80 font-bold transition-colors flex items-center justify-center gap-2"
          >
            <X className="w-5 h-5" />
            CANCEL (I'M SAFE)
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-24 right-4 z-[90]">
      <div className="relative">
        {longPressActive && (
          <div className="absolute inset-0 rounded-full border-4 border-red-600 border-t-transparent animate-spin" />
        )}
        <button
          onMouseDown={handlePressStart}
          onMouseUp={handlePressEnd}
          onTouchStart={handlePressStart}
          onTouchEnd={handlePressEnd}
          className={cn(
            "w-16 h-16 rounded-full bg-red-600 text-white shadow-lg flex items-center justify-center transition-transform active:scale-90",
            longPressActive && "scale-110"
          )}
        >
          <AlertTriangle className="w-8 h-8" />
        </button>
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded whitespace-nowrap">
          HOLD FOR SOS
        </div>
      </div>
    </div>
  );
}
