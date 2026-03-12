import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, Mic, MicOff, Send, X, Bot, User, WifiOff, RefreshCw, AlertTriangle, Zap, ShieldAlert, Navigation, Activity, MapPin, LayoutDashboard, History, Ticket } from "lucide-react";
import { cn, getRailwayApiUrl, getRailwayWsUrl } from "@/lib/utils";
import { searchStationsApi } from "@/services/railwayBackApi";
import { processLocalIntent } from "@/services/localChatBrain";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { logEvent } from "@/lib/observability";
import { loadMemory } from "@/ai/persistentMemory";
import { evaluateProactiveRules } from "@/ai/proactiveRules";
import { listenWakeWord } from "@/ai/wakeWord";
import { analyzeEmotionalRisk } from "@/ai/emotionalEngine";
import { voiceService } from "@/services/voiceService";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { queueMessage, getQueuedMessages, clearQueuedMessage } from "@/services/chatOfflineQueue";

// Declare SpeechRecognition for browser compatibility
declare global {
  interface Window {
    SpeechRecognition?: any;
    webkitSpeechRecognition?: any;
  }
}

export interface ChatAction {
  label: string;
  type: string;
  value?: string;
  icon?: any;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
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

const WELCOME_MSG = `🚂 **RouteMaster / Rail Assistant Online.**

Systems operational. I am your advanced AI travel companion for Indian Railways.

✨ **Capabilities:**
🎫 **Book Tickets** — Search trains dynamically
📊 **Analytics** — View journey stats in real-time
🆘 **Emergency Protocol** — Live tracking & SOS
📱 **Integration** — Telegram mini-app synced

How can I assist you with your logistics today?`;

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

function TypingIndicator({ durationMs = 2000, onCancel }: { durationMs?: number, onCancel?: () => void }) {
  return (
    <div className="flex flex-col gap-1.5 animate-in fade-in duration-300">
      <div className="flex gap-2 items-center bg-muted/50 dark:bg-[#0f172a]/80 border border-border/50 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm w-fit backdrop-blur-md">
        <Activity className="w-4 h-4 text-cyan-500 animate-pulse" />
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
      <div className="flex items-center gap-2 ml-2">
        <span className="text-[10px] text-cyan-500/80 italic font-mono uppercase tracking-widest">
          Processing (~{(durationMs / 1000).toFixed(1)}s)
        </span>
        {onCancel && (
          <button 
            onClick={onCancel}
            className="text-[10px] text-red-500 hover:text-red-400 font-bold uppercase tracking-wider transition-colors"
          >
            [Abort]
          </button>
        )}
      </div>
    </div>
  );
}

export function RailAssistantChatbot({ onSearchRequest, onSortChange: _onSortChange, onNavigate, className }: RailAssistantChatbotProps) {
  const isBackendOnline = useBackendHealth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>(generateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [conversationState, setConversationState] = useState<ConversationState>({
    lastIntent: null,
    searchQuery: null,
    journeyActive: false,
  });

  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);

  // Core Static Suggestion Actions (The "Button Pattern" within the interface)
  const getContextActions = useCallback(() => {
    if (conversationState.journeyActive) {
      return [
        { label: "Share Location", type: "intent", value: "Share live location", icon: <MapPin className="w-3 h-3" /> },
        { label: "Contact Police", type: "intent", value: "Contact Railway Police", icon: <AlertTriangle className="w-3 h-3" /> },
        { label: "Guardian Mode", type: "system_control", value: "enable_guardian", icon: <ShieldAlert className="w-3 h-3" /> },
        { label: "Safety Status", type: "intent", value: "Check safety status", icon: <Activity className="w-3 h-3" /> },
      ];
    }
    if (conversationState.lastIntent === "search") {
      return [
        { label: "Check Availability", type: "intent", value: "Check Availability", icon: <Zap className="w-3 h-3" /> },
        { label: "Alternative Routes", type: "intent", value: "Alternative Routes", icon: <Navigation className="w-3 h-3" /> },
        { label: "PNR Status", type: "intent", value: "PNR Status", icon: <Activity className="w-3 h-3" /> },
        { label: "Route Map", type: "intent", value: "Show route map", icon: <MapPin className="w-3 h-3" /> },
      ];
    }
    return [
      { label: "Book Ticket", type: "intent", value: "Book Ticket", icon: <Ticket className="w-3.5 h-3.5 text-cyan-400" /> },
      { label: "Search Trains", type: "intent", value: "Search Trains", icon: <Navigation className="w-3.5 h-3.5" /> },
      { label: "Delhi → Mumbai", type: "intent", value: "Delhi to Mumbai", icon: <MapPin className="w-3.5 h-3.5" /> },
      { label: "My Bookings", type: "navigate", value: "/bookings", icon: <History className="w-3.5 h-3.5" /> },
      { label: "Dashboard", type: "navigate", value: "/dashboard", icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
      { label: "Telegram", type: "open_url", value: TELEGRAM_BOT_URL, icon: <MessageCircle className="w-3.5 h-3.5" /> },
    ];
  }, [conversationState]);

  // Frictionless Response Tracking: Scroll to top of the latest response
  const scrollToNewMessage = useCallback(() => {
    if (lastMessageRef.current) {
        lastMessageRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  useEffect(() => {
    // Only auto-scroll when a new assistant message is being added or streamed
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === "assistant") {
        scrollToNewMessage();
    }
  }, [messages, scrollToNewMessage]);

  // WebSocket Logic
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = getRailwayWsUrl("/chat/ws");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("Chat WebSocket Connected");
      setIsWsConnected(true);
      logEvent("chatbot_ws_connected");
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
        addMessage("system", "⚠️ System Error: " + data.message);
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

  // Offline Queue
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

  // History Load
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
              { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date() },
              ...formatted
            ]);
          }
        }
      } catch (e) { console.error("History load failed", e); }
    };
    if (isOpen) loadHistory();
  }, [isOpen]);

  // Memory Load
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

  // Wake Word
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

  const addMessage = useCallback((role: "user" | "assistant" | "system", content: string, actions?: ChatAction[]) => {
    setMessages((prev) => [...prev, { id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, role, content, timestamp: new Date(), actions }]);
  }, []);

  // Proactive Engine
  const triggerProactiveSuggestions = useCallback(() => {
    const ctx = {
      journeyActive: conversationState.journeyActive,
      timeOfDay: new Date().getHours(),
      guardianActive: conversationState.lastIntent === "enable_guardian"
    };
    
    const suggestions = evaluateProactiveRules(ctx);
    if (suggestions.length > 0) {
      const suggestion = suggestions[0];
      addMessage("system", `✨ AI Hint: ${suggestion.message}`, [suggestion.action]);
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
    } else if (type === "intent" && value) {
      handleSendCore(value);
    }
  }, [onNavigate]);

  const handleActionClick = (action: ChatAction) => {
    logEvent("chatbot_action_clicked", { label: action.label, type: action.type });
    executeAction(action.type, action.value, action.label);
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    addMessage("system", "Operation aborted by user.");
  };

  const handleSendCore = async (textToSend: string) => {
    const text = textToSend.trim();
    if (!text) return;

    setInput("");
    addMessage("user", text);
    setIsLoading(true);
    logEvent("chatbot_message_sent", { text_length: text.length });

    abortControllerRef.current = new AbortController();

    const risk = analyzeEmotionalRisk(text);
    if (risk.level !== "low") {
      addMessage("system", risk.message);
      if (risk.autoTrigger) {
        executeAction("system_control", risk.action);
        setIsLoading(false);
        return;
      }
    }

    const localResult = processLocalIntent(text);
    if (localResult) {
      setConversationState(prev => ({ ...prev, lastIntent: "local_handled" }));
      addMessage("assistant", localResult.reply, localResult.actions);
      if (localResult.actions && localResult.actions.length > 0) {
        window.dispatchEvent(new CustomEvent("rail-assistant-suggestions", {
          detail: { actions: localResult.actions }
        }));
      }
      if (localResult.triggerSearch && localResult.collected) {
        await resolveAndTriggerSearch(localResult.collected);
      }
      setIsLoading(false);
      return;
    }

    if (isWsConnected && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: text, session_id: sessionIdRef.current }));
    } else {
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
        addMessage("system", "📡 Network isolated. Message queued in local buffer.");
        setIsLoading(false);
      } else {
        try {
          const res = await fetch(getRailwayApiUrl("/chat"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
            signal: abortControllerRef.current.signal
          });
          const data = await res.json();
          setIsLoading(false);
          addMessage("assistant", data.reply, data.actions);
          
          if (data.actions && data.actions.length > 0) {
            window.dispatchEvent(new CustomEvent("rail-assistant-suggestions", {
              detail: { actions: data.actions }
            }));
          }

          if (data.trigger_search && data.collected) {
            await resolveAndTriggerSearch(data.collected, data.correlation_id);
          }
        } catch (e: any) {
          if (e.name === 'AbortError') return;
          setIsLoading(false);
          addMessage("system", "Connection interrupted. Retrying...");
        }
      }
    }
  };

  const handleSend = () => {
    handleSendCore(input);
  };

  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      addMessage("system", "Voice interface incompatible with current browser.");
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
    <div className={cn("fixed bottom-6 right-6 z-50 flex flex-col items-end gap-4 pointer-events-none", className)}>
      
      {isOpen && (
        <div className="w-full max-w-[440px] h-[600px] md:h-[720px] bg-background/95 dark:bg-[#0a0f1c]/98 backdrop-blur-3xl border border-white/20 dark:border-cyan-500/40 rounded-[2.5rem] shadow-[0_20px_80px_rgba(0,0,0,0.4)] dark:shadow-[0_20px_80px_rgba(6,182,212,0.2)] flex flex-col overflow-hidden animate-in zoom-in-95 duration-300 pointer-events-auto origin-bottom-right">
          
          {/* Header */}
          <div className="relative flex items-center justify-between px-8 py-5 bg-gradient-to-r from-[#0f172a] to-[#1e293b] dark:from-[#0a0f1c] dark:to-[#0f172a] border-b border-white/10 dark:border-cyan-500/30 overflow-hidden">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:16px_16px] opacity-20"></div>
            
            <div className="relative flex items-center gap-4">
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-cyan-950/50 flex items-center justify-center shrink-0 border border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.4)] rotate-3">
                  <Bot className="w-7 h-7 text-cyan-400 -rotate-3" />
                </div>
                <div className={cn(
                  "absolute inset-0 rounded-2xl border-2 border-transparent border-t-cyan-400 animate-spin-slow",
                  isWsConnected ? "opacity-100" : "opacity-0"
                )}></div>
                <div className={cn(
                  "absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-[#0f172a] shadow-[0_0_15px_currentColor]",
                  isBackendOnline ? (isWsConnected ? "bg-cyan-400 text-cyan-400" : "bg-yellow-400 text-yellow-400") : "bg-red-500 text-red-500"
                )} />
              </div>
              <div>
                <h3 className="font-black text-xl text-white tracking-tighter flex items-center gap-2">
                  RouteMaster <span className="text-cyan-400 font-mono text-[10px] opacity-80 border border-cyan-500/30 px-1.5 rounded uppercase">Protocol v2.5</span>
                </h3>
                <p className="text-[10px] text-cyan-400/80 font-mono tracking-[0.2em] uppercase flex items-center gap-1 mt-0.5">
                  {isWsConnected ? <><Activity className="w-3 h-3 animate-pulse"/> Syncing Neural Net</> : (isBackendOnline ? "Systems Nominal" : "Offline Cache Mode")}
                </p>
              </div>
            </div>
            <button onClick={() => setIsOpen(false)} className="relative p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all backdrop-blur-md border border-white/10 hover:scale-110 active:scale-95">
              <X className="w-5 h-5 text-white/80" />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-8 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] bg-gradient-to-b from-transparent via-muted/5 to-cyan-500/5 relative custom-scrollbar">
            {messages.map((m, idx) => (
              <div 
                key={m.id} 
                className={cn("flex gap-4 group", m.role === "user" ? "flex-row-reverse" : "flex-row")}
                ref={idx === messages.length - 1 && m.role === "assistant" ? lastMessageRef : null}
              >
                {m.role !== "system" && (
                  <div className={cn(
                    "w-10 h-10 shrink-0 rounded-xl flex items-center justify-center shadow-xl transition-transform group-hover:scale-110", 
                    m.role === "user" 
                      ? "bg-gradient-to-br from-indigo-500 to-purple-600 rotate-3" 
                      : "bg-gradient-to-br from-cyan-900 to-slate-900 border border-cyan-500/40 -rotate-3"
                  )}>
                    {m.role === "user" ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-cyan-400" />}
                  </div>
                )}
                <div className={cn("flex-1 min-w-0", m.role === "system" ? "flex justify-center" : "")}>
                  <div className={cn(
                    "max-w-[88%] rounded-3xl px-5 py-4 text-[15px] shadow-lg leading-[1.6] transition-all", 
                    m.role === "user" 
                      ? "bg-gradient-to-br from-indigo-600 to-purple-700 text-white ml-auto rounded-tr-sm border border-indigo-400/30" 
                      : m.role === "system"
                        ? "bg-yellow-500/10 border border-yellow-500/20 text-yellow-600 dark:text-yellow-400 text-xs mx-auto text-center font-mono rounded-full py-2 px-6 backdrop-blur-sm"
                        : "bg-white dark:bg-[#0f172a]/90 text-foreground border border-border/50 dark:border-cyan-500/10 rounded-tl-sm shadow-cyan-500/5"
                  )}>
                    <MarkdownRenderer content={m.content} />
                    {m.role !== "system" && (
                      <span className="text-[10px] opacity-40 mt-2 block text-right font-mono tracking-widest">
                        {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  
                  {/* Inline Message Actions */}
                  {m.actions && m.actions.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-4 ml-2">
                      {m.actions.map((a, i) => (
                        <button key={i} onClick={() => handleActionClick(a)} className="flex items-center gap-2 px-4 py-2 rounded-2xl text-xs font-bold bg-background border border-cyan-500/30 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500 hover:text-white dark:hover:bg-cyan-500 dark:hover:text-white transition-all shadow-md active:scale-95">
                          {a.icon && <span className="opacity-80">{a.icon}</span>}
                          {a.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && <TypingIndicator durationMs={2500} onCancel={handleCancel} />}
            <div ref={messagesEndRef} />
          </div>

          {/* Unified Smart Input Area */}
          <div className="p-6 border-t border-border/40 bg-white/60 dark:bg-[#0a0f1c]/90 backdrop-blur-3xl space-y-6">
            
            {/* Multi-row Suggested Actions (Fixed Pattern) */}
            <div className="grid grid-cols-2 gap-2 max-h-[140px] overflow-y-auto custom-scrollbar-mini pr-1">
              {getContextActions().map((a, idx) => (
                <button 
                  key={idx} 
                  onClick={() => handleActionClick(a)} 
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-2xl text-[13px] font-bold transition-all border shadow-sm group",
                    a.type === "system_control" || a.label.includes("SOS")
                      ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 hover:bg-red-600 hover:text-white"
                      : "bg-secondary/40 text-secondary-foreground border-transparent hover:border-cyan-500/40 hover:bg-cyan-500/10 dark:hover:bg-cyan-950/40"
                  )}
                >
                  <span className="shrink-0 transition-transform group-hover:scale-125">{a.icon}</span>
                  <span className="truncate">{a.label}</span>
                </button>
              ))}
            </div>

            {/* Offline/Status Notice */}
            {!isBackendOnline && (
              <div className="flex items-center gap-3 px-5 py-3 bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 rounded-2xl text-[11px] font-bold tracking-tight">
                <WifiOff className="w-4 h-4" />
                <span className="flex-1 uppercase font-mono">Offline Protocol: {offlineQueueCount} packets queued</span>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              </div>
            )}
            
            {/* Input Field */}
            <div className="flex items-center gap-3 bg-background dark:bg-[#1e293b]/50 border-2 border-border/50 focus-within:border-cyan-500/60 rounded-[2rem] p-2 shadow-inner transition-all focus-within:shadow-[0_0_20px_rgba(6,182,212,0.1)]">
              <button onClick={toggleVoice} className={cn("p-3.5 rounded-full transition-all active:scale-90", isListening ? "bg-red-500 text-white shadow-[0_0_20px_rgba(239,68,68,0.6)] animate-pulse" : "text-muted-foreground hover:bg-secondary hover:text-foreground")}>
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </button>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Initialize command..."
                className="flex-1 bg-transparent px-2 py-3 outline-none text-[15px] placeholder:text-muted-foreground/50 font-medium"
              />
              <button
                aria-label="Send"
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="p-3.5 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-lg disabled:opacity-40 disabled:grayscale transition-all hover:shadow-[0_0_25px_rgba(6,182,212,0.5)] active:scale-90"
              >
                <Send className="w-6 h-6 ml-0.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Control Hub */}
      <div className="flex items-center gap-5 pointer-events-auto">
        <button 
          onClick={() => onNavigate?.("/sos")}
          className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500 via-red-600 to-red-800 text-white shadow-[0_10px_30px_rgba(239,68,68,0.5)] flex items-center justify-center hover:scale-110 active:scale-95 transition-all border-2 border-white/20 rotate-3 group"
          title="Emergency Protocol"
        >
          <AlertTriangle className="w-7 h-7 animate-pulse group-hover:scale-125 transition-transform" />
        </button>

        <button 
          onClick={() => setIsOpen(!isOpen)} 
          className={cn(
            "w-20 h-20 rounded-[2rem] flex items-center justify-center transition-all duration-500 shadow-[0_15px_60px_rgba(0,0,0,0.4)] border-2 border-white/10 active:scale-90",
            isOpen 
              ? "bg-[#0f172a] text-white rotate-180 scale-90" 
              : "bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600 text-white hover:scale-105 hover:shadow-[0_0_40px_rgba(6,182,212,0.6)]"
          )}
        >
          {isOpen ? <X className="w-9 h-9" /> : <Bot className="w-10 h-10" />}
        </button>
      </div>

    </div>
  );
}
