const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface HiveSquadStatus {
  total_capacity: number;
  active_threads: number;
  health: string;
  current_tasks: string[];
  mapped_agents: string[];
}

export interface HiveStatus {
  timestamp: number;
  squads: Record<string, HiveSquadStatus>;
  modules: Record<string, string>;
  vibe_level: number;
  total_agents_online: number;
  system_mode: string;
  context_window: string;
}

export const getHiveStatus = async (): Promise<HiveStatus> => {
  const response = await fetch(`${API_BASE_URL}/v3/swarm/hive/status`);
  if (!response.ok) throw new Error('Failed to fetch hive status');
  return response.json();
};

export const triggerHivePulse = async (vibe: string): Promise<any> => {
  const response = await fetch(`${API_BASE_URL}/v3/swarm/hive/pulse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vibe }),
  });
  if (!response.ok) throw new Error('Failed to trigger hive pulse');
  return response.json();
};
