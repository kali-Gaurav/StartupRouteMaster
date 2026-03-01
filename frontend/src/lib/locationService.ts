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

  /**
   * Check if location permission is granted
   */
  static async checkPermission(): Promise<PermissionState | null> {
    if (!navigator.permissions) {
      return null;
    }

    try {
      const result = await navigator.permissions.query({ name: 'geolocation' });
      return result.state;
    } catch (error) {
      console.error('Failed to check location permission:', error);
      return null;
    }
  }

  /**
   * Request location permission and get current location
   */
  static async requestLocation(): Promise<LocationData | null> {
    if (!navigator.geolocation) {
      throw new Error('Geolocation not supported');
    }

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp,
          });
        },
        (error) => {
          reject(error);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0,
        }
      );
    });
  }

  /**
   * Start watching location (for active journey tracking)
   */
  static startWatching(
    onUpdate: (location: LocationData) => void,
    onError?: (error: GeolocationPositionError) => void
  ): void {
    if (!navigator.geolocation) {
      return;
    }

    this.watchId = navigator.geolocation.watchPosition(
      (position) => {
        onUpdate({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp,
        });
      },
      (error) => {
        console.error('Location watch error:', error);
        onError?.(error);
      },
      {
        enableHighAccuracy: true,
        timeout: 30000,
        maximumAge: 5000, // Update every 5 seconds
      }
    );
  }

  /**
   * Stop watching location
   */
  static stopWatching(): void {
    if (this.watchId !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
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
}
