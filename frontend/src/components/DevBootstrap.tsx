/**
 * Dev-only: wire event/error logging to dev event log for DevDebugPanel.
 * Renders nothing; runs side effects when in DEV.
 */

import { useEffect } from "react";
import { setEventLogger, setErrorReporter } from "@/lib/observability";
import { pushDevEvent, setLastDevError } from "@/lib/devEventLog";

export function DevBootstrap() {
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    setEventLogger((event, payload, level) => {
      pushDevEvent(event, payload as Record<string, unknown>, level);
      console.debug("[logEvent]", event, payload);
    });
    setErrorReporter((error, context) => {
      setLastDevError(error);
      console.error("[reportError]", error, context);
    });
  }, []);
  return null;
}
