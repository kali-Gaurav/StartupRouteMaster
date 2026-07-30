import { useState, useEffect } from 'react';
import { getRailwayApiUrl } from '@/lib/utils';
import { useSystemStatus, SurgeLevel } from '@/store/useSystemStatus';

export function useBackendHealth() {
  const { isOnline, setSystemStatus, setRetryAfter } = useSystemStatus();

  useEffect(() => {
    const checkHealth = async () => {
      const startTime = performance.now();
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); 
        
        const res = await fetch(getRailwayApiUrl('/health'), { 
          signal: controller.signal,
          headers: { 'Cache-Control': 'no-cache' }
        });
        
        const latencyMs = Math.round(performance.now() - startTime);
        clearTimeout(timeoutId);

        if (res.status === 503) {
          const retryAfter = parseInt(res.headers.get('Retry-After') || '30');
          setRetryAfter(retryAfter);
          setSystemStatus({ isOnline: true, surgeLevel: 'Critical', latencyMs });
          return;
        }

        if (res.ok) {
          const data = await res.json();
          setSystemStatus({ 
            isOnline: true, 
            v3Core: !!data.v3_core,
            scrapersPool: data.components?.scrapers?.pool || "IDLE",
            ledgerStatus: data.components?.ledger?.status || "PENDING",
            surgeLevel: (data.surge_level as SurgeLevel) || 'Normal',
            maintenanceMode: !!data.maintenance,
            degradedFeatures: data.degraded_features || [],
            latencyMs
          });
        } else {
          setSystemStatus({ isOnline: false, latencyMs });
        }
      } catch (err) {
        const latencyMs = Math.round(performance.now() - startTime);
        setSystemStatus({ isOnline: false, latencyMs });
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [setSystemStatus, setRetryAfter]);

  return isOnline;
}
