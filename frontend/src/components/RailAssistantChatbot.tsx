/**
 * RailAssistant 2.0 - IRCTC AskDISHA-style chatbot
 * Features: WebSockets, Streaming, Offline Queue, Session Context, Voice, Proactive AI.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, Mic, MicOff, Send, X, Bot, User, Plus, WifiOff, RefreshCw } from "lucide-react";
import { cn, getRailwayApiUrl, getRailwayWsUrl } from "@/lib/utils";
import { searchStationsApi } from "@/services/railwayBackApi";
import { processLocalIntent } from "@/services/localChatBrain";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { logEvent } from "@/lib/observability";
import { loadMemory, saveMemory } from "@/ai/persistentMemory";
import { evaluateProactiveRules } from "@/ai/proactiveRules";
import { listenWakeWord } from "@/ai/wakeWord";
import { analyzeEmotionalRisk } from "@/ai/emotionalEngine";
import { voiceService } from "@/services/voiceService";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { RouteVisualizer } from "./RouteVisualizer";
import { InteractiveDatePicker } from "./InteractiveDatePicker";
import { queueMessage, getQueuedMessages, clearQueuedMessage } from "@/services/chatOfflineQueue";

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
  isStreaming?: boolean;
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

💡 **Quick Actions** — Tap any button below to get started!

---

**Popular Routes:** Delhi-Mumbai • Chennai-Bangalore • Howrah-Delhi

How can I assist you today? 😊`;

export interface RailAssistantChatbotProps {
  onSearchRequest?: (fromCode: string, toCode: string, date?: string, correlationId?: string) => void;
  onSortChange?: (sortBy: "duration" | "cost") => void;
  onNavigate?: (path: string) => void;
  className?: string;
}

function generateSessionId() {
  const existing = localStorage.getItem("chat_session_id");
  if (existing) return existing;
  const newId = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  localStorage.setItem("chat_session_id", newId);
  return newId;
}

const TELEGRAM_BOT_URL = "https://t.me/RoutemasternagarindustrisBot";

/**
 * Task 10: Typing Cadence Indicator
 */
function TypingIndicator({ durationMs = 2000 }: { durationMs?: number }) {
  return (
    <div className="flex flex-col gap-1.5 animate-in fade-in duration-300">
      <div className="flex gap-1.5 items-center bg-white dark:bg-muted border border-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm w-fit">
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      <span className="text-[10px] text-muted-foreground ml-2 italic">
        Thinking... (~{(durationMs / 1000).toFixed(1)}s)
      </span>
    </div>
  );
}

export function RailAssistantChatbot({ onSearchRequest, onSortChange, onNavigate, className }: RailAssistantChatbotProps) {
  const isBackendOnline = useBackendHealth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date(), actions: QUICK_ACTIONS },
  ]);
  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>(generateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [conversationState, setConversationState] = useState<ConversationState>({
    lastIntent: null,
    searchQuery: null,
    journeyActive: false,
  });

  const [pendingAction, setPendingAction] = useState<ChatAction | null>(null);
  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);

  // Scroll logic
  const scrollToBottom = useCallback((force = false) => {
    // Task 21: Auto-Scroll Management (Pause if user scrolls up)
    if (!messagesEndRef.current) return;
    const container = messagesEndRef.current.parentElement;
    if (!container) return;

    const isAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 100;
    if (isAtBottom || force) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // -- Task 2: WebSocket Token Streaming & Task 3: Session Context --
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = getRailwayWsUrl("/chat/ws");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("Chat WebSocket Connected");
      setIsWsConnected(true);
      logEvent("chatbot_ws_connected");
      // Sync offline queue if connection restored
      syncOfflineQueue();
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "token") {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + data.token }
            ];
          } else {
            return [
              ...prev,
              {
                id: `stream-${Date.now()}`,
                role: "assistant",
                content: data.token,
                timestamp: new Date(),
                isStreaming: true
              }
            ];
          }
        });
      } else if (data.type === "final") {
        setIsLoading(false);
        setMessages((prev) => {
          const filtered = prev.filter(m => !m.isStreaming);
          return [
            ...filtered,
            {
              id: `msg-${Date.now()}`,
              role: "assistant",
              content: data.reply,
              timestamp: new Date(),
              actions: data.actions,
              isStreaming: false
            }
          ];
        });
        if (data.intent) {
          setConversationState(prev => ({ ...prev, lastIntent: data.intent }));
        }
      } else if (data.type === "error") {
        setIsLoading(false);
        addMessage("assistant", "⚠️ Error: " + data.message);
      }
    };

    ws.onclose = () => {
      setIsWsConnected(false);
      wsRef.current = null;
      console.log("Chat WebSocket Disconnected");
    };
  }, []);

  useEffect(() => {
    if (isOpen && isBackendOnline) {
      connectWebSocket();
    }
    return () => {
      wsRef.current?.close();
    };
  }, [isOpen, isBackendOnline, connectWebSocket]);

  // -- Task 7: Offline Message Queue (IndexedDB) --
  const syncOfflineQueue = async () => {
    const queued = await getQueuedMessages();
    setOfflineQueueCount(queued.length);
    if (queued.length > 0 && isBackendOnline) {
      logEvent("chatbot_sync_offline_queue", { count: queued.length });
      for (const msg of queued) {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ message: msg.content, session_id: msg.sessionId }));
          await clearQueuedMessage(msg.id);
        }
      }
      setOfflineQueueCount(0);
    }
  };

  useEffect(() => {
    const interval = setInterval(syncOfflineQueue, 30000);
    return () => clearInterval(interval);
  }, [isBackendOnline]);

  // -- Task 23: Historical Chat Retrieval (Supabase/DB) --
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch(getRailwayApiUrl(`/chat/history?session_id=${sessionIdRef.current}`));
        if (res.ok) {
          const data = await res.json();
          if (data.messages && data.messages.length > 0) {
            const formatted = data.messages.map((m: any, i: number) => ({
              id: `hist-${i}`,
              role: m.role,
              content: m.content,
              timestamp: new Date(m.timestamp),
              actions: m.actions
            }));
            setMessages([
              { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date(), actions: QUICK_ACTIONS },
              ...formatted
            ]);
          }
        }
      } catch (e) { console.error("History load failed", e); }
    };
    if (isOpen) loadHistory();
  }, [isOpen]);

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
  }, []);

  // Wake-word Listener
  useEffect(() => {
    if (!wakeWordEnabled) return;
    const cleanup = listenWakeWord(() => {
      setIsOpen(true);
      logEvent("chatbot_wake_word_detected");
      const audio = new Audio("https://assets.mixkit.co/active_storage/sfx/2354/2354-preview.mp3");
      audio.volume = 0.2;
      audio.play().catch(() => {});
    });
    return cleanup;
  }, [wakeWordEnabled]);

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
        return false;
      } catch {
        return false;
      }
    },
    [onSearchRequest]
  );

  const executeAction = useCallback((type: string, value?: string, label?: string) => {
    logEvent("chatbot_action_executed", { action_type: type });
    
    // Dispatch Global UI Event (Task 11: Chatbot-to-UI Event Bus)
    window.dispatchEvent(new CustomEvent("chatbot-ui-control", {
      detail: { type, value, label }
    }));

    if (type === "open_url" && value) {
      window.open(value, "_blank", "noopener,noreferrer");
    } else if (type === "navigate" && value) {
      onNavigate?.(value);
    } else if (type === "system_control" && value === "trigger_sos") {
      onNavigate?.("/sos?action=trigger");
      voiceService.speak("sos_triggered");
    } else if (type === "system_control" && value === "enable_guardian") {
      onNavigate?.("/sos?action=guardian");
      voiceService.speak("guardian_active");
    }
  }, [onNavigate]);

  const handleActionClick = (action: ChatAction) => {
    logEvent("chatbot_action_clicked", { label: action.label, type: action.type });
    executeAction(action.type, action.value, action.label);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    addMessage("user", text);
    setIsLoading(true);
    logEvent("chatbot_message_sent", { text_length: text.length });

    // Emotional Safety check
    const risk = analyzeEmotionalRisk(text);
    if (risk.level !== "low") {
      addMessage("assistant", risk.message);
      if (risk.autoTrigger) {
        executeAction("system_control", risk.action);
        setIsLoading(false);
        return;
      }
    }

    // Local intent processor first (Task 1: Local NLP Intent Router)
    const localResult = processLocalIntent(text);
    if (localResult) {
      setConversationState(prev => ({ ...prev, lastIntent: "local_handled" }));
      addMessage("assistant", localResult.reply, localResult.actions);
      if (localResult.triggerSearch && localResult.collected) {
        await resolveAndTriggerSearch(localResult.collected);
      }
      setIsLoading(false);
      return;
    }

    // Backend Interaction
    if (isWsConnected && wsRef.current?.readyState === WebSocket.OPEN) {
      // WS Streaming path
      wsRef.current.send(JSON.stringify({ message: text, session_id: sessionIdRef.current }));
    } else {
      // Offline Queue path (Task 7)
      if (!isBackendOnline) {
        const msgId = `offline-${Date.now()}`;
        await queueMessage({
          id: msgId,
          role: "user",
          content: text,
          timestamp: new Date().toISOString(),
          sessionId: sessionIdRef.current
        });
        setOfflineQueueCount(prev => prev + 1);
        addMessage("assistant", "📡 **Offline Mode**: I've queued your message. I'll process it as soon as your 4G restores!");
        setIsLoading(false);
      } else {
        // HTTP Fallback (Task 24)
        try {
          const res = await fetch(getRailwayApiUrl("/chat"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
          });
          const data = await res.json();
          setIsLoading(false);
          addMessage("assistant", data.reply, data.actions);
          if (data.trigger_search && data.collected) {
            await resolveAndTriggerSearch(data.collected, data.correlation_id);
          }
        } catch (e) {
          setIsLoading(false);
          addMessage("assistant", "I'm having trouble connecting. Try again in a moment.");
        }
      }
    }
  };

  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      addMessage("assistant", "Voice input is not supported in this browser.");
      return;
    }
    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "en-IN";
    recognition.onresult = (e: any) => {
      const t = e.results[0][0].transcript;
      setInput(t);
    };
    recognition.onend = () => setIsListening(false);
    recognition.start();
    setIsListening(true);
  };

  return (
    <div className={cn("fixed bottom-6 right-6 z-50 flex flex-col items-end", className)}>
      {isOpen && (
        <div className="w-full max-w-[420px] h-[600px] md:h-[640px] bg-white dark:bg-card border-2 border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 duration-300">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 bg-[#0f172a] dark:bg-[#0c4a6e]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center shrink-0 border border-white/10 relative">
                <Bot className="w-6 h-6 text-white" />
                <div className={cn(
                  "absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#0f172a]",
                  isBackendOnline ? (isWsConnected ? "bg-green-500" : "bg-yellow-500") : "bg-red-500"
                )} title={isWsConnected ? "Streaming Live" : "Polling Mode"} />
              </div>
              <div>
                <h3 className="font-bold text-base text-white leading-none mb-1">Rail Assistant 2.0</h3>
                <p className="text-[10px] text-white/60 font-semibold tracking-wider uppercase">
                  {isWsConnected ? "⚡ Streaming" : (isBackendOnline ? "🟢 Online" : "📡 Offline Queue")}
                </p>
              </div>
            </div>
            <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/20 rounded-lg transition-colors">
              <X className="w-5 h-5 text-white" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-muted/20">
            {messages.map((m) => (
              <div key={m.id} className={cn("flex gap-3", m.role === "user" ? "flex-row-reverse" : "flex-row")}>
                <div className={cn("w-8 h-8 shrink-0 rounded-full flex items-center justify-center", m.role === "user" ? "bg-primary/20" : "bg-[#0f172a]")}>
                  {m.role === "user" ? <User className="w-4 h-4 text-primary" /> : <Bot className="w-4 h-4 text-white" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={cn("max-w-[90%] rounded-2xl px-4 py-3 text-sm shadow-sm", m.role === "user" ? "bg-primary text-primary-foreground ml-auto" : "bg-white dark:bg-muted text-foreground border border-border")}>
                    <MarkdownRenderer content={m.content} />
                    <span className="text-[9px] opacity-50 mt-1 block text-right">
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {m.actions && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {m.actions.map((a, i) => (
                        <button key={i} onClick={() => handleActionClick(a)} className="px-4 py-2 rounded-xl text-xs font-semibold bg-primary/10 text-primary hover:bg-primary hover:text-white border border-primary/20 transition-all">
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && <TypingIndicator durationMs={2500} />}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-border bg-white dark:bg-card space-y-3">
            {!isBackendOnline && (
              <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-lg text-xs">
                <WifiOff className="w-4 h-4" />
                <span>Offline: Messages will be queued ({offlineQueueCount})</span>
                <RefreshCw className="w-3 h-3 animate-spin ml-auto" />
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {QUICK_ACTIONS.map((a) => (
                <button key={a.label} onClick={() => setInput(a.label)} className="px-3 py-1.5 rounded-full text-[11px] font-medium bg-secondary hover:bg-secondary/80 text-secondary-foreground transition-colors">
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
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask me anything..."
                className="flex-1 px-4 py-3 rounded-xl border-2 border-border bg-background outline-none text-sm focus:border-primary transition-all"
              />
              <button onClick={toggleVoice} className={cn("p-3 rounded-xl transition-colors", isListening ? "bg-red-500 text-white" : "bg-secondary")}>
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
              <button onClick={handleSend} disabled={!input.trim() || isLoading} className="p-3 rounded-xl bg-primary text-primary-foreground disabled:opacity-50">
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}
      <button onClick={() => setIsOpen(!isOpen)} className="w-14 h-14 rounded-full bg-primary text-white shadow-lg flex items-center justify-center hover:scale-105 transition-all">
        <MessageCircle className="w-7 h-7" />
      </button>
    </div>
  );
}
