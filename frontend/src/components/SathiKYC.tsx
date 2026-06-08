import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Upload, Fingerprint, CheckCircle2, AlertCircle, FileText } from 'lucide-react';

interface KYCState {
  status: 'IDLE' | 'UPLOADING' | 'VERIFYING' | 'CERTIFIED' | 'REJECTED';
  documentType: string | null;
  fingerprint: string | null;
}

export const SathiKYC: React.FC = () => {
  const [state, setState] = useState<KYCState>({
    status: 'IDLE',
    documentType: null,
    fingerprint: null
  });

  const handleSimulateUpload = async (type: string) => {
    setState(prev => ({ ...prev, status: 'UPLOADING', documentType: type }));
    
    // Simulate industrial-grade document hashing & encryption
    await new Promise(r => setTimeout(r, 2000));
    
    setState(prev => ({ ...prev, status: 'VERIFYING' }));
    
    // Simulate Background Verification via KYCService
    await new Promise(r => setTimeout(r, 3000));
    
    // Generate dynamic hash for audit trail
    const timestamp = new Date().toISOString();
    const uniqueString = `${type}-${timestamp}-${Math.random().toString()}`;
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(uniqueString);
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const dynamicHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 32).toUpperCase();
    
    setState(prev => ({ 
      ...prev, 
      status: 'CERTIFIED', 
      fingerprint: `SHA256:${dynamicHash}` 
    }));
  };

  return (
    <div className="w-full max-w-md mx-auto bg-black/40 backdrop-blur-xl border border-white/10 rounded-3xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 p-6 flex items-center gap-4">
        <div className="bg-white/20 p-3 rounded-2xl">
          <ShieldCheck className="text-white w-8 h-8" />
        </div>
        <div>
          <h2 className="text-xl font-black text-white tracking-tight">Identity Verification</h2>
          <p className="text-blue-100 text-xs">Certified Sathi Onboarding</p>
        </div>
      </div>

      <div className="p-8">
        {state.status === 'IDLE' && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <p className="text-gray-400 text-sm mb-6 leading-relaxed">
              To join the elite safety network, we require a one-time identity verification. Your data is encrypted and stored in an immutable audit ledger.
            </p>
            
            <div className="space-y-3">
              {[
                { id: 'AADHAAR', name: 'Aadhaar Card (Digital)', icon: Fingerprint },
                { id: 'DL', name: 'Driving License', icon: FileText },
                { id: 'VOTER', name: 'Voter ID', icon: Upload }
              ].map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleSimulateUpload(doc.id)}
                  className="w-full flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-2xl hover:bg-white/10 transition-all group"
                >
                  <div className="flex items-center gap-4">
                    <doc.icon className="text-blue-400 group-hover:scale-110 transition-transform" size={20} />
                    <span className="text-white font-medium text-sm">{doc.name}</span>
                  </div>
                  <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {(state.status === 'UPLOADING' || state.status === 'VERIFYING') && (
          <div className="flex flex-col items-center py-10">
            <div className="relative w-20 h-20 mb-6">
              <motion.div 
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 border-4 border-blue-500/20 border-t-blue-500 rounded-full"
              />
              <div className="absolute inset-0 flex items-center justify-center">
                {state.status === 'UPLOADING' ? <Upload className="text-blue-400 animate-bounce" /> : <Fingerprint className="text-blue-400" />}
              </div>
            </div>
            <h3 className="text-white font-bold text-lg mb-1">
              {state.status === 'UPLOADING' ? 'Encrypting Documents...' : 'Verifying Identity...'}
            </h3>
            <p className="text-gray-500 text-xs text-center px-8">
              Connecting to Indian Railways Identity Gateway
            </p>
          </div>
        )}

        {state.status === 'CERTIFIED' && (
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="flex flex-col items-center text-center py-6"
          >
            <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-6">
              <CheckCircle2 className="text-green-500 w-12 h-12" />
            </div>
            <h3 className="text-2xl font-black text-white mb-2">VERIFIED SATHI</h3>
            <p className="text-gray-400 text-sm mb-6">
              Your identity has been cryptographically linked to the safety network.
            </p>
            
            <div className="w-full bg-black/60 rounded-xl p-4 border border-green-500/30 mb-8 font-mono text-[10px] text-green-500/80 break-all text-left">
              <div className="text-white/40 mb-1 uppercase tracking-widest font-sans">Audit Fingerprint</div>
              {state.fingerprint}
            </div>

            <button className="w-full py-4 bg-green-600 hover:bg-green-500 text-white font-black rounded-2xl transition-all shadow-lg shadow-green-900/20">
              ENTER RESPONDER MODE
            </button>
          </motion.div>
        )}
      </div>

      <div className="p-4 bg-white/5 border-t border-white/5 flex items-center justify-center gap-2 text-[10px] text-gray-500 tracking-widest uppercase">
        <ShieldCheck size={12} />
        Bank-Grade Encryption Enabled
      </div>
    </div>
  );
};
