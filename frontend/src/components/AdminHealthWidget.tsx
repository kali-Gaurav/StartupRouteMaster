import React, { useEffect, useState } from 'react';
import { Shield, Activity, BarChart3, AlertTriangle } from 'lucide-react';

interface APIBudget {
  provider: string;
  spent: number;
  limit: number;
  usage_percent: number;
  is_active: boolean;
}

interface TelemetryReport {
  performance: {
    cpu_usage_percent: number;
    ram_usage_percent: number;
    event_loop_latency_ms: number;
  };
  providers?: {
    calls: Record<string, number>;
    failures: Record<string, number>;
    avg_latency: Record<string, number>;
  };
}

export const AdminHealthWidget: React.FC = () => {
  const [budgets, setBudgets] = useState<APIBudget[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [bRes, tRes] = await Promise.all([
          fetch('/api/v2/admin/debug/budget'),
          fetch('/api/v2/admin/debug/telemetry')
        ]);
        
        if (bRes.ok) setBudgets(await bRes.json());
        if (tRes.ok) setTelemetry(await tRes.json());
      } catch (err) {
        console.error("Admin Monitor failed:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return null;

  return (
    <div className="p-6 bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-700/50 shadow-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="w-6 h-6 text-blue-400" />
        <h2 className="text-xl font-bold text-white">System Sentinel</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* API Budget Monitoring */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-slate-400 font-medium">
            <BarChart3 className="w-4 h-4" />
            API BUDGET BURN
          </div>
          {budgets.map(b => (
            <div key={b.provider} className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-semibold text-white">{b.provider}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${b.usage_percent > 80 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                  {b.usage_percent}%
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                <div 
                  className={`h-full transition-all duration-500 ${b.usage_percent > 90 ? 'bg-red-500' : b.usage_percent > 70 ? 'bg-orange-500' : 'bg-blue-500'}`}
                  style={{ width: `${Math.min(100, b.usage_percent)}%` }}
                />
              </div>
              <div className="mt-2 text-[10px] text-slate-500 uppercase tracking-wider">
                ${b.spent.toFixed(2)} / ${b.limit} Monthly Limit
              </div>
            </div>
          ))}
        </div>

        {/* Telemetry & Scraper Health */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-slate-400 font-medium">
            <Activity className="w-4 h-4" />
            LIVE TELEMETRY
          </div>
          
          {telemetry && (
            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-xs text-slate-500 mb-1">CPU</div>
                  <div className="text-lg font-mono text-white">{telemetry.performance.cpu_usage_percent}%</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-1">RAM</div>
                  <div className="text-lg font-mono text-white">{telemetry.performance.ram_usage_percent}%</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-1">LOOP</div>
                  <div className="text-lg font-mono text-white">{telemetry.performance.event_loop_latency_ms.toFixed(1)}ms</div>
                </div>
              </div>
              
              {telemetry.providers && (
                <div className="mt-4 pt-4 border-t border-slate-700/50">
                  <div className="text-[10px] text-slate-500 mb-3 uppercase tracking-widest">Failover Stats</div>
                  <div className="space-y-2">
                    {Object.entries(telemetry.providers.calls).map(([name, calls]) => (
                      <div key={name} className="flex justify-between items-center text-xs">
                        <span className="text-slate-400 capitalize">{name}</span>
                        <div className="flex gap-4">
                          <span className="text-white font-mono">{calls} calls</span>
                          <span className="text-red-400 font-mono">{(telemetry.providers?.failures[name] || 0)} err</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Alerts */}
          {budgets.some(b => b.usage_percent > 90) && (
            <div className="flex items-center gap-3 p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
              <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
              <div className="text-xs text-red-200">
                Critical Budget Alert: Provider fallback to NTES Scraper is imminent or active.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
