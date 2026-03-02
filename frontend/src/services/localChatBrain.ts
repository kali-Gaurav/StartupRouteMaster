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
    keywords: ["scared", "unsafe", "alone", "creep", "followed", "terrified", "help me", "danger"],
    response: "🚨 I'm right here with you. Do you want me to activate Guardian Mode to track your location, or trigger an immediate SOS?",
    action: "PROMPT_SAFETY",
    type: "system_control",
    value: "prompt_safety"
  },
  {
    keywords: ["book", "ticket", "reservation", "seat", "availability"],
    response: "I can help you book a ticket. Please tell me your source and destination (e.g., 'Book from NDLS to MMCT')",
    action: "OPEN_BOOKING",
    type: "navigate",
    value: "/"
  },
  {
    keywords: ["dashboard", "my booking", "history", "stats", "profile"],
    response: "Opening your personal dashboard to view history and stats.",
    action: "OPEN_DASHBOARD",
    type: "navigate",
    value: "/dashboard"
  },
  {
    keywords: ["sos", "emergency", "danger", "panic", "save", "trigger sos", "start sos", "police"],
    response: "🚨 **EMERGENCY MODE DETECTED**\n\nI am triggering an immediate SOS distress signal.",
    action: "TRIGGER_SOS",
    type: "system_control",
    value: "trigger_sos"
  },
  {
    keywords: ["guardian", "guardian mode", "start guardian", "enable guardian", "track me", "share location"],
    response: "🛡️ Activating Journey Guardian Mode. Your live location will be monitored and shared.",
    action: "ENABLE_GUARDIAN",
    type: "system_control",
    value: "enable_guardian"
  },
  {
    keywords: ["safe", "women", "night", "security", "reliable", "safety"],
    response: "Safety is our priority. Every route in RouteMaster is assigned a **Safety Score** based on real-time telemetry and historical data. \n\nI recommend routes with a 'Verified Safe' badge for the best security.",
    action: "VIEW_SAFETY",
    type: "navigate",
    value: "/safety"
  },
  {
    keywords: ["status", "pnr", "running", "where", "late", "delay", "coach", "platform"],
    response: "I can check live running status and PNR for you! Please provide your Train Number or PNR, or view your active journeys in the dashboard.",
    action: "GO_TO_TRACK",
    type: "navigate",
    value: "/dashboard"
  },
  {
    keywords: ["track", "live", "telemetry", "location", "gps"],
    response: "You can track your live journey and share it with family using our **Journey Guardian** mode. Would you like to set it up?",
    action: "OPEN_GUARDIAN",
    type: "navigate",
    value: "/sos"
  },
  {
    keywords: ["help", "what can you do", "features", "diksha", "how", "assist"],
    response: "I am **Diksha**, your AI Rail Assistant. I can handle many things offline:\n\n✅ **Booking** — Find fastest/cheapest routes\n🛡️ **Safety** — SOS, Guardian Mode\n💡 **Info** — Refund rules, Luggage, PNR chances\n📊 **Insights** — View your analytics\n\nHow can I help you right now?",
    action: "SHOW_HELP",
    type: "quick_action"
  },
  {
    keywords: ["hi", "hello", "hey", "greetings", "namaste"],
    response: "Hello! I'm Diksha, your smart local AI brain. I can assist you even when offline. How can I help you with your journey today?",
    action: "GREETING",
    type: "quick_action"
  },
  {
    keywords: ["refund", "cancel", "cancellation", "money back", "deduction"],
    response: "🚆 **Offline Rule Engine: Refund Policy**\n\n- **Before 48 hrs:** ₹120-240 deduction depending on class.\n- **48 hrs to 12 hrs:** 25% deduction.\n- **12 hrs to 4 hrs:** 50% deduction.\n- **Less than 4 hrs/Chart prep:** No refund.\n- **Waitlist (WL):** Auto-refunded if chart is prepared without confirmation (deducting ₹60).",
    action: "REFUND_INFO",
    type: "quick_action"
  },
  {
    keywords: ["luggage", "baggage", "weight", "carry", "bags"],
    response: "🚆 **Offline Rule Engine: Luggage Rules**\n\n- **1AC:** 70 kg free, 150 kg max.\n- **2AC:** 50 kg free, 100 kg max.\n- **3AC / CC:** 40 kg free, 40 kg max.\n- **Sleeper:** 40 kg free, 80 kg max.\n- **General:** 35 kg free, 70 kg max.\nChildren get half allowance. Medical items don't count towards the limit.",
    action: "LUGGAGE_INFO",
    type: "quick_action"
  },
  {
    keywords: ["food", "pantry", "catering", "eat", "meal", "order"],
    response: "🍔 **Offline Rule Engine: e-Catering & Pantry**\n\nIf your train has a pantry car, you can order directly. Otherwise, e-Catering (Domino's, Haldiram's, local restaurants) is available at major junctions (e.g., NDLS, BCT, KANPUR). We recommend ordering 2 hours before the station arrives.",
    action: "FOOD_INFO",
    type: "quick_action"
  },
  {
    keywords: ["rac", "waitlist", "wl", "confirmation", "chance", "probability"],
    response: "🎫 **Offline Rule Engine: PNR & WL Chances**\n\n- **GNWL (General):** Highest chance of confirmation.\n- **PQWL/RLWL (Pooled):** Lower chances.\n- **RAC:** You will get a shared seat (half side-lower berth) and are allowed to board the train.\nWait for chart preparation (4 hrs before departure) for final status.",
    action: "WL_INFO",
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
  // Updated to catch "to", "2", "-", and natural phrasing
  const routeMatch = lower.match(/(?:from\s+)?([a-z0-9]{3,7}|[a-z\s]+?)\s+(?:to|2|-)\s+([a-z0-9]{3,7}|[a-z\s]+)/i);
  const trainNumberMatch = lower.match(/\b(\d{5})\b/); // Matches 5-digit train numbers

  if (trainNumberMatch) {
    return {
      reply: `I see you're asking about train ${trainNumberMatch[1]}. While I can't fetch real-time data offline, you can view schedule details in the dashboard.`,
      actions: [{ label: "Track in Dashboard", type: "navigate", value: "/dashboard" }],
      isLocal: true
    };
  }

  if (routeMatch && routeMatch[1] && routeMatch[2] && routeMatch[1].length > 2 && routeMatch[2].length > 2) {
    const src = (routeMatch[1].trim()).toUpperCase();
    const dest = (routeMatch[2].trim()).toUpperCase();
    // Exclude common false positives
    const ignoreList = ["WHAT", "HOW", "WHY", "WHERE", "WHEN", "CAN", "I", "YOU", "WE"];
    if (!ignoreList.includes(src) && !ignoreList.includes(dest)) {
      return {
        reply: `I've detected a journey request from **${src}** to **${dest}**${dateInfo ? ' on ' + dateInfo : ''}. Searching available trains using my local engine...`,
        isLocal: true,
        triggerSearch: true,
        collected: {
          source: src,
          destination: dest,
          date: dateInfo || undefined
        }
      };
    }
  }

  if (places.length >= 2) {
    return {
      reply: `I've detected a journey request from **${places[0]}** to **${places[1]}**${dateInfo ? ' on ' + dateInfo : ''}. Searching available trains...`,
      isLocal: true,
      triggerSearch: true,
      collected: {
        source: places[0].toUpperCase(),
        destination: places[1].toUpperCase(),
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
