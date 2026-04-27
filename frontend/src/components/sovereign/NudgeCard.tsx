import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Zap, ArrowRight, DollarSign, Gift, CheckCircle, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface NudgeCardProps {
  type: string;
  headline: string;
  description: string;
  incentive: string;
  cta?: string;
  onClaim?: () => void;
}

export const NudgeCard: React.FC<NudgeCardProps> = ({
  type,
  headline,
  description,
  incentive,
  cta = "Claim Incentive & Book",
  onClaim
}) => {
  const [isClaimed, setIsClaimed] = useState(false);

  const handleClaim = () => {
    setIsClaimed(true);
    setTimeout(() => {
      onClaim?.();
    }, 1500);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="relative group"
    >
      <div className={cn(
        "relative overflow-hidden rounded-2xl border-2 transition-all duration-500 p-6",
        isClaimed 
          ? "border-emerald-500 bg-emerald-500/5 shadow-emerald-500/10" 
          : "border-primary/30 bg-gradient-to-br from-primary/5 to-accent/5 hover:border-primary shadow-xl shadow-primary/5"
      )}>
        {/* Particle Overlay for "Premium" feel */}
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-primary via-transparent to-transparent" />
        </div>

        <div className="relative flex flex-col md:flex-row items-center gap-6">
          {/* Incentive Badge */}
          <div className="flex-shrink-0">
            <div className={cn(
              "h-20 w-20 rounded-2xl flex flex-col items-center justify-center shadow-lg transition-transform group-hover:scale-105 duration-300",
              isClaimed ? "bg-emerald-500 text-white" : "bg-primary text-white"
            )}>
              <DollarSign className="h-8 w-8 mb-1" />
              <span className="text-sm font-black tracking-tighter">CLAIM</span>
            </div>
          </div>

          {/* Text Content */}
          <div className="flex-1 text-center md:text-left">
            <div className="flex flex-wrap items-center justify-center md:justify-start gap-2 mb-2">
              <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-black uppercase tracking-widest border border-primary/20">
                {type}
              </span>
              <div className="flex items-center gap-1 text-emerald-500 font-bold text-xs">
                <Gift className="h-3.5 w-3.5" />
                <span>Verified Benefit</span>
              </div>
            </div>
            
            <h4 className="text-xl font-black text-foreground mb-1 leading-tight">
              {headline}
            </h4>
            <p className="text-sm text-muted-foreground leading-snug">
              {description}
            </p>
          </div>

          {/* Pricing & CTA */}
          <div className="flex-shrink-0 w-full md:w-auto border-t md:border-t-0 md:border-l border-border/50 pt-4 md:pt-0 md:pl-6 flex flex-col items-center justify-center gap-3">
            <div className="text-center">
              <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground block mb-1">Redistribution Reward</span>
              <span className="text-3xl font-black text-emerald-500 tabular-nums">
                {incentive}
              </span>
            </div>

            <button
              onClick={handleClaim}
              disabled={isClaimed}
              className={cn(
                "relative overflow-hidden w-full px-6 py-3 rounded-xl font-black text-sm uppercase tracking-widest transition-all",
                isClaimed 
                  ? "bg-emerald-500 text-white cursor-default" 
                  : "bg-primary text-white shadow-lg shadow-primary/20 hover:scale-105 active:scale-95"
              )}
            >
              <AnimatePresence mode="wait">
                {isClaimed ? (
                  <motion.div
                    key="claimed"
                    initial={{ y: 20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="flex items-center justify-center gap-2"
                  >
                    <CheckCircle className="h-4 w-4" />
                    Reward Unlocked
                  </motion.div>
                ) : (
                  <motion.div
                    key="idle"
                    initial={{ y: -20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="flex items-center justify-center gap-2"
                  >
                    <Sparkles className="h-4 w-4" />
                    {cta}
                    <ArrowRight className="h-4 w-4" />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>
          </div>
        </div>

        {/* Incentive Animation Overlay */}
        <AnimatePresence>
          {isClaimed && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 pointer-events-none flex items-center justify-center"
            >
              {[...Array(12)].map((_, i) => (
                <motion.div
                  key={i}
                  initial={{ scale: 0, x: 0, y: 0 }}
                  animate={{
                    scale: [0, 1.5, 0],
                    x: (Math.random() - 0.5) * 300,
                    y: (Math.random() - 0.5) * 300,
                  }}
                  transition={{ duration: 1, ease: "easeOut" }}
                  className="absolute"
                >
                  <DollarSign className="text-emerald-500/40 h-8 w-8" />
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};
