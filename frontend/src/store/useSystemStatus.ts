import { create } from 'zustand';

export type SurgeLevel = 'Normal' | 'Elevated' | 'High' | 'Critical';

 interface SystemState {
  isOnline: boolean;
  v3Core: boolean; // Task 50.1
  scrapersPool: string; // Task 48.7
  ledgerStatus: string; // Task 49.9
  surgeLevel: SurgeLevel;
  maintenanceMode: boolean;
  degradedFeatures: string[];
  retryAfter: number; // seconds
  latencyMs: number;
  fps: number; // Task 1.20
  
  setSystemStatus: (status: Partial<SystemState>) => void;
  setRetryAfter: (seconds: number) => void;
}

export const useSystemStatus = create<SystemState>((set) => ({
  isOnline: true,
  v3Core: false,
  scrapersPool: "IDLE",
  ledgerStatus: "PENDING",
  surgeLevel: 'Normal',
  maintenanceMode: false,
  degradedFeatures: [],
  retryAfter: 0,
  latencyMs: 0,
  fps: 60,

  setSystemStatus: (status) => set((state) => ({ ...state, ...status })),
  setRetryAfter: (seconds) => {
    set({ retryAfter: seconds });
    if (seconds > 0) {
      const timer = setInterval(() => {
        set((state) => {
          if (state.retryAfter <= 1) {
            clearInterval(timer);
            return { retryAfter: 0 };
          }
          return { retryAfter: state.retryAfter - 1 };
        });
      }, 1000);
    }
  },
}));
