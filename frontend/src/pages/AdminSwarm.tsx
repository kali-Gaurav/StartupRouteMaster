import React from 'react';
import SwarmDashboard from '@/components/SwarmDashboard';
import { motion } from 'framer-motion';
import { Info } from 'lucide-react';

const AdminSwarm: React.FC = () => {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Swarm Intelligence</h1>
          <p className="text-muted-foreground">
            Manage the autonomous Kimi K2.6 agent collective and trigger Vibe Coding pulses.
          </p>
        </div>
        <motion.div 
          whileHover={{ scale: 1.05 }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-500 cursor-help"
        >
          <Info className="w-4 h-4" />
          <span className="text-sm font-medium uppercase tracking-wider">Hive Protocol v2.6</span>
        </motion.div>
      </div>

      {/* Main Swarm Dashboard */}
      <SwarmDashboard />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-card border rounded-2xl">
          <h3 className="text-lg font-bold mb-2">Swarm Parallelism</h3>
          <p className="text-3xl font-black text-blue-500">300x</p>
          <p className="text-sm text-muted-foreground mt-1">Simultaneous threads across 5 squads</p>
        </div>
        <div className="p-6 bg-card border rounded-2xl">
          <h3 className="text-lg font-bold mb-2">Vibe Transpilation</h3>
          <p className="text-3xl font-black text-purple-500">Active</p>
          <p className="text-sm text-muted-foreground mt-1">Translating natural language to autonomous logic</p>
        </div>
        <div className="p-6 bg-card border rounded-2xl">
          <h3 className="text-lg font-bold mb-2">Zero-Cloud Latency</h3>
          <p className="text-3xl font-black text-green-500">14ms</p>
          <p className="text-sm text-muted-foreground mt-1">Local orchestration response time</p>
        </div>
      </div>
    </div>
  );
};

export default AdminSwarm;
