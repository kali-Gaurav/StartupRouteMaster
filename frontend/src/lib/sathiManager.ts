import { auth } from "@/lib/firebase";

export class SathiManager {
  private static heartbeatInterval: any = null;

  /**
   * Start sending location heartbeats to the backend.
   */
  static async startTracking(onLocationUpdate?: (lat: number, lon: number) => void) {
    if (this.heartbeatInterval) return;

    const update = async () => {
      if (!navigator.geolocation) return;

      navigator.geolocation.getCurrentPosition(async (pos) => {
        const { latitude, longitude } = pos.coords;
        onLocationUpdate?.(latitude, longitude);

        try {
          const user = auth.currentUser;
          if (!user) return;
          const token = await user.getIdToken();

          const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
          await fetch(`${apiUrl}/api/v2/sathi/location?lat=${latitude}&lng=${longitude}&status=available`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });
          console.log("[SathiManager] Heartbeat sent.");
        } catch (err) {
          console.error("[SathiManager] Heartbeat failed", err);
        }
      });
    };

    // Initial update
    await update();
    
    // Set interval (every 60 seconds for safety/battery balance)
    this.heartbeatInterval = setInterval(update, 60000);
  }

  /**
   * Stop heartbeats.
   */
  static stopTracking() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
      console.log("[SathiManager] Heartbeat stopped.");
    }
  }

  /**
   * Check if tracking is active.
   */
  static isTracking() {
    return this.heartbeatInterval !== null;
  }
}
