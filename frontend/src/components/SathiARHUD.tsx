import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Navigation2, Target, ShieldAlert, CheckCircle, ChevronUp } from 'lucide-react';

interface ARHUDProps {
  victimId: string;
  victimLat: number;
  victimLon: number;
  currentLat: number;
  currentLon: number;
  victimStatus: 'CRITICAL' | 'STABLE' | 'RESOLVED';
  onArrive: () => void;
}

export const SathiARHUD: React.FC<ARHUDProps> = ({
  victimId,
  victimLat,
  victimLon,
  currentLat,
  currentLon,
  victimStatus,
  onArrive
}) => {
  const [distance, setDistance] = useState<number>(0);
  const [bearing, setBearing] = useState<number>(0);

  useEffect(() => {
    // Calculate distance and bearing in real-time
    const R = 6371e3; // metres
    const φ1 = (currentLat * Math.PI) / 180;
    const φ2 = (victimLat * Math.PI) / 180;
    const Δφ = ((victimLat - currentLat) * Math.PI) / 180;
    const Δλ = ((victimLon - currentLon) * Math.PI) / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const d = R * c;
    setDistance(d);

    const y = Math.sin(Δλ) * Math.cos(φ2);
    const x = Math.cos(φ1) * Math.sin(φ2) -
              Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
    const θ = Math.atan2(y, x);
    const brng = ((θ * 180) / Math.PI + 360) % 360;
    setBearing(brng);

    if (d < 5) onArrive(); // Auto-detect arrival
  }, [currentLat, currentLon, victimLat, victimLon, onArrive]);

  return (
    <div className="fixed inset-0 pointer-events-none flex flex-col items-center justify-center bg-black/10 backdrop-blur-[1px]">
      {/* Target Marker (Simulated AR Overlay) */}
      <motion.div 
        animate={{ 
          rotate: bearing,
          scale: distance < 20 ? 1.5 : 1,
          opacity: [0.7, 1, 0.7]
        }}
        transition={{ duration: 2, repeat: Infinity }}
        className="relative w-64 h-64 border-2 border-dashed border-red-500/30 rounded-full flex items-center justify-center"
      >
        <Navigation2 className="w-12 h-12 text-red-500 fill-current" />
        
        {/* Victim Radar Pulse */}
        <motion.div 
          animate={{ scale: [1, 2], opacity: [0.5, 0] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="absolute inset-0 bg-red-500/20 rounded-full"
        />
      </motion.div>

      {/* Tactical HUD Overlay */}
      <div className="absolute top-12 left-6 right-6 flex justify-between items-start">
        <div className="bg-black/60 border border-red-500/50 backdrop-blur-md p-4 rounded-xl">
          <div className="flex items-center gap-2 text-red-400 font-bold tracking-widest text-xs mb-1">
            <ShieldAlert size={16} />
            LIVE INCIDENT: {victimId}
          </div>
          <div className="text-2xl font-black text-white">
            {distance.toFixed(0)}m
          </div>
          <div className="text-[10px] text-gray-400 uppercase tracking-tighter">
            Est. Arrival: {Math.ceil(distance / 1.5)}s
          </div>
        </div>

        <div className="flex flex-col gap-2 items-end">
          <div className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-tighter ${
            victimStatus === 'CRITICAL' ? 'bg-red-600 animate-pulse' : 'bg-orange-600'
          } text-white`}>
            {victimStatus}
          </div>
          <div className="bg-black/60 border border-white/20 backdrop-blur-md p-2 rounded-lg text-white text-[10px] flex items-center gap-2">
            <Target size={12} className="text-blue-400" />
            Accuracy: 1.2m
          </div>
        </div>
      </div>

      {/* Directional Guidance */}
      <div className="absolute bottom-24 flex flex-col items-center">
        <motion.div
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 1, repeat: Infinity }}
        >
          <ChevronUp size={48} className="text-white/80" />
        </motion.div>
        <div className="text-white font-bold tracking-[0.2em] text-sm bg-black/40 px-6 py-2 rounded-full border border-white/10">
          PROCEED FORWARD
        </div>
      </div>

      {/* Arrival Overlay */}
      <AnimatePresence>
        {distance < 5 && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="absolute inset-0 bg-green-900/90 flex flex-col items-center justify-center p-8 text-center pointer-events-auto"
          >
            <CheckCircle size={80} className="text-green-400 mb-6" />
            <h2 className="text-4xl font-black text-white mb-2">TARGET REACHED</h2>
            <p className="text-green-200 mb-8">Secure the perimeter and initiate safety protocol S-1.</p>
            <button 
              onClick={onArrive}
              className="bg-white text-green-900 font-bold px-12 py-4 rounded-2xl hover:bg-green-50 transition-colors"
            >
              CONFIRM ARRIVAL
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
