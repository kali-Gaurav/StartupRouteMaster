import nlp from 'compromise';
import dates from 'compromise-dates';

// Extend nlp with dates plugin
const nlpExtended = nlp.extend(dates as any);

/**
 * Local Chat Intelligence - Offline Intent Processor
 */

export interface ChatIntent {
  keywords: string[];
  response: string;
  action?: string;
  type?: string;
  value?: string;
}

export const INTENTS: ChatIntent[] = [
  {
    keywords: ["scared", "unsafe", "alone", "creep", "followed", "terrified", "help me"],
    response: "🚨 I'm right here with you. Do you want me to activate Guardian Mode to track your location, or trigger an immediate SOS?",
    action: "PROMPT_SAFETY",
    type: "system_control",
    value: "prompt_safety"
  },
  {
    keywords: ["book", "ticket", "reservation", "seat"],
    response: "I can help you book a ticket. Please tell me your source and destination (e.g., 'Book from NDLS to MMCT')",
    action: "OPEN_BOOKING",
    type: "navigate",
    value: "/"
  },
  {
    keywords: ["dashboard", "my booking", "history", "stats"],
    response: "Opening your personal dashboard to view history and stats.",
    action: "OPEN_DASHBOARD",
    type: "navigate",
    value: "/dashboard"
  },
  {
    keywords: ["sos", "emergency", "danger", "panic", "save", "trigger sos", "start sos"],
    response: "🚨 **EMERGENCY MODE DETECTED**\n\nI am triggering an immediate SOS distress signal.",
    action: "TRIGGER_SOS",
    type: "system_control",
    value: "trigger_sos"
  },
  {
    keywords: ["guardian", "guardian mode", "start guardian", "enable guardian"],
    response: "🛡️ Activating Journey Guardian Mode. Your live location will be monitored and shared.",
    action: "ENABLE_GUARDIAN",
    type: "system_control",
    value: "enable_guardian"
  },
  {
    keywords: ["safe", "women", "night", "security", "reliable"],
    response: "Safety is our priority. Every route in RouteMaster is assigned a **Safety Score** based on real-time telemetry and historical data. \n\nI recommend routes with a 'Verified Safe' badge for the best security.",
    action: "VIEW_SAFETY",
    type: "navigate",
    value: "/safety"
  },
  {
    keywords: ["status", "pnr", "running", "where", "late", "delay"],
    response: "I can check live running status and PNR for you! Please provide your Train Number or PNR, or view your active journeys in the dashboard.",
    action: "GO_TO_TRACK",
    type: "navigate",
    value: "/dashboard"
  },
  {
    keywords: ["track", "live", "telemetry", "location"],
    response: "You can track your live journey and share it with family using our **Journey Guardian** mode. Would you like to set it up?",
    action: "OPEN_GUARDIAN",
    type: "navigate",
    value: "/sos"
  },
  {
    keywords: ["help", "what can you do", "features", "diksha", "how"],
    response: "I am **Diksha**, your AI Rail Assistant. I can help with:\n\n✅ **Booking** — Find fastest/cheapest routes\n🛡️ **Safety** — Trigger SOS or Guardian Mode\n📊 **Insights** — View your journey analytics\n📱 **Tracking** — Live GPS route monitoring\n\nHow can I help you right now?",
    action: "SHOW_HELP",
    type: "quick_action"
  },
  {
    keywords: ["hi", "hello", "hey", "greetings"],
    response: "Hello! I'm Diksha. How can I help you with your journey today?",
    action: "GREETING",
    type: "quick_action"
  }
];

export interface ProcessedIntent {
  reply: string;
  actions?: any[];
  action?: string;
  isLocal: boolean;
  triggerSearch?: boolean;
  collected?: { source?: string; destination?: string; date?: string };
}

export function processLocalIntent(text: string): ProcessedIntent | null {
  const lower = text.toLowerCase().trim();
  const doc = nlpExtended(text);

  // 1. NLP Entity Extraction for Routes
  // Patterns like "Delhi to Mumbai tomorrow" or "From NDLS to MMCT on Friday"
  const places = doc.places().out('array');
  const dateEntities = (doc as any).dates();
  const dateInfo = dateEntities.length > 0 
    ? dateEntities.at(0).format('{month} {day} {year}').out('text')
    : "";
  
  // Custom Regex for common railway patterns if NLP misses code-like names (e.g. NDLS)
  const routeMatch = lower.match(/(?:from\s+)?([a-z0-9]{3,7}|[a-z\s]+)\s+(?:to|2)\s+([a-z0-9]{3,7}|[a-z\s]+)/i);

  if (routeMatch || places.length >= 2) {
    const src = (routeMatch ? routeMatch[1].trim() : places[0]).toUpperCase();
    const dest = (routeMatch ? routeMatch[2].trim() : places[1]).toUpperCase();
    
    return {
      reply: `I've detected a journey request from ${src} to ${dest}${dateInfo ? ' on ' + dateInfo : ''}. Searching available trains...`,
      isLocal: true,
      triggerSearch: true,
      collected: {
        source: src,
        destination: dest,
        date: dateInfo || undefined
      }
    };
  }

  // 3. Status Queries
  if (lower.match(/(train|pnr|status|where)/)) {
    return {
      reply: "I can search for trains between stations now! For live PNR or real-time running status, I'll need a backend connection, but I can show you your recent searches offline.",
      actions: [{ label: "Show Recent History", type: "navigate", value: "/dashboard" }],
      isLocal: true
    };
  }

  // 2. Keyword/Intent Matching
  for (const intent of INTENTS) {
    if (intent.keywords.some(k => lower.includes(k))) {
      return {
        reply: intent.response,
        action: intent.action,
        actions: intent.action ? [{ label: intent.action.replace(/_/g, " "), type: intent.type, value: intent.value }] : [],
        isLocal: true
      };
    }
  }

  // 3. Fallback for ambiguous help requests
  if (lower.includes("how") || lower.includes("what") || lower.includes("search")) {
     return {
        reply: "You can find trains by saying something like 'Delhi to Mumbai' or 'NDLS to MMCT'. Or ask for 'Help' to see what else I can do!",
        isLocal: true
     };
  }

  return null; // Let the backend (if online) handle complex queries
}
