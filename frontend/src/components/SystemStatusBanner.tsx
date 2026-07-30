import { useSystemStatus } from "@/store/useSystemStatus";
import { AlertTriangle, Zap, ShieldAlert, X, WifiOff, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export function SystemStatusBanner() {
  const { surgeLevel, isOnline, maintenanceMode, retryAfter, scrapersPool, ledgerStatus, v3Core } = useSystemStatus();

  // ONLY show if there is a CRITICAL state (Offline, Maintenance, Surge) 
  // REMOVED: v3Core / Master Release info as it was pushing the layout too much
  const isVisible = !isOnline || surgeLevel === 'Critical' || maintenanceMode || retryAfter > 0;

  if (!isVisible && isOnline) return null;

  return (
    <AnimatePresence>
      <motion.div 
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: -50, opacity: 0 }}
        className={cn(
          "relative z-[200] px-4 py-2 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-white text-[10px] font-black uppercase tracking-widest transition-colors shadow-lg border-b",
          maintenanceMode ? "bg-amber-600/90 border-amber-500" :
          !isOnline ? "bg-orange-700/90 border-orange-600" :
          surgeLevel === 'Critical' ? "bg-red-600/90 border-red-500" : "bg-primary/95 border-primary/20 backdrop-blur-md"
        )}
      >
        <div className="flex items-center gap-2">
          {!isOnline ? <WifiOff className="w-3.5 h-3.5" /> : 
           maintenanceMode ? <ShieldAlert className="w-3.5 h-3.5" /> : 
           v3Core ? <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> : <Zap className="w-3.5 h-3.5 text-cyan-400" />}
          
          <span className="shrink-0">
            {!isOnline ? "Protocol Offline: Using Local Cache Only" :
             maintenanceMode ? "System Maintenance: v2.5 Deploy" :
             surgeLevel === 'Critical' ? "Critical Surge: Traffic Shaping" :
             "V3 Master Release Online"}
          </span>
        </div>

        {v3Core && isOnline && (
          <>
            <div className="hidden sm:block h-3 w-px bg-white/20" />
            <div className="flex items-center gap-2 opacity-80 hover:opacity-100 transition-opacity">
              <Zap className="w-3 h-3 text-cyan-300" />
              <span>Scraper Pool: <span className="text-white">{scrapersPool}</span></span>
            </div>
            <div className="hidden sm:block h-3 w-px bg-white/20" />
            <div className="flex items-center gap-2 opacity-80 hover:opacity-100 transition-opacity">
              <ShieldAlert className="w-3 h-3 text-emerald-400" />
              <span>Ledger: <span className="text-white">{ledgerStatus}</span></span>
            </div>
          </>
        )}

        {retryAfter > 0 && (
          <div className="px-2 py-0.5 bg-black/40 rounded-full font-mono text-cyan-400 animate-pulse border border-cyan-500/30">
            T-MINUS {retryAfter}S
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
