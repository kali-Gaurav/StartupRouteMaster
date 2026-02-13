/**
 * Mini App auth gate: when opened from Telegram, validates initData and exchanges for JWT.
 * Ensures all /mini-app/* routes have a valid session (same auth as web).
 */

import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { telegramAuth } from "@/lib/authApi";

type GateState = "loading" | "ready" | "error";

export function MiniAppGate({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, login, isAuthenticated } = useAuth();
  const [gateState, setGateState] = useState<GateState>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    const isMiniAppRoute = location.pathname.startsWith("/mini-app");
    if (!isMiniAppRoute) {
      setGateState("ready");
      return;
    }

    const webApp = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
    const initData = webApp?.initData;
    const user = webApp?.initDataUnsafe?.user;

    // Already have a token (e.g. from previous Telegram auth or web login)
    if (token && isAuthenticated) {
      setGateState("ready");
      return;
    }

    // Not in Telegram: allow through for dev (browser testing)
    if (!webApp || !initData) {
      setGateState("ready");
      return;
    }

    // In Telegram with initData but no token: exchange for JWT
    if (!user) {
      setErrorMessage("Invalid session. Please open the app from Telegram again.");
      setGateState("error");
      return;
    }

    let cancelled = false;
    const attempt = (retry = false) => {
      telegramAuth(initData, user)
        .then((res) => {
          if (cancelled) return;
          if (res.success && res.token && res.user) {
            login(res.token, res.user);
            setGateState("ready");
          } else {
            setErrorMessage(res.message || "Sign-in failed. Please try again from Telegram.");
            setGateState("error");
          }
        })
        .catch((err) => {
          if (cancelled) return;
          if (!retry && (err?.message?.includes("network") || err?.message?.includes("fetch"))) {
            setTimeout(() => attempt(true), 1500);
          } else {
            setErrorMessage(err?.message || "Connection error. Check your internet and try again.");
            setGateState("error");
          }
        });
    };
    attempt();

    return () => {
      cancelled = true;
    };
  }, [location.pathname, token, isAuthenticated, login]);

  if (gateState === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
          <p className="text-sm text-gray-600">Setting up your session...</p>
        </div>
      </div>
    );
  }

  if (gateState === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
        <div className="max-w-sm w-full rounded-xl bg-white shadow-lg border border-gray-200 p-6 text-center space-y-4">
          <div className="text-amber-500 text-5xl">⚠️</div>
          <h2 className="text-lg font-semibold text-gray-900">Could not sign in</h2>
          <p className="text-sm text-gray-600">{errorMessage}</p>
          <button
            type="button"
            onClick={() => navigate("/mini-app/home")}
            className="w-full py-2 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
