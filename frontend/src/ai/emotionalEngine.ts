/**
 * Emotional AI Intelligence - Triage distress language and map to safety actions.
 */

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskAnalysis {
  level: RiskLevel;
  action: string;
  autoTrigger: boolean;
  message: string;
}

const DISTRESS_KEYWORDS: Record<string, number> = {
  "scared": 2,
  "unsafe": 2,
  "danger": 3,
  "terrified": 4,
  "help": 3,
  "alone": 1,
  "followed": 4,
  "harassed": 4,
  "emergency": 5,
  "police": 3
};

export function analyzeEmotionalRisk(text: string): RiskAnalysis {
  const lower = text.toLowerCase();
  let score = 0;

  Object.entries(DISTRESS_KEYWORDS).forEach(([word, weight]) => {
    if (lower.includes(word)) score += weight;
  });

  if (score >= 5) {
    return {
      level: "critical",
      action: "trigger_sos",
      autoTrigger: false, // Always confirm for SOS unless we add more AI signals
      message: "🚨 I sense an emergency. Should I trigger an immediate SOS for you?"
    };
  }

  if (score >= 3) {
    return {
      level: "high",
      action: "enable_guardian",
      autoTrigger: true, // Auto-enable guardian for high risk
      message: "🛡️ You seem to be in a high-risk situation. I'm enabling Journey Guardian Mode and alerts for your safety."
    };
  }

  if (score >= 2) {
    return {
      level: "medium",
      action: "prompt_safety",
      autoTrigger: false,
      message: "I'm detecting some concern. Would you like me to activate your Safety Shield or alert a contact?"
    };
  }

  return {
    level: "low",
    action: "none",
    autoTrigger: false,
    message: ""
  };
}
