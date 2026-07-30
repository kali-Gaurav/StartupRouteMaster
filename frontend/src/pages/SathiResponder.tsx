import React, { useState, useEffect } from 'react';
import { Shield, MapPin, Zap, ArrowRight, ShieldCheck, AlertCircle, Phone, Navigation, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

export default function SathiResponder() {
  const [activeIncident, setActiveIncident] = useState<any>(null);
  const [status, setStatus] = useState<'idle' | 'en_route' | 'on_site'>('idle');

  // Simulated live incident reception
  useEffect(() => {
    const timer = setTimeout(() => {
      setActiveIncident({
        id: "INC_9921",
        user: "Passenger #402",
        type: "Emergency SOS",
        location: "Platform 4, New Delhi Station",
        distance: "150m",
        eta: "2 mins",
        priority: "CRITICAL"
      });
    }, 5000);
    return () => clearTimeout(timer);
  }, []);

  const handleAccept = () => {
    setStatus('en_route');
    // In production, this would call /api/v2/sathi/dispatch/accept
  };

  const handleResolve = () => {
    setActiveIncident(null);
    setStatus('idle');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500 rounded-xl">
             <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black uppercase tracking-tighter">Responder Control</h1>
            <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-bold uppercase tracking-widest">
               <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
               Live & Online
            </div>
          </div>
        </div>
        <div className="text-right">
           <div className="text-[10px] opacity-40 font-black uppercase">Rating</div>
           <div className="text-lg font-black italic text-emerald-400">4.9 ★</div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {!activeIncident ? (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="flex-1 flex flex-col items-center justify-center py-20 text-center"
          >
            <div className="w-32 h-32 bg-slate-900 rounded-full flex items-center justify-center mb-6 border border-white/5">
               <Zap className="w-12 h-12 text-slate-700 animate-pulse" />
            </div>
            <h2 className="text-2xl font-black mb-2 italic">Scanning for Signals...</h2>
            <p className="text-white/40 text-sm max-w-[240px]">
              You are currently patrolling **New Delhi Central**. Stay alert for nearby safety pulses.
            </p>
          </motion.div>
        ) : (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-6"
          >
            {/* Incident Card */}
            <div className={cn(
              "p-8 rounded-[2.5rem] border transition-all duration-500",
              status === 'idle' ? "bg-red-600 border-red-500 shadow-[0_0_40px_rgba(220,38,38,0.3)]" : "bg-slate-900 border-white/10"
            )}>
              <div className="flex items-start justify-between mb-8">
                 <div>
                    <div className="text-xs font-black uppercase tracking-widest opacity-60 mb-1">New Alert</div>
                    <div className="text-4xl font-black italic tracking-tighter uppercase">{activeIncident.type}</div>
                 </div>
                 <div className="px-3 py-1 bg-white/20 rounded-full text-[10px] font-black uppercase">
                    {activeIncident.id}
                 </div>
              </div>

              <div className="space-y-4 mb-8">
                 <div className="flex items-center gap-4">
                    <MapPin className="w-6 h-6 opacity-40" />
                    <div>
                       <div className="text-[10px] font-black uppercase opacity-40">Location</div>
                       <div className="text-lg font-bold">{activeIncident.location}</div>
                    </div>
                 </div>
                 <div className="flex items-center gap-4">
                    <Zap className="w-6 h-6 text-amber-400" />
                    <div>
                       <div className="text-[10px] font-black uppercase opacity-40">Distance / ETA</div>
                       <div className="text-lg font-bold">{activeIncident.distance} — <span className="text-amber-400">{activeIncident.eta}</span></div>
                    </div>
                 </div>
              </div>

              {status === 'idle' ? (
                <button 
                  onClick={handleAccept}
                  className="w-full py-5 bg-white text-red-600 rounded-3xl font-black uppercase tracking-widest text-lg shadow-xl hover:scale-[1.02] active:scale-95 transition-all flex items-center justify-center gap-3"
                >
                  Accept Dispatch
                  <ArrowRight className="w-6 h-6" />
                </button>
              ) : (
                <div className="flex items-center gap-3 text-emerald-400 font-black italic animate-pulse">
                   <ShieldCheck className="w-6 h-6" />
                   DISPATCH ACCEPTED — PROCEED TO LOCATION
                </div>
              )}
            </div>

            {/* Tactical Navigation (Mockup) */}
            {status !== 'idle' && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                 <div className="bg-slate-900 border border-white/10 rounded-3xl p-6">
                    <div className="flex items-center justify-between mb-4">
                       <h3 className="text-xs font-black uppercase tracking-widest opacity-40">Tactical HUD</h3>
                       <Navigation className="w-4 h-4 text-blue-500" />
                    </div>
                    <div className="h-40 bg-slate-800 rounded-2xl flex items-center justify-center border border-white/5 relative overflow-hidden">
                       <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent" />
                       <p className="text-[10px] font-black uppercase tracking-widest opacity-40">Map Radar Active</p>
                    </div>
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                    <button className="h-24 bg-blue-600 rounded-3xl p-6 flex flex-col justify-between hover:brightness-110 active:scale-95 transition-all">
                       <Phone className="w-6 h-6" />
                       <div className="text-[10px] font-black uppercase tracking-widest">Call Victim</div>
                    </button>
                    <button 
                      onClick={handleResolve}
                      className="h-24 bg-emerald-600 rounded-3xl p-6 flex flex-col justify-between hover:brightness-110 active:scale-95 transition-all"
                    >
                       <CheckCircle2 className="w-6 h-6" />
                       <div className="text-[10px] font-black uppercase tracking-widest">Mark Resolved</div>
                    </button>
                 </div>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer System Info */}
      <div className="fixed bottom-8 left-6 right-6">
         <div className="bg-white/5 backdrop-blur-md rounded-2xl p-4 flex items-center justify-between border border-white/10">
            <div className="flex items-center gap-2">
               <AlertCircle className="w-4 h-4 text-white/40" />
               <span className="text-[9px] font-bold uppercase tracking-widest opacity-40">System Node: NDLS_C_01</span>
            </div>
            <div className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">
               Sync: 14ms
            </div>
         </div>
      </div>
    </div>
  );
}
