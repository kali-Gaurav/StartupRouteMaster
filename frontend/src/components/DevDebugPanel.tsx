/**
 * Dev-only debug panel: Events | Errors | Queries.
 * Toggle with Ctrl+Shift+D or bug icon. Modular tabs for scaling.
 */

import { useState, useEffect } from "react";
import { queryClient } from "@/infrastructure/queryClient";
import { getDevEventLog, getLastDevError, type DevEventEntry, type EventLevel } from "@/lib/devEventLog";
import { X, Bug, List, AlertCircle, Database } from "lucide-react";

type TabId = "events" | "errors" | "queries";

const LEVEL_COLOR: Record<EventLevel, string> = {
  info: "text-muted-foreground",
  warn: "text-amber-600",
  error: "text-destructive",
  critical: "text-destructive font-semibold",
};

export function DevDebugPanel() {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("events");
  const [tick, setTick] = useState(0);
  const [snapshot, setSnapshot] = useState<{
    queries: { key: string; state: string; dataUpdatedAt: number; isStale: boolean }[];
    events: DevEventEntry[];
    lastError: string | null;
  }>({ queries: [], events: [], lastError: null });

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "D") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    const onUpdate = () => setTick((t) => t + 1);
    window.addEventListener("dev-event-log-update", onUpdate);
    return () => window.removeEventListener("dev-event-log-update", onUpdate);
  }, []);

  useEffect(() => {
    if (!open) return;
    const cache = queryClient.getQueryCache();
    const all = cache.getAll();
    const queries = all.map((q) => ({
      key: JSON.stringify(q.queryKey),
      state: q.state.status,
      dataUpdatedAt: q.state.dataUpdatedAt ?? 0,
      isStale: q.isStale(),
    }));
    setSnapshot({
      queries,
      events: getDevEventLog(),
      lastError: getLastDevError()?.message ?? null,
    });
  }, [open, tick]);

  if (!import.meta.env.DEV) return null;
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-[99] p-2 rounded-lg bg-muted border border-border text-muted-foreground hover:text-foreground"
        aria-label="Open debug panel"
      >
        <Bug className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-[99] w-96 max-h-[28rem] flex flex-col rounded-xl border-2 border-border bg-background shadow-xl text-sm">
      <div className="sticky top-0 flex items-center justify-between p-2 border-b border-border bg-muted/50 shrink-0">
        <span className="font-medium">Dev Debug</span>
        <button type="button" onClick={() => setOpen(false)} aria-label="Close">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex border-b border-border shrink-0">
        {(
          [
            { id: "events" as TabId, label: "Events", icon: List },
            { id: "errors" as TabId, label: "Errors", icon: AlertCircle },
            { id: "queries" as TabId, label: "Queries", icon: Database },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors ${
              activeTab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto p-2 min-h-0">
        {activeTab === "events" && (
          <ul className="space-y-1 font-mono text-xs max-h-64 overflow-auto">
            {snapshot.events.slice(0, 50).map((ev, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-1">
                <span className={LEVEL_COLOR[ev.level ?? "info"]}>[{ev.level ?? "info"}]</span>
                <span className="text-foreground">{ev.event}</span>
                {ev.payload && Object.keys(ev.payload).length > 0 && (
                  <span className="text-muted-foreground truncate max-w-[12rem]">
                    {JSON.stringify(ev.payload)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {activeTab === "errors" && (
          <div className="space-y-2">
            {snapshot.lastError ? (
              <div className="p-2 rounded bg-destructive/10 text-destructive text-xs break-words">
                {snapshot.lastError}
              </div>
            ) : (
              <p className="text-muted-foreground text-xs">No error recorded this session.</p>
            )}
          </div>
        )}
        {activeTab === "queries" && (
          <div className="space-y-1 font-mono text-xs">
            <div className="text-muted-foreground mb-1">Total: {snapshot.queries.length}</div>
            {snapshot.queries.slice(0, 30).map((q, i) => (
              <div key={i} className="p-1.5 rounded bg-muted/50 break-all">
                <div className="font-medium text-foreground truncate" title={q.key}>
                  {q.key}
                </div>
                <div className="text-muted-foreground">
                  {q.state} · {q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toLocaleTimeString() : "—"} ·{" "}
                  {q.isStale ? "stale" : "fresh"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
