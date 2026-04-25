import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Zap, 
  Shield, 
  Cpu, 
  Layout, 
  Search, 
  Activity, 
  Layers, 
  Send,
  Loader2,
  RefreshCcw,
  CheckCircle2,
  Terminal,
  History,
  Lock
} from 'lucide-react';
import { getHiveStatus, triggerHivePulse, HiveStatus } from '../api/swarm';
import { toast } from 'sonner';

const SwarmDashboard: React.FC = () => {
  const [status, setStatus] = useState<HiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [vibeInput, setVibeInput] = useState('');
  const [pulsing, setPulsing] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await getHiveStatus();
        setStatus(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handlePulse = async () => {
    if (!vibeInput.trim()) return;
    setPulsing(true);
    try {
      await triggerHivePulse(vibeInput);
      toast.success("Swarm Pulse Initiated", {
        description: `Autonomous agents are now building: ${vibeInput}`,
      });
      setVibeInput('');
    } catch (err) {
      toast.error("Pulse Failed", { description: "Swarm synchronizer error" });
    } finally {
      setPulsing(false);
    }
  };

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-96 bg-black/50 rounded-3xl border border-blue-500/20 backdrop-blur-xl">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 bg-slate-950 text-white rounded-[2rem] border border-white/10 shadow-2xl relative overflow-hidden">
      {/* Background Cinematic Glow */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-600/10 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2" />
      <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-purple-600/10 blur-[100px] rounded-full translate-y-1/2 -translate-x-1/2" />

      {/* Header Section */}
      <div className="relative flex items-center justify-between">
        <div>
          <h2 className="text-4xl font-black tracking-tighter bg-gradient-to-r from-blue-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent uppercase">
            Kimi K2.6 The Hive
          </h2>
          <p className="text-slate-400 font-medium flex items-center gap-2">
            <Activity className="w-4 h-4 text-green-400" />
            Autonomous Swarm Orchestrator • {status?.system_mode} • {status?.context_window}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-full flex items-center gap-2">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            <span className="text-xs font-bold text-blue-400 uppercase tracking-widest">
              Vibe Level: {((status?.vibe_level || 0) * 100).toFixed(1)}%
            </span>
          </div>
          <div className="px-4 py-2 bg-green-500/10 border border-green-500/20 rounded-full flex items-center gap-2">
            <span className="text-xs font-bold text-green-400 uppercase tracking-widest">
              {status?.total_agents_online} Online Agents
            </span>
          </div>
        </div>
      </div>

      {/* Vibe Engine Input */}
      <div className="relative group">
        <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000" />
        <div className="relative bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-2 flex items-center gap-4">
          <div className="pl-4">
            <Zap className="w-6 h-6 text-yellow-400" />
          </div>
          <input 
            type="text"
            placeholder="Describe the vibe or feature you want to build autonomously..."
            value={vibeInput}
            onChange={(e) => setVibeInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePulse()}
            className="flex-1 bg-transparent border-none outline-none text-lg font-medium placeholder:text-slate-600"
          />
          <button 
            onClick={handlePulse}
            disabled={pulsing || !vibeInput.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white px-6 py-3 rounded-xl flex items-center gap-2 font-bold transition-all transform active:scale-95"
          >
            {pulsing ? <RefreshCcw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            Initiate Swarm
          </button>
        </div>
      </div>

      {/* Squads Grid */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
        {Object.entries(status?.squads || {}).map(([name, data]) => (
          <motion.div 
            key={name}
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900/50 backdrop-blur-sm border border-white/5 p-5 rounded-2xl hover:border-blue-500/30 transition-colors group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400 group-hover:scale-110 transition-transform">
                {name.includes('Architect') && <Layers className="w-5 h-5" />}
                {name.includes('Frontend') && <Layout className="w-5 h-5" />}
                {name.includes('Backend') && <Cpu className="w-5 h-5" />}
                {name.includes('QA') && <Shield className="w-5 h-5" />}
                {name.includes('Reviewer') && <Search className="w-5 h-5" />}
              </div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                {data.total_capacity} Agents
              </span>
            </div>
            
            <h3 className="font-black text-sm uppercase mb-1 tracking-tight">{name}</h3>
            <div className="flex items-center gap-2 mb-4">
              <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${(data.active_threads / data.total_capacity) * 100}%` }}
                  className="h-full bg-blue-500"
                />
              </div>
              <span className="text-[10px] font-bold text-blue-400">{data.active_threads} active</span>
            </div>

            <div className="space-y-2">
              <p className="text-[9px] font-bold text-slate-500 uppercase">Recent Pulse</p>
              <div className="space-y-1">
                {data.current_tasks.slice(0, 2).map((task, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <CheckCircle2 className="w-2.5 h-2.5 text-green-500 mt-0.5 shrink-0" />
                    <span className="text-[10px] text-slate-300 leading-tight truncate">{task}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Advanced Modules Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {status?.modules && Object.entries(status.modules).map(([name, state]) => (
          <div key={name} className="flex items-center gap-4 bg-slate-900/30 border border-white/5 p-4 rounded-2xl">
            <div className="p-2 bg-purple-500/10 rounded-xl text-purple-400">
              {name.includes('Transpiler') && <Terminal className="w-5 h-5" />}
              {name.includes('Refactor') && <History className="w-5 h-5" />}
              {name.includes('SafeExecution') && <Lock className="w-5 h-5" />}
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{name}</p>
              <div className="flex items-center gap-2">
                <span className="text-xs font-black text-white">{state}</span>
                <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Real-time Agent Matrix (Vibe Simulation) */}
      <div className="grid grid-cols-10 gap-1 opacity-20 hover:opacity-40 transition-opacity">
        {Array.from({ length: 100 }).map((_, i) => (
          <motion.div 
            key={i}
            animate={{ 
              opacity: [0.2, 0.8, 0.2],
              scale: [1, 1.2, 1]
            }}
            transition={{ 
              duration: Math.random() * 2 + 1, 
              repeat: Infinity,
              delay: Math.random() * 2
            }}
            className="h-1 bg-blue-400 rounded-full"
          />
        ))}
      </div>
    </div>
  );
};

export default SwarmDashboard;
