import React, { useState, useEffect } from 'react';
import { ShieldAlert, MapPin, Users, Phone, Zap, ArrowRight, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface GuardianHUDProps {
  isActive: boolean;
  incidentStatus?: 'triggered' | 'active' | 'resolved';
  responderInfo?: {
    name: string;
    distance: string;
    eta: string;
  };
  onCancel?: () => void;
}

export function GuardianHUD({ isActive, incidentStatus, responderInfo, onCancel }: GuardianHUDProps) {
  if (!isActive) return null;

  return (
    <AnimatePresence>
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur-xl flex flex-col p-6 text-white"
      >
        {/* Animated Safety Pulse Background */}
        <div className="absolute inset-0 overflow-hidden opacity-20 pointer-events-none">
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] border-[1px] border-red-500/50 rounded-full animate-ping duration-[3s]" />
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border-[1px] border-red-500/30 rounded-full animate-ping duration-[4s]" />
        </div>

        {/* Header Section */}
        <div className="relative flex items-center justify-between mb-12">
           <div className="flex items-center gap-3">
              <div className="p-3 bg-red-600 rounded-2xl animate-pulse">
                 <ShieldAlert className="w-8 h-8" />
              </div>
              <div>
                 <h1 className="text-3xl font-black uppercase tracking-tighter italic">Guardian Mode</h1>
                 <p className="text-red-400 text-xs font-bold uppercase tracking-widest">Active Safety Shield</p>
              </div>
           </div>
           <button 
             onClick={onCancel}
             className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-xl text-[10px] font-black uppercase tracking-widest transition-colors"
           >
             Abort System
           </button>
        </div>

        {/* Status Dashboard */}
        <div className="flex-1 space-y-6">
           {/* Incident State */}
           <div className="bg-white/5 border border-white/10 rounded-[2.5rem] p-8 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-6 opacity-10">
                 <Zap className="w-32 h-32" />
              </div>
              
              <div className="text-xs font-black uppercase tracking-widest text-white/40 mb-2">Live Response Status</div>
              <div className="text-5xl font-black uppercase tracking-tighter italic mb-8">
                 {incidentStatus === 'triggered' ? 'Scanning Responders...' : 
                  incidentStatus === 'active' ? 'Responder En Route' : 'System Standby'}
              </div>

              {responderInfo ? (
                <div className="space-y-4">
                   <div className="flex items-center justify-between p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl">
                      <div className="flex items-center gap-3">
                         <div className="p-2 bg-emerald-500 rounded-lg">
                            <ShieldCheck className="w-5 h-5" />
                         </div>
                         <div>
                            <div className="text-xs font-bold text-emerald-400">Assigned Sathi</div>
                            <div className="text-lg font-black uppercase tracking-tight">{responderInfo.name}</div>
                         </div>
                      </div>
                      <div className="text-right">
                         <div className="text-[10px] font-black uppercase opacity-40">Distance</div>
                         <div className="text-xl font-black">{responderInfo.distance}</div>
                      </div>
                   </div>
                   
                   <div className="flex items-center gap-3 text-emerald-400 font-bold">
                      <Zap className="w-4 h-4 animate-bounce" />
                      <span>ETA: {responderInfo.eta}</span>
                   </div>
                </div>
              ) : (
                <div className="flex flex-col items-center py-12 text-center">
                   <div className="w-16 h-16 border-4 border-red-500 border-t-transparent rounded-full animate-spin mb-6" />
                   <p className="text-red-400 font-bold">Connecting to Railway Police & Nearest Sathis...</p>
                </div>
              )}
           </div>

           {/* Interaction Grid */}
           <div className="grid grid-cols-2 gap-4">
              <button className="bg-red-600 h-32 rounded-3xl p-6 flex flex-col justify-between hover:scale-[1.02] active:scale-95 transition-all">
                 <Phone className="w-8 h-8" />
                 <div className="text-left">
                    <div className="text-[10px] font-black uppercase tracking-widest opacity-60">Call Emergency</div>
                    <div className="text-xl font-black">182 (GRP)</div>
                 </div>
              </button>
              <button className="bg-blue-600 h-32 rounded-3xl p-6 flex flex-col justify-between hover:scale-[1.02] active:scale-95 transition-all">
                 <Users className="w-8 h-8" />
                 <div className="text-left">
                    <div className="text-[10px] font-black uppercase tracking-widest opacity-60">Notify Family</div>
                    <div className="text-xl font-black italic">Alert Group</div>
                 </div>
              </button>
           </div>
        </div>

        {/* Footer Guidance */}
        <div className="mt-8 p-6 bg-white/5 rounded-3xl flex items-center justify-between">
           <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-red-500" />
              <div className="text-xs">
                 <div className="opacity-40 uppercase font-black">Current Location</div>
                 <div className="font-bold">Platform 4, New Delhi Railway Station</div>
              </div>
           </div>
           <ArrowRight className="w-6 h-6 opacity-20" />
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
