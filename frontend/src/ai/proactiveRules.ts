/**
 * Proactive AI Rules Engine - Diksha initiates actions based on telemetry.
 */

export interface ProactiveContext {
  journeyActive?: boolean;
  guardianActive?: boolean;
  safetyScore?: number;
  timeOfDay?: number; // 0-23
  emotionalRisk?: number; // 0-5
  currentStationCode?: string;
  upcomingJourneyDelay?: number; // Task 6.1: Minutes late
  upcomingPNRExpiryHours?: number; // Task 6.2: Hours until journey
  surgeLevel?: string; // VPS integration
}

export interface ProactiveSuggestion {
  message: string;
  action: {
    label: string;
    type: string;
    value: string;
  };
}

const MAJOR_JUNCTIONS = ["KOTA", "AGC", "VGLJ", "BSB", "HWH", "NDLS", "MAS", "SBC"];

export function evaluateProactiveRules(ctx: ProactiveContext): ProactiveSuggestion[] {
  // Task 6.8: Disable ML processing entirely during Level 2 Surge
  if (ctx.surgeLevel === 'High' || ctx.surgeLevel === 'Critical') {
    return [];
  }

  const suggestions: ProactiveSuggestion[] = [];

  // Rule 1: Late night journey without Guardian
  if (ctx.journeyActive && !ctx.guardianActive && (ctx.timeOfDay !== undefined && (ctx.timeOfDay >= 22 || ctx.timeOfDay <= 4))) {
    suggestions.push({
      message: "It's late at night. For your safety, would you like to enable Journey Guardian?",
      action: { label: "Enable Guardian", type: "system_control", value: "enable_guardian" }
    });
  }

  // Rule 2: Task 6.1: Predictive Delay Alert
  if (ctx.upcomingJourneyDelay && ctx.upcomingJourneyDelay > 15) {
    suggestions.push({
      message: `Operational Alert: Your upcoming train is delayed by ${ctx.upcomingJourneyDelay} minutes. Should I monitor alternate connections?`,
      action: { label: "Monitor Delay", type: "navigate", value: "/dashboard" }
    });
  }

  // Rule 3: Task 6.2: PNR Expiry Reminder
  if (ctx.upcomingPNRExpiryHours && ctx.upcomingPNRExpiryHours <= 4 && ctx.upcomingPNRExpiryHours > 0) {
    suggestions.push({
      message: "Mission Start T-4 Hours. Ready to verify final PNR status and platform telemetry?",
      action: { label: "Final PNR Check", type: "intent", value: "PNR Status" }
    });
  }

  // Rule 4: Approaching Major Junction
  if (ctx.journeyActive && !ctx.guardianActive && ctx.currentStationCode && MAJOR_JUNCTIONS.includes(ctx.currentStationCode)) {
    suggestions.push({
      message: `Approaching ${ctx.currentStationCode} (Major Junction). Recommended: Activate Safety Shield.`,
      action: { label: "Enable Shield", type: "system_control", value: "enable_guardian" }
    });
  }

  // Rule 5: Low safety score route
  if (ctx.safetyScore && ctx.safetyScore < 70) {
    suggestions.push({
      message: "Logistics analysis: This route has a low safety score. Enable live location sharing?",
      action: { label: "Share Journey", type: "navigate", value: "/sos" }
    });
  }

  // Rule 6: High emotional risk detected
  if (ctx.emotionalRisk && ctx.emotionalRisk >= 3) {
    suggestions.push({
      message: "Biometric stress detected. Would you like to initialize the Emergency Guardian?",
      action: { label: "Activate Guardian", type: "system_control", value: "enable_guardian" }
    });
  }

  return suggestions;
}
