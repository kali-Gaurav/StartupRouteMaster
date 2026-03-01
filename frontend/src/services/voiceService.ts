/**
 * Voice Service - Multi-lingual audio feedback for safety actions.
 * Used for SOS triggers, Shield activation, and emergency guidance.
 */

type VoiceFeedbackType = "sos_triggered" | "shield_active" | "trip_ended" | "emergency_contact_alerted" | "guardian_active";

const MESSAGES: Record<VoiceFeedbackType, string> = {
  sos_triggered: "Emergency distress signal active. Railway Police and emergency responders have been alerted with your live location. Stay calm, help is on the way.",
  shield_active: "Proactive safety shield activated. Your live location is now being monitored by our security engine.",
  trip_ended: "Safety session ended. You are now marked as safe. Thank you for using Route Master.",
  emergency_contact_alerted: "Your emergency contacts have been notified of your current location.",
  guardian_active: "Journey Guardian enabled. Family tracking active and AI risk monitoring engaged. We are watching over your journey."
};

class VoiceService {
  private static instance: VoiceService;
  private synth: SpeechSynthesis | null = null;
  private enabled: boolean = true;

  private constructor() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      this.synth = window.speechSynthesis;
    }
  }

  public static getInstance(): VoiceService {
    if (!VoiceService.instance) {
      VoiceService.instance = new VoiceService();
    }
    return VoiceService.instance;
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }

  /**
   * Speak a predefined feedback message.
   */
  public speak(type: VoiceFeedbackType) {
    if (!this.synth || !this.enabled) return;

    // Stop any ongoing speech
    this.synth.cancel();

    const utterance = new SpeechSynthesisUtterance(MESSAGES[type]);
    utterance.rate = 0.9; // Slightly slower for clarity
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    // Try to find a clear English voice (female often sounds better for safety systems)
    const voices = this.synth.getVoices();
    const preferredVoice = voices.find(v => v.lang.startsWith("en") && (v.name.includes("Female") || v.name.includes("Google")));
    if (preferredVoice) utterance.voice = preferredVoice;

    this.synth.speak(utterance);
  }

  /**
   * Speak custom text (use sparingly for UI consistency).
   */
  public speakText(text: string) {
    if (!this.synth || !this.enabled) return;
    this.synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    this.synth.speak(utterance);
  }
}

export const voiceService = VoiceService.getInstance();
