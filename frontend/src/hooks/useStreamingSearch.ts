/**
 * useStreamingSearch — Zero-Block Progressive Results Hook
 * Connects to /api/v3/search/stream (SSE) and progressively delivers
 * routes to the UI as the backend discovers them.
 *
 * Usage:
 *   const { routes, isStreaming, isComplete, error, startSearch } = useStreamingSearch();
 */

import { useState, useCallback, useRef } from "react";
import type { Route } from "@/data/routes";
import { mapBackendRoutesToRoutes } from "@/services/railwayBackApi";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const STREAM_ENDPOINT = `${BASE_URL}/api/v3/search/stream`;

type StreamChunkType = "HEARTBEAT" | "FAST_PATH" | "ENRICHED" | "end";

interface StreamChunk {
  chunk: string;
  journeys?: unknown[];
  latency_ms?: number;
  status?: string;
  metadata?: any;
}

interface UseStreamingSearchResult {
  routes: Route[];
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  latencyMs: number | null;
  metadata: any | null;
  startSearch: (source: string, destination: string, date: string, persona?: string) => Promise<void>;
  cancelSearch: () => void;
}

export function useStreamingSearch(
  onFirstResults?: (routes: Route[]) => void
): UseStreamingSearchResult {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [metadata, setMetadata] = useState<any | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const hasFirstResults = useRef(false);

  const cancelSearch = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const startSearch = useCallback(
    (source: string, destination: string, date: string, persona = "ECONOMY") => {
      // Cancel any in-flight search
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Reset state
      setRoutes([]);
      setIsStreaming(true);
      setIsComplete(false);
      setError(null);
      setLatencyMs(null);
      setMetadata(null);
      hasFirstResults.current = false;

      const url = new URL(STREAM_ENDPOINT);
      url.searchParams.set("source", source.toUpperCase());
      url.searchParams.set("destination", destination.toUpperCase());
      url.searchParams.set("date", date);
      url.searchParams.set("persona", persona);

      const parseEvent = (rawEvent: string) => {
        const lines = rawEvent.split(/\r?\n/);
        let eventType = "message";
        const dataLines: string[] = [];

        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.replace(/^event:\s*/, "").trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.replace(/^data:\s*/, ""));
          }
        }

        return { eventType, data: dataLines.join("\n") };
      };

      return new Promise<void>(async (resolve, reject) => {
        try {
          const res = await fetch(url.toString(), {
            signal: controller.signal,
            headers: { Accept: "text/event-stream" },
          });

          if (!res.ok) throw new Error(`Stream error: ${res.status}`);
          if (!res.body) throw new Error("Response body is null");

          resolve();
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split(/\n\n/);
            buffer = events.pop() ?? "";

            for (const rawEvent of events) {
              if (!rawEvent.trim()) continue;
              const { eventType, data } = parseEvent(rawEvent);
              if (!data) continue;

              if (eventType === "end") {
                setIsComplete(true);
                setIsStreaming(false);
                return;
              }

              if (eventType === "error") {
                setError(data);
                setIsStreaming(false);
                return;
              }

              try {
                const chunk: StreamChunk = JSON.parse(data);

                if (chunk.latency_ms) setLatencyMs(chunk.latency_ms);
                if (chunk.metadata) setMetadata(chunk.metadata);

                if (chunk.chunk === "HEARTBEAT") {
                  continue;
                }

                if (chunk.journeys && chunk.journeys.length > 0) {
                  const mapped = mapBackendRoutesToRoutes(
                    { data: { journeys: chunk.journeys } } as any,
                    source,
                    destination
                  );

                  setRoutes((prev) => {
                    const existingIds = new Set(prev.map((r) => r.id));
                    const newOnes = mapped.filter((r) => !existingIds.has(r.id));
                    return [...prev, ...newOnes];
                  });

                  if (!hasFirstResults.current && mapped.length > 0) {
                    hasFirstResults.current = true;
                    onFirstResults?.(mapped);
                  }
                }
              } catch {
                continue;
              }
            }
          }

          setIsComplete(true);
          setIsStreaming(false);
        } catch (err: unknown) {
          if ((err as { name?: string }).name === "AbortError") return;
          setError(err instanceof Error ? err.message : "Stream failed");
          setIsStreaming(false);
          reject(err);
        }
      });
    },
    [onFirstResults]
  );

  return { routes, isStreaming, isComplete, error, latencyMs, metadata, startSearch, cancelSearch };
}
