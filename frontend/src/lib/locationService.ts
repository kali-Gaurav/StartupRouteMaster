/**
 * Location Service
 * Handles intelligent location sharing and permissions
 */

import { updateLocation } from './authApi';

export interface LocationData {
  latitude: number;
  longitude: number;
  accuracy?: number;
  timestamp: number;
}

export class LocationService {
  private static watchId: number | null = null;
  private static wakeLock: any = null;
  private static channel = new BroadcastChannel('location-updates');

  /**
   * Register Background Location Worker
   */
  static async registerWorker(): Promise<void> {
    if ('serviceWorker' in navigator) {
      try {
        const registration = await navigator.serviceWorker.register('/location-sw.js', {
          scope: '/'
        });
        console.log('[Location] ServiceWorker registered:', registration.scope);
      } catch (error) {
        console.error('[Location] ServiceWorker registration failed:', error);
      }
    }
  }

  /**
   * Request Screen Wake Lock
   */
  private static async requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        this.wakeLock = await (navigator as any).wakeLock.request('screen');
        console.log('[Location] Wake Lock active');
      }
    } catch (err) {
      console.error('[Location] Wake Lock error:', err);
    }
  }

  /**
   * Start watching location (with background support)
   */
  static async startWatching(
    onUpdate: (location: LocationData) => void,
    onError?: (error: GeolocationPositionError) => void
  ): Promise<void> {
    if (!navigator.geolocation) {
      return;
    }

    // 1. Enable Wake Lock
    await this.requestWakeLock();

    // 2. Register SW
    await this.registerWorker();

    this.watchId = navigator.geolocation.watchPosition(
      (position) => {
        const data: LocationData = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp,
        };

        // Notify UI
        onUpdate(data);

        // Broadcast to Service Worker
        this.channel.postMessage({ type: 'LOCATION_UPDATE', location: data });

        // Update Server
        this.updateServerLocation(data);
      },
      (error) => {
        console.error('Location watch error:', error);
        onError?.(error);
      },
      {
        enableHighAccuracy: true,
        timeout: 30000,
        maximumAge: 5000,
      }
    );
  }

  /**
   * Stop watching location and release locks
   */
  static stopWatching(): void {
    if (this.watchId !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }

    if (this.wakeLock !== null) {
      this.wakeLock.release().then(() => {
        this.wakeLock = null;
        console.log('[Location] Wake Lock released');
      });
    }
  }

  /**
   * Update location on server
   */
  static async updateServerLocation(location: LocationData): Promise<boolean> {
    try {
      const response = await updateLocation(location.latitude, location.longitude);
      return response.success;
    } catch (error) {
      console.error('Failed to update server location:', error);
      return false;
    }
  }

  /**
   * Check if should prompt for location
   * Returns true if:
   * 1. User is logged in
   * 2. Location not already enabled
   * 3. Haven't asked in the last 7 days
   */
  static shouldPromptForLocation(
    isAuthenticated: boolean,
    locationEnabled: boolean
  ): boolean {
    if (!isAuthenticated || locationEnabled) {
      return false;
    }

    const lastPrompt = localStorage.getItem('location_prompt_last');
    if (lastPrompt) {
      const daysSincePrompt = (Date.now() - parseInt(lastPrompt)) / (1000 * 60 * 60 * 24);
      if (daysSincePrompt < 7) {
        return false; // Asked within last 7 days
      }
    }

    return true;
  }

  /**
   * Mark that we've prompted for location
   */
  static markLocationPrompted(): void {
    localStorage.setItem('location_prompt_last', Date.now().toString());
  }

  /**
   * Save location preference
   */
  static saveLocationPreference(enabled: boolean): void {
    localStorage.setItem('location_enabled', enabled.toString());
  }

  /**
   * Get location preference
   */
  static getLocationPreference(): boolean | null {
    const pref = localStorage.getItem('location_enabled');
    if (pref === null) return null;
    return pref === 'true';
  }

  /**
   * Calculate distance between two coordinates (in km)
   * Using Haversine formula
   */
  static calculateDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number
  ): number {
    const R = 6371; // Earth's radius in km
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);

    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRad(lat1)) *
        Math.cos(this.toRad(lat2)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  private static toRad(degrees: number): number {
    return degrees * (Math.PI / 180);
  }

  /**
   * Format location for display
   */
  static formatLocation(latitude: number, longitude: number): string {
    return `${latitude.toFixed(6)}°, ${longitude.toFixed(6)}°`;
  }

  /**
   * Request current location once (used by prompts)
   */
  static async requestLocation(): Promise<LocationData | null> {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation not supported'));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp,
          });
        },
        (err) => reject(err),
        { enableHighAccuracy: true, timeout: 30000 }
      );
    });
  }
}
