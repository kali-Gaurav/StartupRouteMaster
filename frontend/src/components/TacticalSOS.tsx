import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, Radio, Mic, EyeOff, Zap, MapPin, CheckCircle, X } from 'lucide-react';
import { hapticController } from '../utils/hapticController';
import { useTranslation } from '../context/LanguageContext';

export const TacticalSOS: React.FC = () => {
  const { t } = useTranslation();
  const [isStealth, setIsStealth] = useState(false);
  const [triggerState, setTriggerState] = useState<'IDLE' | 'ARMED' | 'DISPATCHING' | 'ACTIVE' | 'CANCELLED'>('IDLE');
  const [countdown, setCountdown] = useState(3);

  const handleTrigger = () => {
    hapticController.triggerImpact();
    setTriggerState('ARMED');
  };

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (triggerState === 'ARMED' && countdown > 0) {
      timer = setTimeout(() => setCountdown(c => c - 1), 1000);
      hapticController.triggerImpact();
    } else if (triggerState === 'ARMED' && countdown === 0) {
      setTriggerState('DISPATCHING');
      // Simulate Backend Call
      setTimeout(() => {
        setTriggerState('ACTIVE');
        hapticController.triggerSuccess();
      }, 1500);
    }
    return () => clearTimeout(timer);
  }, [triggerState, countdown]);

  if (isStealth && triggerState === 'IDLE') {
    return (
      <div 
        onClick={handleTrigger}
        className="fixed bottom-6 right-6 w-12 h-12 bg-white/5 rounded-full flex items-center justify-center border border-white/5 opacity-20 hover:opacity-100 transition-opacity"
      >
        <EyeOff size={16} className="text-gray-500" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center p-6 z-[9999] pointer-events-none">
      <AnimatePresence>
        {triggerState !== 'IDLE' && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            className="w-full max-w-sm bg-black/80 backdrop-blur-3xl border border-red-500/30 rounded-[40px] p-8 pointer-events-auto shadow-[0_0_100px_rgba(239,68,68,0.2)]"
          >
            {triggerState === 'ARMED' && (
              <div className="text-center">
                <div className="text-red-500 mb-6 flex justify-center">
                  <motion.div 
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="relative"
                  >
                    <ShieldAlert size={80} />
                    <div className="absolute inset-0 bg-red-500/20 blur-xl rounded-full" />
                  </motion.div>
                </div>
                <h2 className="text-3xl font-black text-white mb-2">{t('sos.triggered')}</h2>
                <p className="text-gray-400 text-sm mb-8">Notifying nearby Sathis and Railway Police in...</p>
                
                <div className="text-6xl font-black text-red-500 mb-10">{countdown}s</div>
                
                <button 
                  onClick={() => {
                    setTriggerState('IDLE');
                    setCountdown(3);
                    hapticController.triggerWarning();
                  }}
                  className="w-full py-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-2xl text-white font-bold transition-all"
                >
                  {t('sos.cancel')}
                </button>
              </div>
            )}

            {triggerState === 'DISPATCHING' && (
              <div className="text-center py-10">
                <motion.div 
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  className="w-20 h-20 border-4 border-red-500/20 border-t-red-500 rounded-full mx-auto mb-8"
                />
                <h3 className="text-xl font-bold text-white mb-2 tracking-tight uppercase">Encrypting Signal</h3>
                <p className="text-red-400/70 text-xs animate-pulse">Broadcasting via National Shard [NORTH]</p>
              </div>
            )}

            {triggerState === 'ACTIVE' && (
              <div className="text-center">
                <div className="bg-red-500 w-20 h-20 rounded-full mx-auto flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(239,68,68,0.5)]">
                  <Radio size={40} className="text-white animate-pulse" />
                </div>
                <h2 className="text-2xl font-black text-white mb-1">{t('sos.help_on_way')}</h2>
                <p className="text-gray-400 text-xs mb-8">{t('sos.sathi_nearby')}</p>
                
                <div className="space-y-3 mb-8">
                  <div className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center text-blue-400">
                        <Zap size={16} />
                      </div>
                      <div className="text-left">
                        <div className="text-white text-xs font-bold">Golden Guardian S-4822</div>
                        <div className="text-gray-500 text-[10px]">ETA: 45 seconds</div>
                      </div>
                    </div>
                    <MapPin size={16} className="text-red-500" />
                  </div>
                </div>

                <button 
                  onClick={() => setTriggerState('IDLE')}
                  className="w-full py-4 bg-green-600 hover:bg-green-500 rounded-2xl text-white font-black transition-all shadow-lg shadow-green-900/20"
                >
                  {t('sos.secure_now')}
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Trigger Button (When Idle) */}
      {triggerState === 'IDLE' && !isStealth && (
        <div className="absolute bottom-12 flex flex-col items-center gap-4 pointer-events-auto">
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleTrigger}
            className="group relative w-32 h-32 bg-red-600 rounded-full flex items-center justify-center shadow-[0_0_50px_rgba(220,38,38,0.4)] overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-black/20 to-transparent" />
            <ShieldAlert size={48} className="text-white relative z-10 group-hover:scale-110 transition-transform" />
            <motion.div 
              animate={{ scale: [1, 1.5], opacity: [0.3, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 bg-white rounded-full"
            />
          </motion.button>
          
          <div className="flex gap-3">
            <button 
              onClick={() => setIsStealth(true)}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-full border border-white/10 flex items-center gap-2 text-gray-400 text-[10px] font-black tracking-widest uppercase transition-all"
            >
              <EyeOff size={12} />
              Stealth Mode
            </button>
            <button className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-full border border-white/10 flex items-center gap-2 text-gray-400 text-[10px] font-black tracking-widest uppercase transition-all">
              <Mic size={12} />
              Voice Trigger
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
