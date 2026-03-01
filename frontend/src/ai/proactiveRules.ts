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
  const suggestions: ProactiveSuggestion[] = [];

  // Rule 1: Late night journey without Guardian
  if (ctx.journeyActive && !ctx.guardianActive && (ctx.timeOfDay !== undefined && (ctx.timeOfDay >= 22 || ctx.timeOfDay <= 4))) {
    suggestions.push({
      message: "It's late at night. For your safety, would you like to enable Journey Guardian?",
      action: { label: "Enable Guardian", type: "system_control", value: "enable_guardian" }
    });
  }

  // Rule 2: Approaching Major Junction
  if (ctx.journeyActive && !ctx.guardianActive && ctx.currentStationCode && MAJOR_JUNCTIONS.includes(ctx.currentStationCode)) {
    suggestions.push({
      message: `You are approaching ${ctx.currentStationCode}, a busy junction. I recommend enabling your Safety Shield.`,
      action: { label: "Enable Shield", type: "system_control", value: "enable_guardian" }
    });
  }

  // Rule 3: Low safety score route
  if (ctx.safetyScore && ctx.safetyScore < 70) {
    suggestions.push({
      message: "This route has a lower safety score than usual. I recommend sharing your live location with family.",
      action: { label: "Share Journey", type: "navigate", value: "/sos" }
    });
  }

  // Rule 4: High emotional risk detected (user seems stressed)
  if (ctx.emotionalRisk && ctx.emotionalRisk >= 3) {
    suggestions.push({
      message: "I've detected you might be feeling unsafe. Should I activate the Emergency Shield?",
      action: { label: "Activate Shield", type: "system_control", value: "enable_guardian" }
    });
  }

  return suggestions;
}
