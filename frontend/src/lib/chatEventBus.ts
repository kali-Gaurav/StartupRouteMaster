/**
 * Event bus between chatbot and frontend. Chatbot emits; UI (e.g. Index, Navbar) listens.
 * No tight coupling: actions are typed (search | navigate | sort | open_url).
 */

export type ChatSearchPayload = { fromCode: string; toCode: string; date?: string };
export type ChatSortPayload = { sortBy: "duration" | "cost" };
export type ChatNavigatePayload = { path: string };

const EVENT_SEARCH = "chat:search";
const EVENT_NAVIGATE = "chat:navigate";
const EVENT_SORT = "chat:sort";

export const chatEventBus = {
  /** Emit when chatbot triggers a route search. Listeners run search(fromCode, toCode, date). */
  emitSearch(payload: ChatSearchPayload): void {
    window.dispatchEvent(new CustomEvent(EVENT_SEARCH, { detail: payload }));
  },

  onSearch(handler: (e: CustomEvent<ChatSearchPayload>) => void): () => void {
    const wrapped = (e: Event) => handler(e as CustomEvent<ChatSearchPayload>);
    window.addEventListener(EVENT_SEARCH, wrapped);
    return () => window.removeEventListener(EVENT_SEARCH, wrapped);
  },

  /** Emit when chatbot requests navigation. Listeners call navigate(path). */
  emitNavigate(payload: ChatNavigatePayload): void {
    window.dispatchEvent(new CustomEvent(EVENT_NAVIGATE, { detail: payload }));
  },

  onNavigate(handler: (e: CustomEvent<ChatNavigatePayload>) => void): () => void {
    const wrapped = (e: Event) => handler(e as CustomEvent<ChatNavigatePayload>);
    window.addEventListener(EVENT_NAVIGATE, wrapped);
    return () => window.removeEventListener(EVENT_NAVIGATE, wrapped);
  },

  /** Emit when user chooses sort (duration/cost). Listeners update sort and optionally re-fetch. */
  emitSort(payload: ChatSortPayload): void {
    window.dispatchEvent(new CustomEvent(EVENT_SORT, { detail: payload }));
  },

  onSort(handler: (e: CustomEvent<ChatSortPayload>) => void): () => void {
    const wrapped = (e: Event) => handler(e as CustomEvent<ChatSortPayload>);
    window.addEventListener(EVENT_SORT, wrapped);
    return () => window.removeEventListener(EVENT_SORT, wrapped);
  },
};
