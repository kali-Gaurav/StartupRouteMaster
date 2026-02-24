/**
 * RailAssistant - IRCTC AskDISHA-style chatbot
 * State machine, action cards, voice, session-based conversational flow.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, Mic, MicOff, Send, X, Bot, User, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { getRailwayApiUrl } from "@/lib/utils";
import { searchStationsApi } from "@/services/railwayBackApi";
import { processLocalIntent } from "@/services/localChatBrain";
import { useBackendHealth } from "@/hooks/useBackendHealth";

// Declare SpeechRecognition for browser compatibility
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition | undefined;
    webkitSpeechRecognition: typeof SpeechRecognition | undefined;
  }
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: (event: SpeechRecognitionEvent) => void;
  onerror: (event: SpeechRecognitionErrorEvent) => void;
  onend: () => void;
  start(): void;
  stop(): void;
  abort(): void;
}

declare const SpeechRecognition: {
  new(): SpeechRecognition;
};

export interface ChatAction {
  label: string;
  type: string;
  value?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  actions?: ChatAction[];
}

const QUICK_ACTIONS = [
  { label: "Book Ticket", type: "quick_action" },
  { label: "Search Trains", type: "quick_action" },
  { label: "Delhi to Mumbai", type: "quick_action" },
  { label: "Dashboard", type: "quick_action" },
  { label: "Open in Telegram", type: "quick_action" },
  { label: "SOS", type: "quick_action" },
  { label: "Help", type: "quick_action" },
];

const WELCOME_MSG = `🚂 **Welcome to Rail Assistant!**

Hi! I'm **Diksha**, your AI-powered travel companion for Indian Railways.

✨ **What I can help you with:**

🎫 **Book Tickets** — Search trains between any stations
   _Try: "Book ticket from Delhi to Mumbai"_

📊 **Dashboard** — View your journey stats & analytics

🆘 **Emergency SOS** — Get help with live location sharing

📱 **Telegram Mini App** — Track journeys & manage saved routes

📖 **Journey History** — View all your past travels

💡 **Quick Actions** — Tap any button below to get started!

---

**Popular Routes:** Delhi-Mumbai • Chennai-Bangalore • Howrah-Delhi

How can I assist you today? 😊`;

export interface RailAssistantChatbotProps {
  /** Phase 6: optional correlationId for flow tracker when trigger_search is true */
  onSearchRequest?: (fromCode: string, toCode: string, date?: string, correlationId?: string) => void;
  onSortChange?: (sortBy: "duration" | "cost") => void;
  onNavigate?: (path: string) => void;
  className?: string;
}

function generateSessionId() {
  return "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const TELEGRAM_BOT_URL = "https://t.me/RoutemasternagarindustrisBot";

export function RailAssistantChatbot({ onSearchRequest, onSortChange, onNavigate, className }: RailAssistantChatbotProps) {
  const isBackendOnline = useBackendHealth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date(), actions: QUICK_ACTIONS },
  ]);
  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const sessionIdRef = useRef<string>(generateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(() => { scrollToBottom(); }, [messages]);

  const addMessage = useCallback((role: "user" | "assistant", content: string, actions?: ChatAction[]) => {
    setMessages((prev) => [...prev, { id: `msg-${Date.now()}`, role, content, timestamp: new Date(), actions }]);
  }, []);

  const resolveAndTriggerSearch = useCallback(
    async (
      collected: { source?: string; destination?: string; from?: string; to?: string; date?: string },
      correlationId?: string
    ): Promise<boolean> => {
      const src = (collected.source ?? collected.from ?? "").trim();
      const dest = (collected.destination ?? collected.to ?? "").trim();
      if (!src || !dest) return false;
      try {
        const [fromStations, toStations] = await Promise.all([searchStationsApi(src), searchStationsApi(dest)]);
        const fromCode = fromStations[0]?.code;
        const toCode = toStations[0]?.code;
        if (fromCode && toCode) {
          const useDate = collected.date?.trim() || new Date().toISOString().slice(0, 10);
          onSearchRequest?.(fromCode, toCode, useDate, correlationId);
          return true;
        }
        addMessage("assistant", "Could not find stations for that route. Please try different names (e.g. New Delhi, Mumbai Central).", undefined);
        return false;
      } catch {
        addMessage("assistant", "Station lookup failed. Please try the search form above with station names or codes.", undefined);
        return false;
      }
    },
    [onSearchRequest, addMessage]
  );

  const sendToBackend = useCallback(
    async (text: string) => {
      try {
        const res = await fetch(getRailwayApiUrl("/chat"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
        });
        const data = await res.json().catch(() => ({}));
        const reply = data.reply || data.message || "";
        const actions = Array.isArray(data.actions) ? data.actions : [];

        if (!res.ok) {
          addMessage("assistant", (reply || "Backend returned an error. Please try again.").replace(/\*\*/g, ""), undefined);
          return;
        }

        addMessage("assistant", reply.replace(/\*\*/g, ""), actions.length ? actions : undefined);

        // Dispatch UI-friendly suggestion events when backend returns action buttons
        if (Array.isArray(actions) && actions.length > 0) {
          try {
            const suggestions = actions.map((a: ChatAction) => {
              // Try to parse route-like labels (e.g. "Delhi to Mumbai" or "NDLS - BCT")
              const label: string = String(a.label ?? "");
              const routeMatch = label.match(/\s*([^\-–—:→]+?)\s*(?:to|-|→|\u2013|\u2014)\s*([^\-–—:→]+?)\s*$/i);
              const fromName = routeMatch ? routeMatch[1].trim() : undefined;
              const toName = routeMatch ? routeMatch[2].trim() : undefined;
              return { label, type: a.type, value: a.value, fromName, toName };
            });
            window.dispatchEvent(new CustomEvent("rail-assistant-suggestions", { detail: { suggestions } }));
          } catch {
            /* non-fatal */
          }
        }

        if (data.trigger_search && data.collected) {
          const triggered = await resolveAndTriggerSearch(data.collected, data.correlation_id);
          if (triggered) addMessage("assistant", "✓ Search done! Check the results above.", undefined);
        }
      } catch {
        addMessage(
          "assistant",
          "⚠️ **Backend Connection Issue**\n\nI can still help you with cached routes for these major junctions:\n\n• **Delhi → Mumbai** (NDLS → BCT)\n• **Kolkata → Delhi** (HWH → NDLS)\n• **Chennai → Bangalore** (MAS → SBC)\n• **Pune → Delhi** (PUNE → NDLS)\n• **Lucknow → Mumbai** (LKO → BCT)\n\nYou can also access Dashboard, SOS, or open in Telegram!",
          [
            { label: "Delhi to Mumbai", type: "intent", value: "search" },
            { label: "Dashboard", type: "navigate", value: "/dashboard" },
            { label: "Open in Telegram", type: "open_url", value: TELEGRAM_BOT_URL },
            { label: "SOS", type: "navigate", value: "/sos" },
          ]
        );
      }
    },
    [addMessage, resolveAndTriggerSearch]
  );

  const handleActionClick = useCallback(
    (action: ChatAction) => {
      if (action.type === "open_url" && action.value) {
        window.open(action.value, "_blank", "noopener,noreferrer");
        addMessage("assistant", "Opened in a new tab. You can use the Telegram Mini App there.", undefined);
        return;
      }
      if (action.type === "navigate" && action.value) {
        onNavigate?.(action.value);
        addMessage("assistant", `Taking you to ${action.label || action.value}.`, undefined);
        return;
      }
      if (action.type === "sort" && action.value) {
        onSortChange?.(action.value as "duration" | "cost");
        addMessage("assistant", `Showing ${action.label.toLowerCase()} routes.`, undefined);
        return;
      }
      const payload = action.value || action.label;
      addMessage("user", payload);
      setIsLoading(true);

      // Try local brain for actions too
      const localResult = processLocalIntent(payload);
      if (localResult) {
        addMessage("assistant", localResult.reply, localResult.actions);
        if (localResult.triggerSearch && localResult.collected) {
          resolveAndTriggerSearch(localResult.collected);
        }
        setIsLoading(false);
        return;
      }

      sendToBackend(payload).finally(() => setIsLoading(false));
    },
    [addMessage, onSortChange, onNavigate, sendToBackend, resolveAndTriggerSearch]
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    addMessage("user", text);
    setIsLoading(true);

    // 1. Try local intent processor first (Instant/Offline)
    const localResult = processLocalIntent(text);
    if (localResult) {
      addMessage("assistant", localResult.reply, localResult.actions);
      if (localResult.triggerSearch && localResult.collected) {
        await resolveAndTriggerSearch(localResult.collected);
      }
      setIsLoading(false);
      return;
    }

    // 2. Fallback to backend AI
    try {
      await sendToBackend(text);
    } finally {
      setIsLoading(false);
    }
  }, [input, addMessage, sendToBackend, resolveAndTriggerSearch]);

  const handleQuickAction = (label: string) => {
    if (label === "Open in Telegram") {
      window.open(TELEGRAM_BOT_URL, "_blank", "noopener,noreferrer");
      addMessage("assistant", "Opened Telegram. You can use the Mini App there for tracking and saved routes.", undefined);
      return;
    }
    if (label === "Dashboard") {
      onNavigate?.("/dashboard");
      addMessage("assistant", "Taking you to the Dashboard.", undefined);
      return;
    }
    if (label === "SOS") {
      onNavigate?.("/sos");
      addMessage("assistant", "Taking you to the SOS page. Stay safe.", undefined);
      return;
    }
    if (label === "Help") {
      addMessage("user", "What can you do?");
      setIsLoading(true);
      sendToBackend("What can you do?").finally(() => setIsLoading(false));
      return;
    }
    if (label.includes(" to ")) {
      addMessage("user", `Search trains ${label}`);
      setIsLoading(true);
      
      const localResult = processLocalIntent(label);
      if (localResult) {
        addMessage("assistant", localResult.reply, localResult.actions);
        if (localResult.triggerSearch && localResult.collected) {
          resolveAndTriggerSearch(localResult.collected);
        }
        setIsLoading(false);
        return;
      }
      sendToBackend(`Search trains ${label}`).finally(() => setIsLoading(false));
    } else {
      addMessage("user", label);
      setIsLoading(true);
      
      const localResult = processLocalIntent(label);
      if (localResult) {
        addMessage("assistant", localResult.reply, localResult.actions);
        setIsLoading(false);
        return;
      }
      sendToBackend(label).finally(() => setIsLoading(false));
    }
  };

  const toggleVoice = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      addMessage("assistant", "Voice input is not supported. Try Chrome or Edge.");
      return;
    }
    const SR = (window as unknown as { SpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition;
    if (!SR) return;

    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "en-IN";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      const t = e.results[0][0].transcript;
      setInput((prev) => (prev ? `${prev} ${t}` : t));
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognition.start();
    setIsListening(true);
  };

  return (
    <div className={cn("fixed bottom-6 right-6 z-50 flex flex-col items-end", className)}>
      {isOpen && (
        <div
          className={cn(
            "w-full max-w-[420px] h-[600px] md:h-[640px]",
            "bg-white dark:bg-card border-2 border-border rounded-2xl shadow-2xl",
            "flex flex-col overflow-hidden",
            "animate-in slide-in-from-bottom-4 duration-300"
          )}
        >
          {/* AskDisha-style header - dark blue */}
          <div className="flex items-center justify-between px-5 py-4 bg-[#0f172a] dark:bg-[#0c4a6e]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center shrink-0 border border-white/10 relative">
                <Bot className="w-6 h-6 text-white" />
                <div className={cn(
                  "absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#0f172a]",
                  isBackendOnline ? "bg-green-500" : "bg-orange-500"
                )} title={isBackendOnline ? "Backend Live" : "Backend Offline - Local Brain Active"} />
              </div>
              <div>
                <h3 className="font-bold text-base text-white leading-none mb-1">Rail Assistant 2.0</h3>
                <p className="text-[10px] text-white/60 font-semibold tracking-wider uppercase">
                  {isBackendOnline ? "🟢 AI Live" : "🟠 Local Brain"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleQuickAction("Book Ticket")}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/20 hover:bg-white/30 text-white text-sm font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                Book Ticket
              </button>
              <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/20 rounded-lg transition-colors">
                <X className="w-5 h-5 text-white" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-muted/20">
            {messages.map((m) => (
              <div key={m.id} className={cn("flex gap-3", m.role === "user" ? "flex-row-reverse" : "flex-row")}>
                <div
                  className={cn(
                    "w-8 h-8 shrink-0 rounded-full flex items-center justify-center",
                    m.role === "user" ? "bg-primary/20" : "bg-primary"
                  )}
                >
                  {m.role === "user" ? <User className="w-4 h-4 text-primary" /> : <Bot className="w-4 h-4 text-white" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                      m.role === "user"
                        ? "bg-primary text-primary-foreground rounded-tr-sm ml-auto"
                        : "bg-secondary text-foreground rounded-tl-sm"
                    )}
                  >
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  </div>
                  {m.actions && m.actions.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {m.actions.map((a, i) => (
                        <button
                          key={i}
                          onClick={() => handleActionClick(a)}
                          className="px-3 py-1.5 rounded-full text-xs font-medium bg-primary/15 text-primary hover:bg-primary/25 border border-primary/30 transition-colors"
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 shrink-0 rounded-full bg-primary flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-secondary rounded-2xl rounded-tl-sm px-4 py-2">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 border-t border-border bg-white dark:bg-card space-y-2">
            <div className="flex flex-wrap gap-2">
              {QUICK_ACTIONS.map((a) => (
                <button
                  key={a.label}
                  onClick={() => handleQuickAction(a.label)}
                  className="px-3 py-2 rounded-full text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  {a.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                placeholder="Type or Ask Rail Assistant..."
                className="flex-1 px-4 py-3 rounded-xl border-2 border-border bg-background text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none text-sm"
              />
              <button
                onClick={toggleVoice}
                className={cn("p-3 rounded-xl transition-colors shrink-0", isListening ? "bg-red-500 text-white" : "bg-secondary hover:bg-secondary/80")}
                title="Voice"
              >
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="p-3 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            {/* Footer links - AskDisha style; Open in Telegram opens bot on mobile */}
            <div className="flex flex-wrap gap-3 pt-2 text-xs text-muted-foreground items-center">
              <a
                href={TELEGRAM_BOT_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-foreground transition-colors font-medium text-primary"
              >
                Open in Telegram
              </a>
              <span className="text-muted-foreground/60">|</span>
              <a href="#" className="hover:text-foreground transition-colors">Terms of Use</a>
              <a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn("w-14 h-14 rounded-full bg-primary text-white shadow-lg hover:scale-105 transition-transform flex items-center justify-center")}
      >
        <MessageCircle className="w-7 h-7" />
      </button>
    </div>
  );
}
