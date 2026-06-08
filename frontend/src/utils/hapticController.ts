/**
 * [RM-FE-404] Tactical Haptic Feedback Controller.
 * Provides sensory confirmation for high-stress safety actions.
 */

export const hapticController = {
  /**
   * Short pulse for subtle confirmation.
   */
  light: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate(10);
    }
  },

  /**
   * Medium pulse for standard interaction.
   */
  medium: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate(20);
    }
  },

  /**
   * Heavy pulse for critical confirmation.
   */
  heavy: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate(50);
    }
  },

  /**
   * Rhythmic pattern for Active SOS Escalation.
   */
  sos: () => {
    if ("vibrate" in navigator) {
      // SOS pattern in Morse Code: ... --- ...
      navigator.vibrate([100, 100, 100, 100, 100, 300, 300, 100, 300, 100, 300, 300, 100, 100, 100]);
    }
  },

  /**
   * Error pattern for failed escalation.
   */
  error: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate([200, 100, 200]);
    }
  },

  /**
   * Tactical confirmation for SOS triggers.
   */
  triggerImpact: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate([30, 50, 30, 50, 100]);
    }
  },

  /**
   * Success pulse for resolved safety actions.
   */
  triggerSuccess: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate([10, 30, 10]);
    }
  },

  /**
   * Warning vibration for proximity or delay alerts.
   */
  triggerWarning: () => {
    if ("vibrate" in navigator) {
      navigator.vibrate([100, 50, 100]);
    }
  }
};
