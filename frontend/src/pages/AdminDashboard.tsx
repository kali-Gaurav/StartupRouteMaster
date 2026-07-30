import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Shield, Activity, Users, Zap, Globe, Lock, AlertTriangle, CheckCircle } from 'lucide-react';

const REGIONS = ['NORTH', 'SOUTH', 'EAST', 'WEST', 'CENTRAL'];

export const AdminDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState({
    activeSathis: 12450,
    incidentsResolved: 892,
    avgResponseTime: '1.2m',
    systemIntegrity: '100%'
  });

  const [regionalHealth, setRegionalHealth] = useState(
    REGIONS.map(name => ({
      name,
      status: 'HEALTHY',
      load: Math.floor(Math.random() * 30) + 10,
      latency: Math.floor(Math.random() * 10) + 5
    }))
  );

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8 font-sans">
      {/* Header */}
      <div className="flex justify-between items-center mb-12">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-blue-600 p-2 rounded-lg">
              <Shield size={24} className="text-white" />
            </div>
            <h1 className="text-3xl font-black tracking-tighter">SATHI COMMAND</h1>
          </div>
          <p className="text-gray-500 text-xs tracking-widest uppercase">National Safety Infrastructure v3.1.0</p>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Global Shard Status</div>
            <div className="flex items-center gap-2 text-green-400 font-bold">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              OPERATIONAL
            </div>
          </div>
          <div className="h-12 w-[1px] bg-white/10" />
          <button className="bg-white/5 border border-white/10 px-6 py-3 rounded-xl hover:bg-white/10 transition-all text-sm font-bold">
            EXPORT AUDIT LEDGER
          </button>
        </div>
      </div>

      {/* Top Level Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
        {[
          { label: 'Active Guardians', value: metrics.activeSathis, icon: Users, color: 'text-blue-400' },
          { label: 'Incidents (24h)', value: metrics.incidentsResolved, icon: Activity, color: 'text-orange-400' },
          { label: 'Avg Dispatch', value: metrics.avgResponseTime, icon: Zap, color: 'text-yellow-400' },
          { label: 'Audit Integrity', value: metrics.systemIntegrity, icon: Lock, color: 'text-green-400' }
        ].map((m, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="bg-white/5 border border-white/10 p-6 rounded-3xl"
          >
            <m.icon size={20} className={`${m.color} mb-4`} />
            <div className="text-3xl font-black mb-1">{m.value}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">{m.label}</div>
          </motion.div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Regional Shard Matrix */}
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-xl font-black tracking-tight mb-4 flex items-center gap-2">
            <Globe size={20} className="text-blue-500" />
            Regional Shard Matrix
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {regionalHealth.map((shard, i) => (
              <div key={i} className="bg-white/5 border border-white/10 p-6 rounded-3xl flex justify-between items-center">
                <div>
                  <div className="text-lg font-bold mb-1">{shard.name}</div>
                  <div className="flex gap-4">
                    <div className="text-[10px] text-gray-500 uppercase">Load: <span className="text-white">{shard.load}%</span></div>
                    <div className="text-[10px] text-gray-500 uppercase">Latency: <span className="text-white">{shard.latency}ms</span></div>
                  </div>
                </div>
                <div className="px-3 py-1 rounded-full bg-green-500/10 text-green-400 text-[10px] font-black border border-green-500/20">
                  {shard.status}
                </div>
              </div>
            ))}
          </div>

          {/* National Heatmap Placeholder */}
          <div className="bg-white/5 border border-white/10 h-80 rounded-3xl relative overflow-hidden flex items-center justify-center">
            <div className="absolute inset-0 opacity-20 bg-[url('https://upload.wikimedia.org/wikipedia/commons/e/e0/India_map_blank.svg')] bg-center bg-no-repeat bg-contain" />
            <div className="z-10 text-center">
              <Activity size={48} className="text-blue-500/30 mx-auto mb-4" />
              <div className="text-gray-500 font-bold tracking-widest text-xs uppercase">National Safety Heatmap Live</div>
            </div>
            
            {/* Simulated Heatmap Pulses */}
            <motion.div animate={{ scale: [1, 2], opacity: [0.5, 0] }} transition={{ duration: 3, repeat: Infinity }} className="absolute top-1/3 left-1/2 w-32 h-32 bg-red-500/20 rounded-full" />
            <motion.div animate={{ scale: [1, 2], opacity: [0.5, 0] }} transition={{ duration: 4, repeat: Infinity, delay: 1 }} className="absolute bottom-1/4 right-1/3 w-24 h-24 bg-blue-500/20 rounded-full" />
          </div>
        </div>

        {/* Live Audit Ledger */}
        <div className="space-y-6">
          <h2 className="text-xl font-black tracking-tight mb-4 flex items-center gap-2">
            <Lock size={20} className="text-green-500" />
            Audit Integrity Feed
          </h2>
          <div className="bg-black/60 border border-white/10 rounded-3xl p-6 h-[600px] overflow-hidden relative">
            <div className="space-y-4">
              {[
                { event: 'INCIDENT_RESOLVED', sathi: 'S-4822', hash: '88AF...3DE2', time: '2m ago', type: 'SUCCESS' },
                { event: 'KYC_CERTIFIED', sathi: 'S-9011', hash: '44B1...11A9', time: '5m ago', type: 'SUCCESS' },
                { event: 'SHARD_REBALANCE', region: 'NORTH', hash: 'CE09...FF21', time: '12m ago', type: 'SYSTEM' },
                { event: 'SOS_TRIGGERED', user: 'U-1102', hash: '2F1D...B87B', time: '15m ago', type: 'ALERT' },
                { event: 'INCIDENT_RESOLVED', sathi: 'S-2210', hash: '99CC...44D1', time: '22m ago', type: 'SUCCESS' },
              ].map((log, i) => (
                <div key={i} className="border-b border-white/5 pb-4">
                  <div className="flex justify-between items-start mb-1">
                    <span className={`text-[10px] font-black px-2 py-0.5 rounded ${
                      log.type === 'SUCCESS' ? 'bg-green-500/10 text-green-400' : 
                      log.type === 'ALERT' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400'
                    }`}>
                      {log.event}
                    </span>
                    <span className="text-[10px] text-gray-500">{log.time}</span>
                  </div>
                  <div className="text-[10px] font-mono text-gray-400 break-all">
                    SIG: {log.hash}
                  </div>
                </div>
              ))}
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent pointer-events-none" />
          </div>
          
          <div className="bg-orange-500/10 border border-orange-500/30 p-4 rounded-2xl flex gap-4 items-center">
            <AlertTriangle className="text-orange-500 shrink-0" size={24} />
            <div>
              <div className="text-sm font-bold text-orange-400">High Load Warning</div>
              <div className="text-[10px] text-orange-400/70">Shard NORTH experiencing 82% concurrent load. Triggering predictive rebalance.</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
