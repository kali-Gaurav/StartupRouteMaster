import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useSosSocket, SosAlert } from "../hooks/useSosWebSocket";
import { AlertCircle } from "lucide-react";


export default function ResponderPage() {
  const { user, isAuthenticated } = useAuth();
  const [alerts, setAlerts] = useState<SosAlert[]>([]);
  const { connected } = useSosSocket((alert: SosAlert) => {
    setAlerts((prev) => [alert, ...prev]);
  });

  if (!isAuthenticated) {
    return <p>Please login to view SOS alerts.</p>;
  }
  if (user && !["admin", "responder", "support"].includes((user as any).role || "")) {
    return <p>You are not authorized to view this page.</p>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">SOS Alerts</h1>
      <p className="mb-2">
        WebSocket status: <strong>{connected ? "connected" : "disconnected"}</strong>
      </p>
      <ul className="space-y-2">
        {alerts.map((a) => (
          <li key={a.id} className="border p-2 rounded">
            <p>
              <span className="font-semibold">{a.name || a.id}</span> -{' '}
              {a.trip?.vehicle_number || "unknown vehicle"}
            </p>
            <p>
              Location: {a.lat.toFixed(4)},{a.lng.toFixed(4)}{' '}
              {a.priority && <span className="text-red-600">({a.priority})</span>}
            </p>
            <p className="text-sm text-muted-foreground">{a.triggered_at}</p>
          </li>
        ))}
      </ul>
      {alerts.length === 0 && (
        <div className="text-center text-muted-foreground mt-8">
          <AlertCircle className="inline-block w-8 h-8 mb-2" />
          <p>No alerts received yet.</p>
        </div>
      )}
    </div>
  );
}
