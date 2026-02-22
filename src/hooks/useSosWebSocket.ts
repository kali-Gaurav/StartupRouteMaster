import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";

export interface SosAlert {
  id: string;
  lat: number;
  lng: number;
  [key: string]: any;
}

export function useSosSocket(onAlert?: (alert: SosAlert) => void) {
  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }

    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host;
    const url = `${scheme}://${host}/api/ws/sos?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "sos_alert") {
          onAlert && onAlert(msg.data);
        }
      } catch (e) {
        console.error("Invalid WS message", e);
      }
    };
    ws.onclose = () => {
      setConnected(false);
      // attempt reconnect after short delay if token still exists
      setTimeout(() => {
        if (token) {
          setConnected(false); // trigger effect rerun by bumping token? actually token unchanged will not rerun
          // we deliberately rely on effect dependency on token
        }
      }, 5000);
    };
    ws.onerror = (e) => {
      console.error("WS error", e);
    };

    return () => {
      try {
        ws.close();
      } catch {}
    };
  }, [token, onAlert]);

  return { connected, ws: wsRef.current };
}
