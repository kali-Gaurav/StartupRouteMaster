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
import { logEvent } from "@/lib/observability";
import { loadMemory, saveMemory } from "@/ai/persistentMemory";
import { evaluateProactiveRules } from "@/ai/proactiveRules";
import { listenWakeWord } from "@/ai/wakeWord";
import { analyzeEmotionalRisk } from "@/ai/emotionalEngine";
import { voiceService } from "@/services/voiceService";

// Declare SpeechRecognition for browser compatibility
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition | undefined;
    webkitSpeechRecognition: typeof SpeechRecognition | undefined;
  }
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
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

interface ConversationState {
  lastIntent: string | null;
  searchQuery: any | null;
  journeyActive: boolean;
}

const QUICK_ACTIONS = [
  { label: "Book Ticket", type: "quick_action" },
  { label: "Search Trains", type: "quick_action" },
  { label: "Delhi to Mumbai", type: "quick_action" },
  { label: "Safety Guarantee", type: "quick_action" },
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

  const [conversationState, setConversationState] = useState<ConversationState>({
    lastIntent: null,
    searchQuery: null,
    journeyActive: false,
  });

  const [pendingAction, setPendingAction] = useState<ChatAction | null>(null);
  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);

  // Initialize Memory
  useEffect(() => {
    const memory = loadMemory();
    if (memory.lastIntent) {
      setConversationState(prev => ({ 
        ...prev, 
        lastIntent: memory.lastIntent || null,
        journeyActive: !!memory.journeyActive
      }));
    }

    // Sync from Backend if authenticated
    const syncFromBackend = async () => {
      try {
        const res = await fetch(getRailwayApiUrl("/chat/memory"));
        if (res.ok) {
          const data = await res.json();
          if (data.memory && Object.keys(data.memory).length > 0) {
            saveMemory(data.memory); // Update local
            setConversationState(prev => ({
              ...prev,
              lastIntent: data.memory.lastIntent || prev.lastIntent,
              journeyActive: data.memory.journeyActive !== undefined ? data.memory.journeyActive : prev.journeyActive
            }));
          }
        }
      } catch (e) { /* background sync, fail silently */ }
    };
    syncFromBackend();
  }, []);

  // Persistence Sink
  useEffect(() => {
    const mem = {
      lastIntent: conversationState.lastIntent || undefined,
      journeyActive: conversationState.journeyActive,
      guardianActive: conversationState.lastIntent === "enable_guardian"
    };
    saveMemory(mem);

    // Background push to backend
    const syncToBackend = async () => {
      try {
        await fetch(getRailwayApiUrl("/chat/memory"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ memory: mem })
        });
      } catch (e) { /* silent */ }
    };
    syncToBackend();
  }, [conversationState]);

  // Wake-word Listener
  useEffect(() => {
    if (!wakeWordEnabled) return;
    const cleanup = listenWakeWord(() => {
      setIsOpen(true);
      logEvent("chatbot_wake_word_detected");
      // Provide a small audio hint
      const audio = new Audio("https://assets.mixkit.co/active_storage/sfx/2354/2354-preview.mp3");
      audio.volume = 0.2;
      audio.play().catch(() => {});
    });
    return cleanup;
  }, [wakeWordEnabled, isOpen]); // isOpen dependency helps reset if needed

  const scrollToBottom = () => {
    if (messagesEndRef.current?.scrollIntoView) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };
  useEffect(() => { scrollToBottom(); }, [messages]);

  const addMessage = useCallback((role: "user" | "assistant", content: string, actions?: ChatAction[]) => {
    setMessages((prev) => [...prev, { id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, role, content, timestamp: new Date(), actions }]);
  }, []);

  // Proactive AI Engine
  const triggerProactiveSuggestions = useCallback(() => {
    const ctx = {
      journeyActive: conversationState.journeyActive,
      timeOfDay: new Date().getHours(),
      guardianActive: conversationState.lastIntent === "enable_guardian"
    };
    
    const suggestions = evaluateProactiveRules(ctx);
    if (suggestions.length > 0) {
      const suggestion = suggestions[0];
      addMessage("assistant", `✨ AI Hint: ${suggestion.message}`, [suggestion.action]);
      logEvent("chatbot_proactive_suggestion_shown", { type: suggestion.action.value });
    }
  }, [conversationState, addMessage]);

  // Trigger proactive check every 2 minutes or on journey state change
  useEffect(() => {
    const timer = setInterval(triggerProactiveSuggestions, 120000);
    return () => clearInterval(timer);
  }, [triggerProactiveSuggestions]);

  const resolveAndTriggerSearch = useCallback(
    async (
      collected: { source?: string; destination?: string; from?: string; to?: string; date?: string },
      correlationId?: string
    ): Promise<boolean> => {
      const src = (collected.source ?? collected.from ?? "").trim();
      const dest = (collected.destination ?? collected.to ?? "").trim();
      if (!src || !dest) return false;
      
      setConversationState(prev => ({ ...prev, searchQuery: collected, lastIntent: "search" }));

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
          body: JSON.stringify({ message: text, session_id: sessionIdRef.current, context: conversationState }),
        });
        const data = await res.json().catch(() => ({}));
        const reply = data.reply || data.message || "";
        const actions = Array.isArray(data.actions) ? data.actions : [];

        if (data.state) {
          setConversationState(prev => ({ ...prev, lastIntent: data.state }));
        }

        if (!res.ok) {
          addMessage("assistant", (reply || "Backend returned an error. Please try again.").replace(/\*\*/g, ""), undefined);
          return;
        }

        // Smart Suggestions Engine: Dynamically append actions based on AI state
        let finalActions = [...actions];
        if (data.trigger_search && data.collected) {
           finalActions.push({ label: "Start Guardian", type: "system_control", value: "enable_guardian" });
        }

        addMessage("assistant", reply.replace(/\*\*/g, ""), finalActions.length ? finalActions : undefined);

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

        // Confidence-Based Automation Engine
        const confidence = data.confidence ?? 0;
        const intent = data.intent;
        
        if (intent && confidence > 0.85) {
           // High Confidence: Auto-execute
           executeAction(data.actions?.[0]?.type || "navigate", data.actions?.[0]?.value);
        } else if (intent && confidence > 0.6) {
           // Medium Confidence: Prompt for Confirmation
           setPendingAction({ label: "Confirm Action", type: "system_control", value: intent });
           addMessage("assistant", `I think you want to ${intent.replace(/_/g, " ")}. Should I proceed?`);
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
    [addMessage, resolveAndTriggerSearch, conversationState]
  );

  // Universal Action Engine
  const actionHandlers = useRef<Record<string, (value?: string, label?: string) => void>>({});
  
  actionHandlers.current = {
    open_url: (value) => {
      if (value) window.open(value, "_blank", "noopener,noreferrer");
      addMessage("assistant", "Opened in a new tab.", undefined);
    },
    navigate: (value, label) => {
      if (value) onNavigate?.(value);
      addMessage("assistant", `Navigating to ${label || value}...`, undefined);
    },
    sort: (value, label) => {
      onSortChange?.(value as "duration" | "cost");
      addMessage("assistant", `Showing ${label?.toLowerCase() || value} routes.`, undefined);
    },
    system_control: (value) => {
      if (value === "trigger_sos") {
        onNavigate?.("/sos?action=trigger");
        addMessage("assistant", "🚨 Activating Emergency SOS. Your location is being shared.", undefined);
        logEvent("chatbot_action_executed", { action_type: "trigger_sos" });
        voiceService.speak("sos_triggered");
      } else if (value === "enable_guardian") {
        onNavigate?.("/sos?action=guardian");
        addMessage("assistant", "🛡️ Guardian Mode activated. Safe travels!", undefined);
        logEvent("chatbot_action_executed", { action_type: "enable_guardian" });
        voiceService.speak("guardian_active");
      } else if (value === "prompt_safety") {
        addMessage("assistant", "I am here. Please let me know what you need.", [
          { label: "Trigger SOS Now", type: "system_control", value: "trigger_sos" },
          { label: "Start Guardian Mode", type: "system_control", value: "enable_guardian" }
        ]);
      }
    },
    default: (value, label) => {
      const payload = value || label;
      if (!payload) return;
      addMessage("user", payload);
      setIsLoading(true);

      const localResult = processLocalIntent(payload);
      if (localResult) {
        setConversationState(prev => ({ ...prev, lastIntent: "local_handled" }));
        
        // Smart Suggestions Engine
        let finalActions = localResult.actions ? [...localResult.actions] : [];
        if (localResult.triggerSearch) {
           finalActions.push({ label: "Start Guardian", type: "system_control", value: "enable_guardian" });
           finalActions.push({ label: "Share Journey", type: "navigate", value: "/dashboard" });
        }
        
        addMessage("assistant", localResult.reply, finalActions.length ? finalActions : undefined);
        if (localResult.triggerSearch && localResult.collected) {
          resolveAndTriggerSearch(localResult.collected);
        }
        setIsLoading(false);
      } else {
        sendToBackend(payload).finally(() => setIsLoading(false));
      }
    }
  };

  const executeAction = useCallback((type: string, value?: string, label?: string) => {
    logEvent("chatbot_action_executed", { action_type: type });
    const handler = actionHandlers.current[type] || actionHandlers.current.default;
    handler(value, label);
  }, []);

  const handleActionClick = useCallback(
    (action: ChatAction) => {
      logEvent("chatbot_action_clicked", { label: action.label, type: action.type });
      executeAction(action.type, action.value, action.label);
    },
    [executeAction]
  );

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    addMessage("user", text);
    setIsLoading(true);
    logEvent("chatbot_message_sent", { text_length: text.length });

    // 0. Emotional Safety Intelligence
    const risk = analyzeEmotionalRisk(text);
    if (risk.level !== "low") {
      logEvent("chatbot_emotional_risk_detected", { level: risk.level });
      addMessage("assistant", risk.message);
      
      if (risk.autoTrigger) {
        executeAction("system_control", risk.action);
        setIsLoading(false);
        return;
      }
      
      if (risk.level === "critical" || risk.level === "medium") {
        setPendingAction({ label: risk.level === "critical" ? "Trigger SOS" : "Activate Protection", type: "system_control", value: risk.action });
        setIsLoading(false);
        return;
      }
    }

    // 1. Try local intent processor first (Instant/Offline)
    const localResult = processLocalIntent(text);
    if (localResult) {
      setConversationState(prev => ({ ...prev, lastIntent: "local_handled" }));
      
      // Smart Suggestions Engine
      let finalActions = localResult.actions ? [...localResult.actions] : [];
      if (localResult.triggerSearch) {
         finalActions.push({ label: "Start Guardian", type: "system_control", value: "enable_guardian" });
         finalActions.push({ label: "Share Journey", type: "navigate", value: "/dashboard" });
      } else if (localResult.action === "PROMPT_SAFETY") {
         // Distress language detected, proactive AI response
         finalActions = [
           { label: "Trigger SOS Now", type: "system_control", value: "trigger_sos" },
           { label: "Start Guardian Mode", type: "system_control", value: "enable_guardian" }
         ];
      }

      addMessage("assistant", localResult.reply, finalActions.length ? finalActions : undefined);
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
      executeAction("open_url", TELEGRAM_BOT_URL, label);
      return;
    }
    if (label === "Dashboard") {
      executeAction("navigate", "/dashboard", label);
      return;
    }
    if (label === "SOS") {
      executeAction("system_control", "trigger_sos", label);
      return;
    }
    if (label === "Safety Guarantee") {
      executeAction("navigate", "/safety", label);
      return;
    }
    if (label === "Help") {
      addMessage("user", "What can you do?");
      setIsLoading(true);
      sendToBackend("What can you do?").finally(() => setIsLoading(false));
      return;
    }
    // Handle route-based quick actions like "Delhi to Mumbai"
    executeAction("default", label, label);
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
              <div key={m.id} className={cn("flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300", m.role === "user" ? "flex-row-reverse" : "flex-row")}>
                <div
                  className={cn(
                    "w-8 h-8 shrink-0 rounded-full flex items-center justify-center shadow-sm",
                    m.role === "user" ? "bg-primary/20" : "bg-[#0f172a]"
                  )}
                >
                  {m.role === "user" ? <User className="w-4 h-4 text-primary" /> : <Bot className="w-4 h-4 text-white" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div
                    className={cn(
                      "max-w-[90%] rounded-2xl px-4 py-3 text-sm shadow-sm",
                      m.role === "user"
                        ? "bg-primary text-primary-foreground rounded-tr-sm ml-auto"
                        : "bg-white dark:bg-muted text-foreground border border-border rounded-tl-sm"
                    )}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                    <span className="text-[9px] opacity-50 mt-1 block text-right">
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {m.actions && m.actions.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {m.actions.map((a, i) => (
                        <button
                          key={i}
                          onClick={() => handleActionClick(a)}
                          className="px-4 py-2 rounded-xl text-xs font-semibold bg-primary/10 text-primary hover:bg-primary hover:text-white border border-primary/20 transition-all transform hover:scale-105 active:scale-95 shadow-sm"
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                  {/* Confirmation Layer for Critical Actions */}
                  {m.id === messages[messages.length - 1].id && pendingAction && m.role === "assistant" && (
                    <div className="flex gap-2 mt-4 animate-in zoom-in duration-300">
                      <button
                        onClick={() => {
                          executeAction("system_control", pendingAction.value);
                          setPendingAction(null);
                        }}
                        className="flex-1 py-2.5 bg-emerald-600 text-white rounded-xl text-xs font-black uppercase tracking-widest shadow-lg shadow-emerald-600/20"
                      >
                        Yes, Proceed
                      </button>
                      <button
                        onClick={() => setPendingAction(null)}
                        className="flex-1 py-2.5 bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-xl text-xs font-black uppercase tracking-widest"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3 items-center">
                <div className="w-8 h-8 shrink-0 rounded-full bg-[#0f172a] flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="bg-white dark:bg-muted border border-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <div className="flex gap-1.5 items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }} />
                    <span className="ml-2 text-[10px] font-medium text-muted-foreground">Diksha is typing...</span>
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
                aria-label="Send"
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
