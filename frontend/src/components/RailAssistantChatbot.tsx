import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useChatStore } from "@/store/useChatStore";
import { useSystemStatus } from "@/store/useSystemStatus";
import { motion, AnimatePresence } from "framer-motion";
import { MessageCircle, Mic, MicOff, Send, X, Bot, User, WifiOff, RefreshCw, AlertTriangle, Zap, ShieldAlert, Navigation, Activity, MapPin, LayoutDashboard, History, Ticket, ChevronDown, Trash2 } from "lucide-react";
import { cn, getRailwayApiUrl, getRailwayWsUrl } from "@/lib/utils";
import { searchStationsApi } from "@/services/railwayBackApi";
import { processLocalIntent } from "@/services/localChatBrain";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { useFPS } from "@/hooks/useFPS";
import { useTheme } from "@/context/ThemeContext";
import { logEvent } from "@/lib/observability";
import { saveMemory, loadMemory } from "@/ai/persistentMemory";
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

function ChatBubbleSkeleton({ role }: { role: "user" | "assistant" }) {
  return (
    <div className={cn("flex gap-3 py-3 animate-pulse", role === "user" ? "flex-row-reverse" : "flex-row")}>
      <div className={cn("w-8 h-8 rounded-lg shrink-0", role === "user" ? "bg-indigo-500/20" : "bg-cyan-500/20")} />
      <div className={cn(
        "max-w-[70%] h-16 rounded-2xl",
        role === "user" ? "bg-indigo-600/10 ml-auto rounded-tr-sm" : "bg-slate-800/20 rounded-tl-sm"
      )} style={{ width: Math.random() * 100 + 100 + 'px' }} />
    </div>
  );
}

export function RailAssistantChatbot({ onSearchRequest, onSortChange: _onSortChange, onNavigate, className }: RailAssistantChatbotProps) {
  const isBackendOnline = useBackendHealth();
  const { surgeLevel, latencyMs, retryAfter, fps } = useSystemStatus();
  const { isLowPowerMode } = useTheme();
  
  // Task 1.20: Performance Profiling
  useFPS();
  
  // Task 8.1: Global Chat State
  const { 
    isOpen, setIsOpen, 
    isHydrating, setIsHydrating,
    isError, setIsError,
    messages: storeMessages, 
    addMessage: addToStore, 
    updateLastMessage, 
    setMessages: setStoreMessages,
    lastIntent: storeLastIntent,
    setLastIntent: setStoreLastIntent,
    draftInput, setDraftInput,
    clearHistory: clearStoreHistory
  } = useChatStore();

  const messages = useMemo(() => storeMessages.map(m => ({
    ...m,
    timestamp: new Date(m.timestamp)
  })), [storeMessages]);

  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [offlineQueueCount, setOfflineQueueCount] = useState(0);
  const [showNewMessageBadge, setShowNewMessageBadge] = useState(false); // Task 1.10

  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>(generateSessionId());
  const instanceId = useMemo(() => Math.random().toString(36).substring(7), []);
  const [isMaster, setIsMaster] = useState(false);
  const channelRef = useRef<BroadcastChannel | null>(null);
  const reconnectTimeoutRef = useRef<number>(1000);

  const safePostMessage = useCallback((data: any) => {
    try {
      if (channelRef.current) {
        channelRef.current.postMessage(data);
      }
    } catch (err) {
      // Catch "Channel is closed" or other InvalidStateErrors during unmount
      console.debug("BroadcastChannel postMessage suppressed (channel likely closed):", err);
    }
  }, []);

  const claimLeadership = useCallback(() => {
    setIsMaster(true);
    safePostMessage({ type: "LEADER_ANNOUNCE", id: instanceId });
  }, [instanceId, safePostMessage]);

  // Task 1.14: Leader Election & Cross-Tab Sync
  useEffect(() => {
    const channel = new BroadcastChannel("routemaster_neural_sync");
    channelRef.current = channel;
    const currentChannel = channel;

    channel.onmessage = (event) => {
      const { type, id, payload } = event.data;
      
      if (type === "WHO_IS_LEADER") {
        if (isMaster) safePostMessage({ type: "LEADER_ANNOUNCE", id: instanceId });
      } else if (type === "LEADER_ANNOUNCE") {
        if (id !== instanceId) {
          setIsMaster(false);
          if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
          }
        }
      } else if (type === "LEADER_RETIRE") {
        if (id !== instanceId) {
          // A leader left, try to claim it
          setTimeout(claimLeadership, Math.random() * 500);
        }
      } else if (type === "SYNC_STATE" && !isMaster) {
        if (payload.messages) setStoreMessages(payload.messages);
        if (payload.lastIntent) setStoreLastIntent(payload.lastIntent);
      }
    };

    safePostMessage({ type: "WHO_IS_LEADER", id: instanceId });
    const timer = setTimeout(() => {
      if (!isMaster) claimLeadership();
    }, 500);

    return () => {
      clearTimeout(timer);
      if (isMaster) {
        try {
          currentChannel.postMessage({ type: "LEADER_RETIRE", id: instanceId });
        } catch (e) { /* suppress close race */ }
      }
      currentChannel.close();
      channelRef.current = null;
    };
  }, [instanceId, isMaster, setStoreMessages, setStoreLastIntent, claimLeadership, safePostMessage]);

  // Sync state to other tabs if Master
  useEffect(() => {
    if (isMaster && channelRef.current) {
      safePostMessage({ 
        type: "SYNC_STATE", 
        payload: { messages: storeMessages, lastIntent: storeLastIntent } 
      });
    }
  }, [isMaster, storeMessages, storeLastIntent]);

  const parentRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null); // For click-outside
  const toggleButtonRef = useRef<HTMLButtonElement>(null); // To exclude toggle button
  const abortControllerRef = useRef<AbortController | null>(null);
  const isAtBottomRef = useRef(true); // Task 1.10

  // Task 1.17 Optimization: Use store state directly
  const input = draftInput;
  const setInput = useCallback((val: string) => setDraftInput(val), [setDraftInput]);

  const [conversationState, setConversationState] = useState<ConversationState>({
    lastIntent: storeLastIntent,
    searchQuery: null,
    journeyActive: false,
  });

  // Sync state intent with store intent
  useEffect(() => {
    setConversationState(prev => ({ ...prev, lastIntent: storeLastIntent }));
  }, [storeLastIntent]);

  const [wakeWordEnabled, setWakeWordEnabled] = useState(true);

  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  useEffect(() => {
    const memory = loadMemory();
    if (memory.recentSearches) {
      setRecentSearches(memory.recentSearches);
    }
    // Initialize welcome if empty
    if (storeMessages.length === 0) {
      addToStore({ role: "assistant", content: WELCOME_MSG });
    }
  }, []);

  const saveSearchToMemory = useCallback((query: string) => {
    setRecentSearches(prev => {
      const updated = [query, ...prev.filter(s => s !== query)].slice(0, 3);
      saveMemory({ recentSearches: updated });
      return updated;
    });
  }, []);

  const addMessage = useCallback((role: "user" | "assistant" | "system", content: string, actions?: ChatAction[]) => {
    addToStore({ role, content, actions });
  }, [addToStore]);

  // Task 1.1: Virtualizer Setup
  const rowVirtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => messages[index]?.role === 'system' ? 40 : 80,
    overscan: 10,
  });

  // Task 1.14: Smart Scroll Detection with Auto-Hide
  const handleScroll = useCallback(() => {
    if (!parentRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = parentRef.current;
    const isBottom = scrollHeight - scrollTop - clientHeight < 100;
    isAtBottomRef.current = isBottom;
    if (isBottom) setShowNewMessageBadge(false);
  }, []);

  // Task 1.10: Scroll to Bottom (Frictionless)
  const scrollToNewMessage = useCallback((force = false) => {
    if (messages.length > 0 && (isAtBottomRef.current || force)) {
      rowVirtualizer.scrollToIndex(messages.length - 1, { align: 'start', behavior: 'smooth' });
      setShowNewMessageBadge(false);
    } else if (messages.length > 0 && !isAtBottomRef.current) {
      setShowNewMessageBadge(true);
    }
  }, [messages.length, rowVirtualizer]);

  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === "assistant" || lastMsg?.role === "user") {
        scrollToNewMessage();
    }
  }, [messages.length, scrollToNewMessage]);

  const clearChatHistory = useCallback(() => {
    // 1. Clear local store IMMEDIATELY for instant feedback
    clearStoreHistory();
    
    // 2. Re-add welcome message immediately
    addToStore({ role: "assistant", content: WELCOME_MSG });

    // 3. Clear backend history in background (Task 8.1 Resilience)
    fetch(getRailwayApiUrl(`/chat/history?session_id=${sessionIdRef.current}`), {
      method: 'DELETE'
    }).catch(e => console.warn("Failed to clear backend history", e));

    if ('vibrate' in navigator) {
      navigator.vibrate([200]); // Mission Clear Haptic
    }
    logEvent("chatbot_history_cleared");
  }, [clearStoreHistory, addToStore]);

  const triggerErrorFeedback = useCallback((vibrate = true) => {
    setIsError(true);
    if (vibrate && 'vibrate' in navigator) {
      try {
        navigator.vibrate([100, 50, 100]); // Stark-grade double pulse
      } catch (e) { /* Ignore intervention errors */ }
    }
    // Auto-clear error after 3s if no typing
    setTimeout(() => setIsError(false), 3000);
  }, [setIsError]);

  // Sync isError with input to clear it
  useEffect(() => {
    if (input.length > 0) setIsError(false);
  }, [input, setIsError]);

  // Task 1.15: Offline Queue Sync
  const syncOfflineQueue = useCallback(async () => {
    const queued = await getQueuedMessages();
    setOfflineQueueCount(queued.length);
    if (queued.length > 0 && isBackendOnline) {
      logEvent("chatbot_sync_offline_queue", { count: queued.length });
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        for (const msg of queued) {
          wsRef.current.send(JSON.stringify({ message: msg.content, session_id: msg.sessionId }));
          await clearQueuedMessage(msg.id);
        }
        setOfflineQueueCount(0);
      }
    }
  }, [isBackendOnline]);

  useEffect(() => {
    const interval = setInterval(syncOfflineQueue, 30000);
    return () => clearInterval(interval);
  }, [syncOfflineQueue]);

  // WebSocket Logic
  const connectWebSocket = useCallback(() => {
    if (!isMaster) return; // Only Master connects
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

    const wsUrl = getRailwayWsUrl("/chat/ws");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("Chat WebSocket Connected");
      setIsWsConnected(true);
      reconnectTimeoutRef.current = 1000; // Reset backoff
      logEvent("chatbot_ws_connected");
      syncOfflineQueue();
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Access store directly to avoid dependency on storeMessages array
      const state = useChatStore.getState();

      if (data.type === "token") {
        const lastMsg = state.messages[state.messages.length - 1];
        if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
          updateLastMessage(lastMsg.content + data.token, true);
        } else {
          addToStore({ role: "assistant", content: data.token, isStreaming: true });
        }
      } else if (data.type === "final") {
        setIsLoading(false);
        const filtered = state.messages.filter(m => !m.isStreaming);
        setStoreMessages([
          ...filtered,
          {
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: data.reply,
            timestamp: new Date().toISOString(),
            actions: data.actions,
            isStreaming: false
          }
        ]);
        if (data.intent) {
          setStoreLastIntent(data.intent);
        }
      } else if (data.type === "error") {
        setIsLoading(false);
        triggerErrorFeedback(false); // Don't vibrate on background errors
        addMessage("system", "⚠️ Protocol Failure: " + data.message);
      }
    };

    ws.onclose = () => {
      setIsWsConnected(false);
      wsRef.current = null;
      console.log("Chat WebSocket Disconnected");
      
      // Task 8.8: Exponential Backoff with Jitter
      if (useChatStore.getState().isOpen && isBackendOnline) {
        const jitter = Math.random() * 1000;
        const nextDelay = Math.min(reconnectTimeoutRef.current * 2, 30000) + jitter;
        reconnectTimeoutRef.current = nextDelay;
        
        console.log(`Reconnecting in ${Math.round(nextDelay)}ms...`);
        setTimeout(() => {
          connectWebSocket();
        }, nextDelay);
      }
    };

    ws.onerror = () => {
      triggerErrorFeedback(false); // Don't vibrate on background errors
    };
  }, [isMaster, isBackendOnline, syncOfflineQueue, triggerErrorFeedback, updateLastMessage, addToStore, setStoreMessages, setStoreLastIntent, addMessage]);

  useEffect(() => {
    if (isOpen && isBackendOnline) {
      connectWebSocket();
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isOpen, isBackendOnline, connectWebSocket]);

  const hasLoadedHistoryRef = useRef(false);

  // History Load (Server sync if needed)
  useEffect(() => {
    const loadHistory = async () => {
      if (hasLoadedHistoryRef.current) return;
      if (storeMessages.length > 1) {
        hasLoadedHistoryRef.current = true;
        return;
      }
      
      setIsHydrating(true);
      try {
        const res = await fetch(getRailwayApiUrl(`/chat/history?session_id=${sessionIdRef.current}`));
        if (res.ok) {
          const data = await res.json();
          if (data.messages && data.messages.length > 0) {
            const formatted = data.messages.map((m: any, i: number) => ({
              id: `hist-${i}`,
              role: m.role,
              content: m.content,
              timestamp: m.timestamp,
              actions: m.actions
            }));
            setStoreMessages([
              { id: "welcome", role: "assistant", content: WELCOME_MSG, timestamp: new Date().toISOString() },
              ...formatted
            ]);
          }
          hasLoadedHistoryRef.current = true;
        }
      } catch (e) { console.error("History load failed", e); }
      finally {
        setIsHydrating(false);
      }
    };
    if (isOpen) loadHistory();
  }, [isOpen, setIsHydrating, setStoreMessages]);

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
  }, [wakeWordEnabled, setIsOpen]);

  // Proactive Engine
  const triggerProactiveSuggestions = useCallback(() => {
    const ctx = {
      journeyActive: conversationState.journeyActive,
      timeOfDay: new Date().getHours(),
      guardianActive: conversationState.lastIntent === "enable_guardian",
      surgeLevel: surgeLevel // Task 6.8
    };
    
    const suggestions = evaluateProactiveRules(ctx);
    if (suggestions.length > 0) {
      const suggestion = suggestions[0];
      addMessage("system", `✨ AI Hint: ${suggestion.message}`, [suggestion.action]);
      logEvent("chatbot_proactive_suggestion_shown", { type: suggestion.action.value });
    }
  }, [conversationState, addMessage, surgeLevel]);

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
      setStoreLastIntent("search");

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
    [onSearchRequest, setStoreLastIntent]
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
      setStoreLastIntent("local_handled");
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

    if (text.toLowerCase().includes(" to ") || text.toLowerCase().includes(" from ")) {
      saveSearchToMemory(text);
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
      addMessage("system", "Voice interface incompatible with current hardware.");
      return;
    }
    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "en-IN";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onresult = (e: any) => {
      const t = e.results[0][0].transcript;
      setInput(t);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    
    recognition.start();
    setIsListening(true);
  };

  // Task 1.16: Auto-focus input on open
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 500); // Wait for animation to finish
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Task: Click outside to close (UX improvement)
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!isOpen) return;
      
      const target = event.target as Node;
      const isOutsideContainer = containerRef.current && !containerRef.current.contains(target);
      const isOutsideToggle = toggleButtonRef.current && !toggleButtonRef.current.contains(target);
      
      if (isOutsideContainer && isOutsideToggle) {
        setIsOpen(false);
        logEvent("chatbot_closed_outside_click");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, setIsOpen]);

  // Core Static Suggestion Actions (The "Button Pattern" within the interface)
  const getContextActions = useCallback(() => {
    if (conversationState.journeyActive) {
      return [
        { label: "Share Location", type: "intent", value: "Share live location", icon: <MapPin className="w-3 h-3" /> },
        { label: "Safety Status", type: "intent", value: "Check safety status", icon: <Activity className="w-3 h-3" /> },
      ];
    }
    if (conversationState.lastIntent === "search") {
      return [
        { label: "Check Availability", type: "intent", value: "Check Availability", icon: <Zap className="w-3 h-3" /> },
        { label: "Alternative Routes", type: "intent", value: "Alternative Routes", icon: <Navigation className="w-3 h-3" /> },
        { label: "PNR Status", type: "intent", value: "PNR Status", icon: <Activity className="w-3 h-3" /> },
      ];
    }
    return [
      { label: "Book Ticket", type: "intent", value: "Book Ticket", icon: <Ticket className="w-3.5 h-3.5 text-cyan-400" /> },
      { label: "Search Trains", type: "intent", value: "Search Trains", icon: <Navigation className="w-3.5 h-3.5" /> },
      { label: "Delhi → Mumbai", type: "intent", value: "Delhi to Mumbai", icon: <MapPin className="w-3.5 h-3.5" /> },
      // Hide non-critical features during high surge (Task 4.4/4.5)
      ...(surgeLevel !== 'High' && surgeLevel !== 'Critical' ? [
        { label: "My Bookings", type: "navigate", value: "/bookings", icon: <History className="w-3.5 h-3.5" /> },
        { label: "Dashboard", type: "navigate", value: "/dashboard", icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
        { label: "Telegram", type: "open_url", value: TELEGRAM_BOT_URL, icon: <MessageCircle className="w-3.5 h-3.5" /> },
      ] : []),
    ];
  }, [conversationState, surgeLevel]);

  return (
    <div className={cn("fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2 pointer-events-none", className)}>
      
      <AnimatePresence mode="wait">
        {isOpen && (
          <motion.div 
            key="chatbot-main-panel"
            ref={containerRef}
            initial={{ opacity: 0, scale: 0.8, originX: 1, originY: 1 }}
            animate={{ 
              opacity: 1,
              scale: 1, 
              x: isError ? [0, -10, 10, -10, 10, 0] : 0 
            }}
            exit={{ opacity: 0, scale: 0.8, originX: 1, originY: 1 }}
            transition={{ 
              type: "spring", 
              damping: 25, 
              stiffness: 300,
              opacity: { duration: 0.2 }
            }}
            className={cn(
              "w-full max-w-[440px] h-[calc(100vh-100px)] max-h-[800px] min-h-[500px] bg-background/90 dark:bg-[#0a0f1c]/95 backdrop-blur-[40px] border rounded-[2.5rem] shadow-[0_20px_80px_rgba(0,0,0,0.4)] flex flex-col overflow-hidden pointer-events-auto origin-bottom-right will-change-transform",
              isError 
                ? "border-red-500/50 shadow-[0_0_40px_rgba(239,68,68,0.3)]" 
                : "border-white/20 dark:border-cyan-500/30 dark:shadow-[0_20px_80px_rgba(6,182,212,0.15)]",
              isLowPowerMode && "low-power-mode"
            )}
          >
          
          {/* Header */}
          <div className="relative z-20 flex items-center justify-between px-8 py-4 bg-gradient-to-r from-[#0f172a] to-[#1e293b] dark:from-[#0a0f1c] dark:to-[#0f172a] border-b border-white/10 dark:border-cyan-500/30 overflow-hidden shrink-0">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:16px_16px] opacity-20"></div>
            
            <div className="relative flex items-center gap-4">
              {/* ... same bot icon stuff ... */}
              <div className="relative">
                <div className="w-10 h-10 rounded-xl bg-cyan-950/50 flex items-center justify-center shrink-0 border border-cyan-500/50 shadow-[0_0_15px_rgba(6,182,212,0.3)] rotate-3">
                  <Bot className="w-5 h-5 text-cyan-400 -rotate-3" />
                </div>
                <div className={cn(
                  "absolute inset-0 rounded-xl border-2 border-transparent border-t-cyan-400 animate-spin-slow",
                  isWsConnected ? "opacity-100" : "opacity-0"
                )}></div>
                <div className={cn(
                  "absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-[#0f172a] shadow-[0_0_10px_currentColor]",
                  !isBackendOnline ? "bg-red-500 text-red-500" : (surgeLevel === 'Normal' ? "bg-cyan-400 text-cyan-400" : "bg-yellow-400 text-yellow-400")
                )} />
              </div>
              <div>
                <h3 className="font-black text-base text-white tracking-tighter flex items-center gap-2">
                  RouteMaster <span className="text-cyan-400 font-mono text-[8px] opacity-70 border border-cyan-500/30 px-1 rounded uppercase">v2.5</span>
                </h3>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-[8px] text-cyan-400/60 font-mono tracking-[0.2em] uppercase">
                    {surgeLevel === 'Normal' ? 'Systems Nominal' : `Surge: ${surgeLevel}`}
                  </p>
                  <span className="w-1 h-1 rounded-full bg-white/20" />
                  <p className="text-[8px] text-white/40 font-mono tracking-tighter uppercase">
                    {latencyMs}ms / {fps}fps
                  </p>
                </div>
              </div>
            </div>
            <div className="relative z-30 flex items-center gap-2">
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  clearChatHistory();
                }} 
                title="Reset Terminal" 
                className="p-2 bg-white/5 hover:bg-red-500/20 rounded-xl transition-all border border-white/10 group cursor-pointer pointer-events-auto"
              >
                <Trash2 className="w-4 h-4 text-white/40 group-hover:text-red-400" />
              </button>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  setIsOpen(false);
                }} 
                className="relative p-2 bg-white/5 hover:bg-white/10 rounded-xl transition-all backdrop-blur-md border border-white/10 active:scale-95 cursor-pointer pointer-events-auto"
              >
                <X className="w-4 h-4 text-white/80" />
              </button>
            </div>
          </div>

          {/* Messages Area - MAXIMIZED & VIRTUALIZED (Task 1.1) */}
          <div 
            ref={parentRef} 
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto px-6 py-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] bg-gradient-to-b from-transparent via-muted/5 to-cyan-500/5 relative custom-scrollbar animate-neural"
          >
            {isHydrating ? (
              <div className="space-y-4">
                <ChatBubbleSkeleton role="assistant" />
                <ChatBubbleSkeleton role="user" />
                <ChatBubbleSkeleton role="assistant" />
              </div>
            ) : (
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const m = messages[virtualRow.index];
                  return (
                    <div 
                      key={m.id} 
                      data-index={virtualRow.index}
                      data-role={m.role}
                      ref={rowVirtualizer.measureElement}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      className={cn("flex gap-3 group message-container", 
                        m.role === "user" ? "flex-row-reverse py-3" : 
                        m.role === "system" ? "flex-row py-1" : "flex-row py-3"
                      )}
                    >
                      {m.role !== "system" && (
                        <div className={cn(
                          "w-8 h-8 shrink-0 rounded-lg flex items-center justify-center shadow-lg transition-transform group-hover:scale-105", 
                          m.role === "user" 
                            ? "bg-gradient-to-br from-indigo-500 to-purple-600 rotate-3" 
                            : "bg-gradient-to-br from-cyan-900 to-slate-900 border border-cyan-500/40 -rotate-3"
                        )}>
                          {m.role === "user" ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-cyan-400" />}
                        </div>
                      )}
                      <div className={cn("flex-1 min-w-0", m.role === "system" ? "flex justify-center" : "")}>
                        <div className={cn(
                          "max-w-[90%] rounded-2xl px-4 py-3 text-[14px] shadow-md leading-[1.5] transition-all", 
                          m.role === "user" 
                            ? "bg-gradient-to-br from-indigo-600 to-purple-700 text-white ml-auto rounded-tr-sm border border-indigo-400/20" 
                            : m.role === "system"
                              ? "bg-yellow-500/5 border border-yellow-500/10 text-yellow-600/80 dark:text-yellow-400/80 text-[10px] mx-auto text-center font-mono rounded-full py-1 px-4 backdrop-blur-sm"
                              : "bg-white dark:bg-[#0f172a]/90 text-foreground border border-border/40 dark:border-cyan-500/10 rounded-tl-sm shadow-cyan-500/5"
                        )}>
                          <MarkdownRenderer content={m.content} />
                          {m.role !== "system" && (
                            <span className="text-[8px] opacity-30 mt-1 block text-right font-mono tracking-widest uppercase">
                              {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          )}
                        </div>
                        
                        {/* Inline Message Actions */}
                        {m.actions && m.actions.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-3 ml-1">
                            {m.actions.map((a, i) => (
                              <button key={i} onClick={() => handleActionClick(a)} className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-[11px] font-bold bg-background border border-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500 hover:text-white dark:hover:bg-cyan-500 dark:hover:text-white transition-all shadow-sm active:scale-95">
                                {a.icon && <span className="shrink-0 flex items-center justify-center">{a.icon}</span>}
                                <span className="leading-none">{a.label}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {isLoading && (
              <div className="py-4">
                <TypingIndicator durationMs={2500} onCancel={handleCancel} />
              </div>
            )}
          </div>

          {/* New Message Badge (Task 1.10) */}
          <AnimatePresence>
            {showNewMessageBadge && (
              <div key="new-message-badge" className="absolute bottom-32 left-1/2 -translate-x-1/2 z-10">
                <motion.button 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  onClick={() => scrollToNewMessage(true)}
                  className="px-4 py-2 bg-cyan-500 text-white text-[10px] font-black uppercase tracking-widest rounded-full shadow-lg flex items-center gap-2 hover:bg-cyan-600 transition-all border-2 border-white/20"
                >
                  <ChevronDown className="w-3 h-3 animate-bounce" />
                  New Telemetry Received
                </motion.button>
              </div>
            )}
          </AnimatePresence>

          {/* Unified Smart Input Area - MINIMIZED SUGGESTIONS */}
          <div className="p-4 border-t border-border/20 bg-white/60 dark:bg-[#0a0f1c]/95 backdrop-blur-3xl space-y-3 shrink-0">
            
            {/* Task 1.2: Recent Searches */}
            {recentSearches.length > 0 && !isHydrating && (
              <div className="flex gap-1.5 overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] pb-1">
                {recentSearches.map((s, i) => (
                  <button key={i} onClick={() => handleSendCore(s)} className="text-[9px] font-bold bg-cyan-500/5 border border-cyan-500/10 text-cyan-400/80 px-2 py-1 rounded-lg whitespace-nowrap hover:bg-cyan-500 hover:text-white transition-all">
                    {s}
                  </button>
                ))}
              </div>
            )}

            {/* Context-Aware Quick Actions - COMPACT GRID */}
            <div className="grid grid-cols-3 gap-1">
              {isHydrating ? (
                <>
                  {[1, 2, 3, 4, 5, 6].map(i => (
                    <div key={i} className="h-8 bg-slate-800/20 rounded-xl animate-pulse" />
                  ))}
                </>
              ) : (
                getContextActions().map((a, idx) => (
                  <button 
                    key={idx} 
                    onClick={() => handleActionClick(a)} 
                    className={cn(
                      "flex items-center justify-center gap-1.5 px-2 py-2 rounded-xl text-[10px] font-black transition-all border shadow-sm group",
                      a.type === "system_control"
                        ? "bg-red-500/5 text-red-600 dark:text-red-400 border-red-500/10 hover:bg-red-600 hover:text-white"
                        : "bg-secondary/30 text-secondary-foreground border-transparent hover:border-cyan-500/30 hover:bg-cyan-500/5 dark:hover:bg-cyan-950/40"
                    )}
                  >
                    <span className="shrink-0 transition-transform group-hover:scale-110">{a.icon}</span>
                    <span className="truncate leading-none uppercase tracking-tighter">{a.label}</span>
                  </button>
                ))
              )}
            </div>

            {/* Offline/Status Notice */}
            {!isBackendOnline && (
              <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/5 border border-amber-500/10 text-amber-600 dark:text-amber-400 rounded-xl text-[9px] font-bold tracking-tight shrink-0">
                <WifiOff className="w-3 h-3" />
                <span className="flex-1 uppercase font-mono">Buffer: {offlineQueueCount} pkts</span>
                <RefreshCw className="w-2.5 h-2.5 animate-spin" />
              </div>
            )}
            
            {/* Input Field */}
            <div className="relative">
              <div className={cn(
                "flex items-center gap-2 bg-background dark:bg-[#1e293b]/40 border border-border/40 focus-within:border-cyan-500/40 rounded-2xl p-1.5 shadow-inner transition-all shrink-0",
                retryAfter > 0 && "opacity-50 pointer-events-none grayscale"
              )}>
                <button onClick={toggleVoice} className={cn("p-2.5 rounded-xl transition-all active:scale-90", isListening ? "bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse" : "text-muted-foreground hover:bg-secondary hover:text-foreground")}>
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder={retryAfter > 0 ? `System Throttled (${retryAfter}s)` : "Message..."}
                  className="flex-1 bg-transparent px-1 py-2 outline-none text-sm placeholder:text-muted-foreground/40 font-medium"
                />
                <button
                  aria-label="Send"
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading || retryAfter > 0}
                  className="p-2.5 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-md disabled:opacity-30 disabled:grayscale transition-all hover:shadow-[0_0_20px_rgba(6,182,212,0.4)] active:scale-90"
                >
                  <Send className="w-4.5 h-4.5 ml-0.5" />
                </button>
              </div>
              
              {/* Task 4.6: Traffic Shaping Overlay */}
              {retryAfter > 0 && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0a0f1c]/20 backdrop-blur-[2px] rounded-2xl">
                  <div className="flex items-center gap-2 px-3 py-1 bg-black/60 border border-white/10 rounded-full animate-in zoom-in-95 duration-200">
                    <Activity className="w-3 h-3 text-cyan-400 animate-pulse" />
                    <span className="text-[10px] font-black text-white uppercase tracking-widest">
                      Resource Wait: {retryAfter}s
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Control Hub */}
      <div className="flex items-center gap-4 pointer-events-auto">
        <button 
          ref={toggleButtonRef}
          onClick={() => setIsOpen(!isOpen)} 
          className={cn(
            "w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-500 shadow-[0_10px_40px_rgba(0,0,0,0.3)] border-2 border-white/10 active:scale-90",
            isOpen 
              ? "bg-[#0f172a] text-white rotate-180 scale-90" 
              : "bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600 text-white hover:scale-105 hover:shadow-[0_0_30px_rgba(6,182,212,0.5)]"
          )}
        >
          {isOpen ? <X className="w-7 h-7" /> : <Bot className="w-8 h-8" />}
        </button>
      </div>

    </div>
  );
}
