import { useSystemStatus } from "@/store/useSystemStatus";
import { AlertTriangle, Zap, ShieldAlert, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export function SystemStatusBanner() {
  const { surgeLevel, isOnline, maintenanceMode, retryAfter, setSystemStatus } = useSystemStatus();

  const isVisible = !isOnline || surgeLevel === 'Critical' || maintenanceMode || retryAfter > 0;

  if (!isVisible) return null;

  return (
    <AnimatePresence>
      <motion.div 
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -50, opacity: 0 }}
        className={cn(
          "fixed top-0 left-0 right-0 z-[200] px-4 py-2 flex items-center justify-center gap-3 backdrop-blur-md border-b text-white text-xs font-bold uppercase tracking-widest transition-colors shadow-lg",
          maintenanceMode ? "bg-amber-600/90 border-amber-500" :
          !isOnline ? "bg-red-700/90 border-red-600" :
          surgeLevel === 'Critical' ? "bg-red-600/90 border-red-500" : "bg-blue-600/90 border-blue-500"
        )}
      >
        {!isOnline ? <Zap className="w-4 h-4 animate-pulse" /> : 
         maintenanceMode ? <ShieldAlert className="w-4 h-4" /> : 
         <AlertTriangle className="w-4 h-4 animate-bounce" />}
        
        <span>
          {!isOnline ? "Protocol Disconnected: Re-establishing Neural Link..." :
           maintenanceMode ? "System Maintenance: Protocol v2.5 Deployment in Progress" :
           surgeLevel === 'Critical' ? "Critical Surge: Traffic Shaping Active (Priority SOS Only)" :
           `Network Latency Detected: Systems Optimizing...`}
        </span>

        {retryAfter > 0 && (
          <div className="ml-2 px-2 py-0.5 bg-black/30 rounded-full font-mono">
            T-MINUS {retryAfter}S
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
