import React from "react";
import { Wallet, Gift, Coffee, Star, ArrowUpRight, TrendingUp, Sparkles, Clock } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { formatCost } from "@/data/routes";

interface IncentiveItem {
  id: string;
  type: 'CASHBACK' | 'LOUNGE_ACCESS' | 'MEAL_VOUCHER' | 'UPGRADE';
  value: string;
  description: string;
  status: 'PENDING' | 'ACTIVE' | 'USED';
  date: string;
}

const MOCK_INCENTIVES: IncentiveItem[] = [
  {
    id: "1",
    type: "CASHBACK",
    value: "₹150",
    description: "Network Load Contribution: NDLS-HWH Corridor",
    status: "ACTIVE",
    date: "2024-04-20"
  },
  {
    id: "2",
    type: "LOUNGE_ACCESS",
    value: "Executive Lounge",
    description: "Premium Transit Benefit - New Delhi Station",
    status: "ACTIVE",
    date: "2024-04-18"
  },
  {
    id: "3",
    type: "MEAL_VOUCHER",
    value: "₹200",
    description: "IRCTC Catering Voucher",
    status: "USED",
    date: "2024-04-10"
  }
];

export function IncentiveWallet() {
  const activeCount = MOCK_INCENTIVES.filter(i => i.status === 'ACTIVE').length;
  const totalSaved = 350; // Mock total

  return (
    <div className="w-full max-w-md bg-card rounded-2xl border border-border shadow-xl overflow-hidden animate-in fade-in zoom-in duration-300">
      {/* Header: Premium Gradient */}
      <div className="p-6 bg-gradient-to-br from-primary/20 via-primary/5 to-transparent border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Wallet className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-foreground leading-none">Incentive Wallet</h3>
              <p className="text-xs text-muted-foreground mt-1 font-medium">Patent-Pending Reward Engine</p>
            </div>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[10px] font-black uppercase tracking-widest text-primary/60">Elite Tier</span>
            <div className="flex items-center gap-1 mt-1">
              {[1, 2, 3, 4, 5].map(i => <Star key={i} className="w-2.5 h-2.5 fill-primary text-primary" />)}
            </div>
          </div>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-semibold uppercase tracking-tighter">Total Network Credits</p>
            <div className="text-3xl font-black text-foreground mt-1 flex items-baseline gap-1">
              {formatCost(totalSaved)}
              <TrendingUp className="w-4 h-4 text-emerald-500" />
            </div>
          </div>
          <div className="bg-background/50 backdrop-blur-sm px-3 py-1.5 rounded-lg border border-border flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold text-foreground">{activeCount} Active Perks</span>
          </div>
        </div>
      </div>

      {/* Perks List */}
      <div className="p-4 space-y-3">
        <div className="text-xs font-black uppercase tracking-widest text-muted-foreground flex items-center gap-2 mb-2">
          <Sparkles className="w-3 h-3" /> Active Benefits
        </div>
        
        {MOCK_INCENTIVES.filter(i => i.status === 'ACTIVE').map((perk, i) => (
          <motion.div 
            key={perk.id}
            initial={{ x: -20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: i * 0.1 }}
            className="group relative flex items-center gap-3 p-3 rounded-xl bg-secondary/30 border border-border hover:border-primary/30 transition-all cursor-pointer"
          >
            <div className="w-10 h-10 rounded-lg bg-background flex items-center justify-center border border-border shadow-sm group-hover:shadow-md transition-all">
              {perk.type === 'CASHBACK' && <Gift className="w-5 h-5 text-emerald-500" />}
              {perk.type === 'LOUNGE_ACCESS' && <Coffee className="w-5 h-5 text-amber-500" />}
              {perk.type === 'MEAL_VOUCHER' && <Sparkles className="w-5 h-5 text-blue-500" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-foreground leading-none">{perk.value}</span>
                <span className="text-[10px] text-muted-foreground font-medium">{perk.date}</span>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1 truncate">{perk.description}</p>
            </div>
            <ArrowUpRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </motion.div>
        ))}

        <div className="pt-2">
          <button className="w-full py-2.5 rounded-xl bg-secondary text-secondary-foreground text-xs font-black uppercase tracking-widest hover:bg-secondary/80 transition-colors border border-border">
            View Contribution History
          </button>
        </div>
      </div>

      {/* Footer / Meta */}
      <div className="p-4 bg-secondary/10 border-t border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground font-medium">Auto-refreshes with DemandForecaster™</span>
        </div>
        <button className="text-[10px] font-black text-primary uppercase hover:underline decoration-2 underline-offset-4">
          How it works?
        </button>
      </div>
    </div>
  );
}
