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
    keywords: ["sos", "emergency", "help", "danger"],
    response: "🚨 Emergency mode activated. I'm sharing your location with emergency contacts and railway authorities.",
    action: "ACTIVATE_SOS",
    type: "quick_action"
  },
  {
    keywords: ["help", "what can you do", "features", "diksha"],
    response: "I am Diksha, your AI Rail Assistant. I can help with:\n- Booking tickets\n- Finding trains\n- Checking journey status\n- Emergency SOS\n- Dashboard analytics",
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
  const dateInfo = (doc as any).dates().at(0).format('{month} {day} {year}').out('text');
  
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
