import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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
  timestamp: string;
  actions?: ChatAction[];
  isStreaming?: boolean;
}

interface ChatState {
  isOpen: boolean;
  isHydrating: boolean;
  isError: boolean;
  messages: ChatMessage[];
  lastIntent: string | null;
  setIsOpen: (open: boolean) => void;
  setIsHydrating: (loading: boolean) => void;
  setIsError: (error: boolean) => void;
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  setMessages: (msgs: ChatMessage[]) => void;
  updateLastMessage: (content: string, isStreaming: boolean) => void;
  setLastIntent: (intent: string | null) => void;
  clearHistory: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      isOpen: false,
      isHydrating: false,
      isError: false,
      messages: [],
      lastIntent: null,
      setIsOpen: (open) => set({ isOpen: open }),
      setIsHydrating: (loading) => set({ isHydrating: loading }),
      setIsError: (error) => set({ isError: error }),
      setMessages: (msgs) => set({ messages: msgs }),
      addMessage: (msg) => set((state) => ({
        messages: [
          ...state.messages,
          {
            ...msg,
            id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            timestamp: new Date().toISOString()
          }
        ]
      })),
      updateLastMessage: (content, isStreaming) => set((state) => {
        const lastMsg = state.messages[state.messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
          const updated = [...state.messages];
          updated[updated.length - 1] = { ...lastMsg, content, isStreaming };
          return { messages: updated };
        }
        return state;
      }),
      setLastIntent: (intent) => set({ lastIntent: intent }),
      clearHistory: () => set({ messages: [], lastIntent: null }),
    }),
    {
      name: 'routemaster-chat-storage',
    }
  )
);
