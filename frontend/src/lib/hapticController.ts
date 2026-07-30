/**
 * [RM-UX-106] Tactical Haptic Language Controller.
 * Communicates safety state and dispatch priority through vibrations.
 */

export const HapticSafetyController = {
  /**
   * Heartbeat Pulse: Used for 'Safe' status or active tracking.
   */
  safePulse: () => {
    if (navigator.vibrate) {
      navigator.vibrate([10, 1000]); // Suble periodic pulse
    }
  },

  /**
   * Caution Pulse: Used when entering an 'Elevated Risk' zone.
   */
  cautionPulse: () => {
    if (navigator.vibrate) {
      navigator.vibrate([200, 100, 200]); // Double short pulse
    }
  },

  /**
   * Emergency Dispatch: Heavy jolting vibration for SOS alerts.
   */
  emergencyAlert: () => {
    if (navigator.vibrate) {
      navigator.vibrate([500, 100, 500, 100, 500]); // Long jolting pulses
    }
  },

  /**
   * Proximity Guidance: Frequency increases as responder nears the victim.
   */
  proximityGuide: (distance: number) => {
    if (!navigator.vibrate) return;
    
    // Frequency increases as distance decreases
    const pulseDuration = Math.max(50, distance / 2);
    navigator.vibrate([pulseDuration, 100]);
  }
};
