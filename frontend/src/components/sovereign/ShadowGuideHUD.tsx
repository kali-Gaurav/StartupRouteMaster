import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Info, TrendingUp, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ShadowGuideHUDProps {
  message: string;
  pressure?: number;
  level?: "LOW" | "MODERATE" | "HIGH" | "CRITICAL" | "OVERFLOW";
  isVisible: boolean;
}

export const ShadowGuideHUD: React.FC<ShadowGuideHUDProps> = ({
  message,
  pressure = 0,
  level = "LOW",
  isVisible
}) => {
  const getLevelColor = () => {
    switch (level) {
      case "CRITICAL":
      case "OVERFLOW":
        return "text-red-500 border-red-500/20 bg-red-500/5";
      case "HIGH":
        return "text-orange-500 border-orange-500/20 bg-orange-500/5";
      case "MODERATE":
        return "text-blue-500 border-blue-500/20 bg-blue-500/5";
      default:
        return "text-emerald-500 border-emerald-500/20 bg-emerald-500/5";
    }
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          className="mb-8 w-full"
        >
          <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-card p-6 shadow-2xl shadow-primary/5">
            {/* Background Glow */}
            <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/5 blur-3xl" />
            
            <div className="relative flex flex-col md:flex-row items-start gap-6">
              {/* Profile/Avatar Segment */}
              <div className="flex-shrink-0 flex flex-col items-center gap-2">
                <div className="relative h-16 w-16 rounded-full bg-gradient-to-br from-primary to-accent p-0.5 shadow-lg">
                  <div className="flex h-full w-full items-center justify-center rounded-full bg-card">
                    <Sparkles className="h-8 w-8 text-primary animate-pulse" />
                  </div>
                  {/* Status Indicator */}
                  <div className="absolute bottom-0 right-0 h-4 w-4 rounded-full border-2 border-card bg-emerald-500 shadow-sm" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Shadow-Guide</span>
              </div>

              {/* Content Segment */}
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <h3 className="text-lg font-bold text-foreground">Sovereign Guidance</h3>
                  <div className={cn(
                    "flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-tighter border",
                    getLevelColor()
                  )}>
                    {level === "OVERFLOW" || level === "CRITICAL" ? <AlertTriangle className="h-3 w-3" /> : <TrendingUp className="h-3 w-3" />}
                    Network Pressure: {level} ({Math.round(pressure * 100)}%)
                  </div>
                </div>
                
                <p className="text-sm md:text-base text-muted-foreground leading-relaxed italic">
                  "{message}"
                </p>

                <div className="mt-4 flex flex-wrap gap-4">
                  <div className="flex items-center gap-2 text-xs font-medium text-primary">
                    <Info className="h-3.5 w-3.5" />
                    <span>Real-time Nash Equilibrium optimization active</span>
                  </div>
                </div>
              </div>

              {/* Pulse Visualizer */}
              <div className="hidden lg:flex items-center gap-1 h-12">
                {[...Array(8)].map((_, i) => (
                  <motion.div
                    key={i}
                    animate={{
                      height: [10, 30, 10],
                    }}
                    transition={{
                      duration: 1 + Math.random(),
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                    className="w-1 rounded-full bg-primary/20"
                  />
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
